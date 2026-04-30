from __future__ import annotations

import base64
import json
import os
import re
import secrets
import time
import urllib.parse
from dataclasses import dataclass
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

    def redacted(self) -> dict[str, str]:
        return {
            "user_id": _redact(self.user_id),
            "rgsn_dttm": _redact(self.rgsn_dttm),
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
    for entry in entries:
        payload = _parse_post_json_from_har_entry(entry)
        if not payload:
            continue
        user_id = payload.get("USER_ID")
        rgsn_dttm = payload.get("RGSN_DTTM")
        if user_id and rgsn_dttm and str(rgsn_dttm).startswith("FLOW_"):
            return FlowSession(user_id=str(user_id), rgsn_dttm=str(rgsn_dttm))
    raise FlowApiError("No authenticated USER_ID/RGSN_DTTM pair found in HAR")


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

    Auth for normal API calls appears to be USER_ID + RGSN_DTTM token in the JSON body,
    not cookies. That token is sensitive and should be treated like a session credential.
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
        if not (self.user_id and self.rgsn_dttm):
            self.load_session(required=False)
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

    @property
    def session(self) -> FlowSession:
        if not self.user_id or not self.rgsn_dttm:
            raise FlowApiError("Flow session is not configured. Use flow_import_session_from_har or set FLOW_USER_ID/FLOW_RGSN_DTTM.")
        return FlowSession(self.user_id, self.rgsn_dttm)

    def save_session(self, session: FlowSession | None = None) -> dict[str, Any]:
        session = session or self.session
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        self.session_path.write_text(json.dumps(session.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            self.session_path.chmod(0o600)
        except OSError:
            pass
        self.user_id = session.user_id
        self.rgsn_dttm = session.rgsn_dttm
        return {"ok": True, "path": str(self.session_path), "session": session.redacted()}

    def load_session(self, required: bool = True) -> Optional[FlowSession]:
        if self.session_path.exists():
            data = json.loads(self.session_path.read_text(encoding="utf-8"))
            self.user_id = data["user_id"]
            self.rgsn_dttm = data["rgsn_dttm"]
            return FlowSession(self.user_id, self.rgsn_dttm)
        if required:
            raise FlowApiError(f"Session file not found: {self.session_path}")
        return None

    def import_session_from_har(self, har_path: str | Path) -> dict[str, Any]:
        session = extract_session_from_har(har_path)
        return self.save_session(session)

    def set_session(self, user_id: str, rgsn_dttm: str) -> dict[str, Any]:
        return self.save_session(FlowSession(user_id=user_id, rgsn_dttm=rgsn_dttm))

    def _post(self, endpoint: str, payload: dict[str, Any], *, referer_path: str = "/main.act", retries: int = 2) -> dict[str, Any]:
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        body = urllib.parse.urlencode({"_JSON_": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))})
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
        saved = self.save_session(FlowSession(str(new_user), str(token)))
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
