from __future__ import annotations

import base64
import json
import os
import re
import secrets
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


DEFAULT_BASE_URL = "https://flow.team"
DEFAULT_SESSION_PATH = Path(os.environ.get("FLOW_SESSION_PATH", "~/.flow-mcp/session.json")).expanduser()
DEFAULT_SCHEDULE_PROJECT_TITLE = os.environ.get("FLOW_DEFAULT_SCHEDULE_PROJECT_TITLE", "일정 공유")


class FlowApiError(RuntimeError):
    pass


@dataclass
class FlowSession:
    user_id: str
    rgsn_dttm: str
    cookies: dict[str, str] = field(default_factory=dict)

    def redacted(self) -> dict[str, Any]:
        return {
            "user_id": _redact(self.user_id),
            "rgsn_dttm": _redact(self.rgsn_dttm),
            "cookies": sorted(self.cookies.keys()),
        }


def _redact(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return value[:1] + "***"
    return value[:4] + "..." + value[-4:]


def _decode_har_content(content: dict[str, Any]) -> str:
    text = content.get("text") or ""
    if content.get("encoding") == "base64":
        return base64.b64decode(text).decode("utf-8", "replace")
    return text


def _parse_post_json_from_har_entry(entry: dict[str, Any]) -> Optional[dict[str, Any]]:
    raw = entry.get("request", {}).get("postData", {}).get("text") or ""
    if not raw:
        return None
    form = dict(urllib.parse.parse_qsl(raw, keep_blank_values=True))
    val = form.get("_JSON_")
    if not val:
        return None
    return json.loads(urllib.parse.unquote_plus(val))


def extract_session_from_har(har_path: str | Path) -> FlowSession:
    """Extract USER_ID/RGSN_DTTM from a HAR captured from your own logged-in Flow session."""
    path = Path(har_path).expanduser()
    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    entries = data.get("log", {}).get("entries", [])
    best: FlowSession | None = None
    for entry in entries:
        payload = _parse_post_json_from_har_entry(entry)
        if not payload:
            continue
        user_id = payload.get("USER_ID")
        rgsn_dttm = payload.get("RGSN_DTTM")
        if user_id and rgsn_dttm and str(rgsn_dttm).startswith("FLOW_"):
            token = str(rgsn_dttm)
            # HAR JSON values are still URL-encoded once (token specials like %2F);
            # normalize to raw base64 so the send path can re-encode deterministically.
            while "%" in token:
                dec = urllib.parse.unquote(token)
                if dec == token:
                    break
                token = dec
            # Flow auth also requires server-issued cookies (JSESSIONID, AWSALB sticky
            # session). Pull them from the same HAR entry — the latest match wins.
            cookies_arr = entry.get("request", {}).get("cookies") or []
            cookies = {c["name"]: c["value"] for c in cookies_arr if c.get("name") and c.get("value") is not None}
            best = FlowSession(user_id=str(user_id), rgsn_dttm=token, cookies=cookies)
    if best is None:
        raise FlowApiError("No authenticated USER_ID/RGSN_DTTM pair found in HAR")
    return best


def _flow_password_encrypt(password: str, cur_dttm: str) -> str:
    """Replicate Flow web login's fallback password transform.

    The browser code currently does:
      GibberishAES.size(256)
      GibberishAES.aesEncrypt(password, "aes256-global-flow" + CUR_DTTM)

    For flow.team, FLOW_CUR_TIME_R001 usually returns an empty RSA KEY, so this AES-CBC
    path is used. The key string is exactly 32 UTF-8 bytes when CUR_DTTM is YYYYMMDDHHMMSS.
    """
    key = ("aes256-global-flow" + (cur_dttm or "00000000000000")).encode("utf-8")
    if len(key) != 32:
        raise FlowApiError(f"Unexpected Flow password key length: {len(key)}")
    data = password.encode("utf-8")
    pad_len = 16 - (len(data) % 16)
    padded = data + bytes([pad_len]) * pad_len
    encryptor = Cipher(algorithms.AES(key), modes.CBC(bytes(16))).encryptor()
    encrypted = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(encrypted).decode("ascii")


def _flow_device_json() -> dict[str, str]:
    """Match Flow web's Often.getDeviceJson() shape for browser logins."""
    duid = f"{secrets.randbelow(1_000_001)}-{secrets.randbelow(1_001)}-{secrets.randbelow(1_001)}-{secrets.randbelow(1_000_001)}"
    return {"DUID": duid, "DUID_NM": f"PC-CHROME_{duid}"}


def _local_timezone_name() -> str:
    tz = os.environ.get("TZ")
    if tz:
        try:
            ZoneInfo(tz)
            return tz
        except ZoneInfoNotFoundError:
            pass
    # Flow's Korean workspace usually uses Asia/Seoul; this is also what the browser sends
    # for Korea-based users. The header is advisory for login/session validation.
    return "Asia/Seoul"


class FlowClient:
    """Small unofficial Flow.team web endpoint client.

    Observed request format:
      POST https://flow.team/<ENDPOINT>.jct
      Content-Type: application/x-www-form-urlencoded; charset=UTF-8
      body: _JSON_=<urlencoded JSON>

    Auth for normal API calls requires both USER_ID + RGSN_DTTM in the JSON body AND
    the server-issued session cookies (JSESSIONID, plus AWSALB sticky-session pair).
    Without the cookies, the server treats the request as a brand-new anonymous session
    and returns S0002 even with a valid token. The token and the cookies are both
    sensitive and persisted to ~/.flow-mcp/session.json together.
    """

    def __init__(
        self,
        user_id: str | None = None,
        rgsn_dttm: str | None = None,
        base_url: str | None = None,
        session_path: str | Path | None = None,
    ) -> None:
        self.base_url = (base_url or os.environ.get("FLOW_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.session_path = Path(session_path or DEFAULT_SESSION_PATH).expanduser()
        self.user_id = user_id or os.environ.get("FLOW_USER_ID") or ""
        self.rgsn_dttm = rgsn_dttm or os.environ.get("FLOW_RGSN_DTTM") or ""
        self.http = httpx.Client(
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0 flow-mcp/0.1",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/main.act",
                "X-Requested-With": "XMLHttpRequest",
                "x-user-timezone": _local_timezone_name(),
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            },
        )
        if not (self.user_id and self.rgsn_dttm):
            loaded = self.load_session(required=False)
            if loaded and loaded.cookies:
                self._apply_cookies(loaded.cookies)

    def _apply_cookies(self, cookies: dict[str, str]) -> None:
        domain = urllib.parse.urlparse(self.base_url).hostname or "flow.team"
        for name, value in cookies.items():
            self.http.cookies.set(name, value, domain=domain, path="/")

    def _current_cookies(self) -> dict[str, str]:
        return {c.name: c.value for c in self.http.cookies.jar}

    @property
    def session(self) -> FlowSession:
        if not self.user_id or not self.rgsn_dttm:
            raise FlowApiError("Flow session is not configured. Use flow_import_session_from_har or set FLOW_USER_ID/FLOW_RGSN_DTTM.")
        return FlowSession(self.user_id, self.rgsn_dttm, cookies=self._current_cookies())

    def save_session(self, session: FlowSession | None = None) -> dict[str, Any]:
        session = session or self.session
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {"user_id": session.user_id, "rgsn_dttm": session.rgsn_dttm}
        if session.cookies:
            payload["cookies"] = session.cookies
        self.session_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            self.session_path.chmod(0o600)
        except OSError:
            pass
        self.user_id = session.user_id
        self.rgsn_dttm = session.rgsn_dttm
        if session.cookies:
            self._apply_cookies(session.cookies)
        return {"ok": True, "path": str(self.session_path), "session": session.redacted()}

    def load_session(self, required: bool = True) -> Optional[FlowSession]:
        if self.session_path.exists():
            data = json.loads(self.session_path.read_text(encoding="utf-8"))
            self.user_id = data["user_id"]
            self.rgsn_dttm = data["rgsn_dttm"]
            cookies = data.get("cookies") or {}
            if not isinstance(cookies, dict):
                cookies = {}
            return FlowSession(self.user_id, self.rgsn_dttm, cookies=cookies)
        if required:
            raise FlowApiError(f"Session file not found: {self.session_path}")
        return None

    def import_session_from_har(self, har_path: str | Path) -> dict[str, Any]:
        session = extract_session_from_har(har_path)
        return self.save_session(session)

    def set_session(self, user_id: str, rgsn_dttm: str) -> dict[str, Any]:
        return self.save_session(FlowSession(user_id=user_id, rgsn_dttm=rgsn_dttm))

    @staticmethod
    def _encode_jct_body(payload: dict[str, Any]) -> str:
        """Build the _JSON_ form body exactly as Flow's web client does.

        Flow double-URL-encodes the whole _JSON_ value, and embeds the RGSN_DTTM
        token already URL-encoded once (so its '/', '+', '=' end up triple-encoded
        on the wire). Sending a single-encoded body yields S0002 'session expired'
        even with a valid token. Verified byte-for-byte against a captured request.
        """
        p = dict(payload)
        tok = p.get("RGSN_DTTM")
        if tok:
            # Stored token may be raw base64 or partially %-encoded; normalize to raw.
            while "%" in tok:
                dec = urllib.parse.unquote(tok)
                if dec == tok:
                    break
                tok = dec
            p["RGSN_DTTM"] = urllib.parse.quote(tok, safe="")
        js = json.dumps(p, ensure_ascii=False, separators=(",", ":"))
        return "_JSON_=" + urllib.parse.quote(urllib.parse.quote(js, safe=""), safe="")

    def _post(self, endpoint: str, payload: dict[str, Any], *, referer_path: str = "/main.act", retries: int = 2) -> dict[str, Any]:
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        body = self._encode_jct_body(payload)
        headers = {"Referer": f"{self.base_url}{referer_path}"}
        last_head: Any = None
        for attempt in range(retries + 1):
            resp = self.http.post(f"{self.base_url}{endpoint}", content=body, headers=headers)
            resp.raise_for_status()
            try:
                data = resp.json()
            except json.JSONDecodeError as exc:
                raise FlowApiError(f"Non-JSON response from {endpoint}: {resp.text[:300]}") from exc
            head = data.get("COMMON_HEAD") if isinstance(data, dict) else None
            if isinstance(head, dict) and head.get("ERROR"):
                last_head = head
                # Observed intermittently with a HAR-imported session even when the next identical
                # request succeeds. Retry a couple of times, but still fail if truly expired.
                if head.get("CODE") == "S0002" and attempt < retries:
                    time.sleep(0.35 * (attempt + 1))
                    continue
                raise FlowApiError(f"Flow error from {endpoint}: {head}")
            return data
        raise FlowApiError(f"Flow error from {endpoint}: {last_head}")

    def _auth_payload(self, **extra: Any) -> dict[str, Any]:
        s = self.session
        payload = {"USER_ID": s.user_id, "RGSN_DTTM": s.rgsn_dttm}
        payload.update(extra)
        return payload

    def login(self, user_id: str, password: str) -> dict[str, Any]:
        """Log in with Flow ID/password and persist USER_ID/RGSN_DTTM.

        This follows the current Flow web login flow:
        1. Call FLOW_CUR_TIME_R001 to get CUR_DTTM and optional RSA KEY.
        2. If no RSA KEY is returned, AES-encrypt the password with
           "aes256-global-flow" + CUR_DTTM and send ENCRYPT_YN='YC'.

        If Flow changes its frontend encryption again, this method can fail and should be
        rechecked against the current signin JavaScript.
        """
        cookie_domain = urllib.parse.urlparse(self.base_url).hostname or "flow.team"
        device = _flow_device_json()
        self.http.cookies.set("googleLoginYn", "N", domain=cookie_domain, path="/")
        self.http.cookies.set("FLOW_DUID", device["DUID"], domain=cookie_domain, path="/")

        time_data = self._post(
            "/FLOW_CUR_TIME_R001.jct",
            {"USER_ID": user_id},
            referer_path="/signin.act",
            retries=0,
        )
        cur_dttm = str(time_data.get("CUR_DTTM") or "")
        self.http.cookies.set("DATE_TIME", cur_dttm, domain=cookie_domain, path="/")
        public_key = str(time_data.get("KEY") or "")
        if public_key:
            raise FlowApiError("Flow returned an RSA login key; RSA password encryption is not implemented yet.")

        encrypted_password = _flow_password_encrypt(password, cur_dttm)
        payload = {
            "USER_ID": user_id,
            "RGSN_DTTM": "",
            **device,
            "PWD": encrypted_password,
            "ID_GB": "1",
            "ENCRYPT_YN": "YC",
            "OBJ_CNTS_NM": "",
            "SUB_DOM": "",
            "CMPN_CD": "",
            "OTP_TYPE": "",
            "packetOption": 1,
            "CP_CODE": "",
            "AUTH_TYPE": "",
        }
        data = self._post("/COLABO2_LOGIN_R003.jct", payload, referer_path="/signin.act", retries=0)
        result_code = str(data.get("RSLT_CD") or data.get("ERR_CD") or "")
        error_message = data.get("ERR_MSG") or data.get("COMMON_HEAD", {}).get("MESSAGE")
        if result_code and result_code not in {"0000", "0"}:
            raise FlowApiError(f"Flow login failed: code={result_code}, message={error_message or ''}")
        new_user = data.get("USER_ID") or data.get("user_id") or data.get("EML") or user_id
        token = data.get("RGSN_DTTM") or data.get("TOKEN") or data.get("SESSION_KEY")
        if not token:
            raise FlowApiError(f"Flow login succeeded but no session token was found in response keys: {sorted(data.keys())}")
        self.user_id = str(new_user)
        self.rgsn_dttm = str(token)
        # save_session() uses self.session, which captures the JSESSIONID/AWSALB cookies
        # the server just issued — those are required for subsequent API calls.
        saved = self.save_session()
        return {"ok": True, "session": saved["session"], "raw_keys": sorted(data.keys())}

    def list_projects(
        self,
        page: int = 1,
        per_page: int = 50,
        mode: str = "",
        folder_srno: str | None = "9",
        folder_kind: str = "1",
        sort_desc: str = "0",
    ) -> dict[str, Any]:
        payload = self._auth_payload(
            PG_NO=page,
            PG_PER_CNT=per_page,
            NEXT_YN="Y",
            COLABO_FLD_KIND=folder_kind,
            COLABO_FLD_SRNO=folder_srno,
            MODE=mode,
            MNGR_YN="N",
            SORT_DESC=sort_desc,
            packetOption=2,
            FOLDER_SRNO=None,
        )
        path = "/ACT_PROJECT_LIST.jct" + ("?mode=RECENT" if mode == "RECENT" else "")
        return self._post(path, payload)

    def list_projects_simple(self, page: int = 1, per_page: int = 50) -> dict[str, Any]:
        data = self.list_projects(page=page, per_page=per_page)
        records = data.get("PROJECT_RECORD") or []
        return {
            "next": data.get("NEXT_YN"),
            "count": len(records),
            "projects": [
                {
                    "colabo_srno": r.get("COLABO_SRNO"),
                    "title": r.get("TTL"),
                    "badge_count": r.get("BADGE_CNT"),
                    "important": r.get("IMPT_YN"),
                    "home_tab": r.get("HOME_TAB_CODE"),
                }
                for r in records
            ],
        }

    def get_project_info(self, colabo_srno: str) -> dict[str, Any]:
        return self._post("/ACT_PROJECT_INFO.jct", self._auth_payload(COLABO_SRNO=str(colabo_srno)), referer_path="/main.act?detail")

    def list_project_posts(self, colabo_srno: str, page: int = 1, per_page: int = 20) -> dict[str, Any]:
        payload = self._auth_payload(
            PG_NO=page,
            PG_PER_CNT=per_page,
            PREV_YN="Y",
            NEXT_YN="Y",
            COLABO_SRNO=str(colabo_srno),
            RENEWAL_YN="Y",
            MORE_BUTTON=False,
            SEARCH_COMMT_SRNO="",
            SRCH_COLABO_REMARK_SRNO="",
            ORDER_TYPE="N",
            GUBUN="",
            TAG_NM="",
            TMPL_TYPE="",
        )
        return self._post("/COLABO2_R104.jct", payload, referer_path="/main.act?detail")

    def get_post_detail(
        self,
        colabo_srno: str,
        colabo_commt_srno: str,
        remark_per_page: int = 999,
        remark_anchor_srno: str = "-1",
    ) -> dict[str, Any]:
        """Fetch a single post (or subtask) with body and preview remarks.

        Uses /COLABO2_R104.jct?mode=DETAIL. Returns COMMT_REC[0] with the body (CNTN)
        and REMARK_REC (preview only — typically the newest ~2). To collect all remarks
        when REMARK_CNT > REMARK_REC.length, follow up with list_post_remarks() using
        the oldest received remark srno as anchor.
        """
        payload = self._auth_payload(
            GUBUN="DETAIL",
            COLABO_SRNO=str(colabo_srno),
            COLABO_COMMT_SRNO=str(colabo_commt_srno),
            COLABO_REMARK_SRNO=str(remark_anchor_srno),
            RENEWAL_YN="Y",
            PG_NO=1,
            PG_PER_CNT=int(remark_per_page),
            COPY_YN="N",
        )
        return self._post("/COLABO2_R104.jct?mode=DETAIL", payload, referer_path="/main.act?detail")

    def list_post_remarks(
        self,
        colabo_srno: str,
        colabo_commt_srno: str,
        anchor_srno: str = "-1",
        order_type: str = "P",
    ) -> dict[str, Any]:
        """Fetch one page of remarks for a post via /COLABO2_REMARK_R101.jct?mode=M.

        anchor_srno: the COLABO_REMARK_SRNO cursor (use the oldest already-seen srno
        to load older remarks). order_type 'P' loads earlier (past) remarks.
        Response contains COLABO_REMARK_REC and PREV_YN/NEXT_YN flags.
        """
        payload = self._auth_payload(
            MODE="M",
            ORDER_TYPE=order_type,
            COLABO_SRNO=str(colabo_srno),
            COLABO_COMMT_SRNO=str(colabo_commt_srno),
            SRCH_COLABO_REMARK_SRNO=str(anchor_srno),
            REPEAT_DTTM="",
            REMARK_FILTER="",
            packetOption=1,
        )
        return self._post("/COLABO2_REMARK_R101.jct?mode=M", payload, referer_path="/main.act?detail")

    def extract_post(
        self,
        colabo_srno: str,
        colabo_commt_srno: str,
        max_remark_pages: int = 20,
    ) -> dict[str, Any]:
        """Slim wrapper around get_post_full — returns only body + flattened comments.

        Output is ~1KB per typical subtask vs ~30KB raw, which matters when iterating
        over many subtasks. Body and comment text fall back to CNTN when REMARK_CNTN
        is missing.
        """
        full = self.get_post_full(colabo_srno, colabo_commt_srno, max_remark_pages=max_remark_pages)
        post = full.get("post") or {}
        comments = []
        for r in full.get("remarks") or []:
            comments.append({
                "srno": r.get("COLABO_REMARK_SRNO"),
                "author": r.get("RGSR_NM"),
                "author_id": r.get("RGSR_ID"),
                "registered_at": r.get("RGSN_DTTM"),
                "text": r.get("REMARK_CNTN") or r.get("CNTN"),
                "is_system": (r.get("SYSTEM_REMARK_YN") == "Y"),
                "img_count": len(r.get("IMG_ATCH_REC") or []) + len(r.get("REMARK_IMG_ATCH_REC") or []),
                "atch_count": len(r.get("ATCH_REC") or []) + len(r.get("REMARK_ATCH_REC") or []),
            })
        return {
            "colabo_srno": str(colabo_srno),
            "post_srno": str(colabo_commt_srno),
            "title": post.get("COMMT_TTL"),
            "content": post.get("CNTN") or "",
            "remark_expected": full.get("expected_remark_cnt"),
            "remark_fetched": full.get("fetched_remark_cnt"),
            "comments": comments,
        }

    def get_post_full(
        self,
        colabo_srno: str,
        colabo_commt_srno: str,
        max_remark_pages: int = 20,
    ) -> dict[str, Any]:
        """Fetch a post with body + ALL remarks via DETAIL + REMARK_R101 pagination.

        Strategy:
        1. Call get_post_detail to grab the body and the preview remarks (REMARK_REC).
        2. If ONLY_REMARK_CNT > 0, walk backward via list_post_remarks using the oldest
           received srno as anchor, until PREV_YN != 'Y' or max_remark_pages hit.
        3. Return a flat dict with `post` (the COMMT_REC entry, less REMARK_REC) and
           `remarks` (merged + de-duplicated, sorted by RGSN_DTTM ascending).
        """
        detail = self.get_post_detail(colabo_srno, colabo_commt_srno)
        commt = (detail.get("COMMT_REC") or [{}])[0]
        preview = list(commt.get("REMARK_REC") or [])
        only_remark_cnt = int(str(commt.get("ONLY_REMARK_CNT") or "0") or "0")

        all_remarks: dict[str, dict[str, Any]] = {r.get("COLABO_REMARK_SRNO"): r for r in preview if r.get("COLABO_REMARK_SRNO")}

        if only_remark_cnt > 0 and preview:
            anchor = min((r.get("COLABO_REMARK_SRNO") for r in preview if r.get("COLABO_REMARK_SRNO")), default=None)
            for _ in range(max_remark_pages):
                if not anchor:
                    break
                page = self.list_post_remarks(colabo_srno, colabo_commt_srno, anchor_srno=anchor, order_type="P")
                rec = page.get("COLABO_REMARK_REC") or []
                new_any = False
                for r in rec:
                    srno = r.get("COLABO_REMARK_SRNO")
                    if srno and srno not in all_remarks:
                        all_remarks[srno] = r
                        new_any = True
                if not new_any or (page.get("PREV_YN") or "").upper() != "Y":
                    break
                anchor = min((r.get("COLABO_REMARK_SRNO") for r in rec if r.get("COLABO_REMARK_SRNO")), default=None)

        sorted_remarks = sorted(all_remarks.values(), key=lambda r: (r.get("RGSN_DTTM") or ""))
        post_meta = {k: v for k, v in commt.items() if k != "REMARK_REC"}
        return {
            "colabo_srno": str(colabo_srno),
            "colabo_commt_srno": str(colabo_commt_srno),
            "expected_remark_cnt": int(str(commt.get("REMARK_CNT") or "0") or "0"),
            "fetched_remark_cnt": len(sorted_remarks),
            "post": post_meta,
            "remarks": sorted_remarks,
        }

    def list_project_schedules(
        self,
        colabo_srno: str,
        first_dt: str,
        last_dt: str,
        project_schd_filter: str = "0,1",
        task_schd_filter: str = "",
    ) -> dict[str, Any]:
        payload = self._auth_payload(
            FIRST_DT=first_dt,
            LAST_DT=last_dt,
            PROJECT_SCHD_FILTER=project_schd_filter,
            TASK_SCHD_FILTER=task_schd_filter,
            COLABO_SRNO=str(colabo_srno),
        )
        return self._post("/COLABO2_SCHD_R005.jct", payload, referer_path="/main.act?prjSchd")

    def find_project_by_title(self, title: str, max_pages: int = 5) -> Optional[dict[str, Any]]:
        for page in range(1, max_pages + 1):
            data = self.list_projects(page=page, per_page=50)
            for rec in data.get("PROJECT_RECORD") or []:
                if rec.get("TTL") == title:
                    return rec
            if data.get("NEXT_YN") != "Y":
                break
        return None

    def list_today_schedules(self, colabo_srno: str | None = None, project_title: str | None = None) -> dict[str, Any]:
        if not colabo_srno:
            project_title = project_title or DEFAULT_SCHEDULE_PROJECT_TITLE
            project = self.find_project_by_title(project_title)
            if not project:
                raise FlowApiError(f"Project not found by title: {project_title}")
            colabo_srno = str(project["COLABO_SRNO"])
        today = date.today().strftime("%Y%m%d")
        data = self.list_project_schedules(colabo_srno=colabo_srno, first_dt=today, last_dt=today)
        schedules = data.get("SCHD_REC") or []
        return {
            "date": today,
            "colabo_srno": colabo_srno,
            "count": len(schedules),
            "schedules": [
                {
                    "title": s.get("TTL"),
                    "start": s.get("STTG_DTTM"),
                    "finish": s.get("FNSH_DTTM"),
                    "all_day": s.get("ALL_DAY_YN"),
                    "place": s.get("PLACE") or s.get("LOCATION"),
                    "memo": s.get("MEMO") or s.get("CONV_MEMO"),
                    "colabo_commt_srno": s.get("COLABO_COMMT_SRNO"),
                }
                for s in schedules
            ],
        }
