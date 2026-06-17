# 2026-06-17 — 세션 쿠키 영속화로 S0002 완전 해결

## 요약

모든 Flow API 호출이 유효한 토큰으로도 `S0002 "로그인 세션이 만료되었습니다"` 로 거부되던 문제 해결. 진짜 원인은 토큰 인코딩이 아니라 **JSESSIONID 등 서버 발급 쿠키 미저장**이었음. `_JSON_` 이중 인코딩 수정(이전 작업)은 유효했으나 단독으로는 불충분.

## 원인

이전 분석은 "인증은 `_JSON_` 바디의 `USER_ID + RGSN_DTTM` 만으로 이뤄짐, 쿠키 없음"이라고 결론냈는데 이는 부정확. 실측 결과:

- 첫 요청 시 서버가 `Set-Cookie: JSESSIONID=...; AWSALB=...; AWSALBCORS=...; AWSALBTG=...; AWSALBTGCORS=...; SCOUTER=...` 발급.
- 새 FlowClient 인스턴스는 매번 쿠키 없이 시작 → 서버가 새 JSESSIONID 발급 → 그 세션은 어떤 사용자와도 매핑돼 있지 않음 → S0002.
- 같은 인스턴스로 `login()` 직후 `list_projects` 호출은 성공 (쿠키 유지됨).

즉 Flow 인증 모델은 `JSESSIONID(서버 세션) + RGSN_DTTM(사용자 토큰)` 조합이며 둘 다 필요.

## 변경 사항 (`flow_mcp/client.py`)

### 1. `FlowSession` 에 `cookies` 필드 추가

```python
@dataclass
class FlowSession:
    user_id: str
    rgsn_dttm: str
    cookies: dict[str, str] = field(default_factory=dict)
```

`redacted()` 는 쿠키 이름 목록만 노출 (값은 미노출).

### 2. `extract_session_from_har` — HAR에서 쿠키도 추출

HAR 엔트리의 `request.cookies` 배열에서 JSESSIONID 등을 함께 수집. 마지막으로 인증된 엔트리 사용 (쿠키가 회전될 수 있어 최신 우선).

### 3. `save_session` / `load_session` — 디스크에 쿠키 영속화

`~/.flow-mcp/session.json` 스키마 확장:

```jsonc
{
  "user_id": "...",
  "rgsn_dttm": "FLOW_...",
  "cookies": {
    "JSESSIONID": "...",
    "AWSALB": "...",
    "AWSALBCORS": "...",
    "AWSALBTG": "...",
    "AWSALBTGCORS": "...",
    "SCOUTER": "...",
    "FLOW_DUID": "...",
    "DATE_TIME": "...",
    "googleLoginYn": "N"
  }
}
```

기존 토큰 전용 파일도 호환 (`cookies` 키 없으면 빈 dict).

### 4. `FlowClient.__init__` — 순서 재배치 + 쿠키 적용

`httpx.Client` 생성을 `load_session` 호출보다 앞으로 옮기고, 로드된 쿠키를 `self.http.cookies` 에 주입.

```python
self.http = httpx.Client(...)
if not (self.user_id and self.rgsn_dttm):
    loaded = self.load_session(required=False)
    if loaded and loaded.cookies:
        self._apply_cookies(loaded.cookies)
```

새 헬퍼 두 개:
- `_apply_cookies(cookies)` — 도메인/path 지정해 http 클라이언트에 set.
- `_current_cookies()` — `self.http.cookies.jar` → dict.

### 5. `login()` — 토큰 + 쿠키 동시 저장

```python
self.user_id = str(new_user)
self.rgsn_dttm = str(token)
saved = self.save_session()  # session 프로퍼티가 현재 http.cookies 캡처
```

`session` 프로퍼티가 호출 시점의 쿠키를 항상 캡처하도록 변경.

### 6. 클래스 docstring 수정

"Auth ... not cookies" → 쿠키 필요성과 그 결과(누락 시 S0002) 명시.

## 검증

- `uv run pytest` — 3/3 통과.
- `uv run flow-mcp-setup login` (실 비밀번호) → 토큰 + 9개 쿠키 저장 확인.
- `uv run flow-mcp-setup smoke-test --per-page 3` → 실제 프로젝트 3개 반환 (`일정 공유`, `업무요청`, `개발본부`). S0002 사라짐.
- 회귀 테스트 스크립트 `scripts/probe_jsessionid.py` — 동일 인스턴스 vs fresh 인스턴스 비교, 둘 다 성공.

## 남은 고려 사항

- **AWSALB 쿠키 staleness**: 매 요청마다 서버가 회전시키는데 디스크 저장은 login/import-har 시점에만 발생. JSESSIONID TTL 안에서는 문제 없으나, 장기 운용 중 간헐적 S0002가 다시 보이면 매 성공 응답 후 `save_session()` 호출로 갱신하는 로직 검토.
- **`set_session` MCP tool**: 현재 토큰만 받고 쿠키는 못 받음. 이 경로로 직접 토큰을 주입한 경우 첫 호출에서 S0002 가능. 우회는 `login` 또는 `import_session_from_har` 사용. 필요 시 `cookies` 인자 추가 검토.
- `flow_mcp_session_fix.md` (이전 핸드오프 문서)는 인코딩 부분은 맞고 인증 모델 부분(쿠키 없음)은 틀린 정보. 본 패치 노트를 정본으로 보면 됨.

## 변경 통계

`flow_mcp/client.py` — +44 / −10 (대략).
