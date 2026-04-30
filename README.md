# flow-mcp

비공식 Flow.team 웹 API MCP 서버입니다.

이 프로젝트는 본인 또는 조직 내부에서 접근 권한이 있는 Flow 계정/워크스페이스를 자동화하기 위한 도구입니다. 저장소에는 개인 인증정보, HAR 파일, 쿠키, 세션 토큰이 포함되지 않습니다.

English documentation is available below: [English](#english)

## 한국어

### 안전 및 개인정보

- HAR 파일을 커밋하지 마세요.
- `.env`를 커밋하지 마세요.
- `session.json`을 커밋하지 마세요.
- `FLOW_RGSN_DTTM`은 세션 인증정보로 취급하세요.
- 본인 또는 조직에서 접근 권한이 있는 계정/워크스페이스에서만 사용하세요.
- 이 래퍼는 Flow 웹앱이 호출하는 동일한 웹 endpoint를 호출합니다. 공식 Flow API 클라이언트가 아닙니다.
- CAPTCHA, 2FA, SSO, 접근제어, rate limit을 우회하기 위한 용도로 사용하지 마세요.

### 확인된 API 형태

현재 확인된 Flow 웹 요청은 다음 형태입니다.

```text
POST https://flow.team/<ENDPOINT>.jct
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
Body: _JSON_=<urlencoded JSON payload>
```

인증이 필요한 요청은 JSON payload 안에 다음 필드를 포함합니다.

```json
{
  "USER_ID": "...",
  "RGSN_DTTM": "FLOW_..."
}
```

구현된 endpoint:

- `POST /FLOW_CUR_TIME_R001.jct` - 로그인 전 현재 시간/암호화 seed 조회
- `POST /COLABO2_LOGIN_R003.jct` - ID/password 로그인
- `POST /ACT_PROJECT_LIST.jct` - 프로젝트 목록
- `POST /ACT_PROJECT_INFO.jct` - 프로젝트 정보/설정
- `POST /COLABO2_R104.jct` - 프로젝트 피드/게시글
- `POST /COLABO2_SCHD_R005.jct` - 프로젝트 일정

ID/password 로그인은 현재 Flow 웹 클라이언트 동작을 따릅니다.

1. `POST /FLOW_CUR_TIME_R001.jct`에서 `CUR_DTTM`을 가져옵니다.
2. 비밀번호를 `aes256-global-flow + CUR_DTTM` 키로 AES-256-CBC 암호화합니다.
3. `POST /COLABO2_LOGIN_R003.jct`에 암호화된 비밀번호와 `ENCRYPT_YN='YC'`를 전송합니다.

Flow가 `FLOW_CUR_TIME_R001`에서 RSA `KEY`를 반환하는 로그인 경로로 바뀌면, 현재 클라이언트는 우회하지 않고 명확히 실패합니다. 2FA, CAPTCHA, SSO 전용 계정도 자동 로그인이 실패할 수 있습니다.

### 요구사항

- Python 3.10+
- uv
- git

### 팀원용 원샷 설치

```bash
curl -fsSL https://raw.githubusercontent.com/Allra-Fintech/flow-mcp/main/install.sh | bash
```

설치 스크립트가 수행하는 일:

1. `uv`가 없으면 설치합니다.
2. 이 프로젝트를 `~/.flow-mcp/app` 아래에 clone/update합니다.
3. 의존성을 설치합니다.
4. Flow ID/password 입력을 요청합니다.
5. 비밀번호는 저장하지 않고, 로그인 결과 세션만 `~/.flow-mcp/session.json`에 저장합니다.
6. 기본적으로 `~/.hermes/config.yaml`에 MCP 서버 설정을 추가/갱신합니다.

옵션:

```bash
# 로그인 프롬프트 없이 설치만
FLOW_MCP_LOGIN=0 curl -fsSL https://raw.githubusercontent.com/Allra-Fintech/flow-mcp/main/install.sh | bash

# Hermes config 자동 등록 없이 설치
FLOW_MCP_CONFIGURE_HERMES=0 curl -fsSL https://raw.githubusercontent.com/Allra-Fintech/flow-mcp/main/install.sh | bash

# 설치 위치 변경
FLOW_MCP_INSTALL_DIR="$HOME/dev/flow-mcp" curl -fsSL https://raw.githubusercontent.com/Allra-Fintech/flow-mcp/main/install.sh | bash

# MCP 서버 이름 변경
FLOW_MCP_SERVER_NAME=flow-team curl -fsSL https://raw.githubusercontent.com/Allra-Fintech/flow-mcp/main/install.sh | bash
```

### 체크아웃에서 설치

```bash
git clone git@github.com:Allra-Fintech/flow-mcp.git
cd flow-mcp
uv sync
```

체크아웃에서 대화형 설정:

```bash
uv run flow-mcp-setup setup --login --configure-hermes
```

### Flow ID/password 로그인

```bash
cd flow-mcp
uv run flow-mcp-setup login
uv run flow-mcp-setup smoke-test
```

기본 세션 저장 위치:

```text
~/.flow-mcp/session.json
```

이 파일은 민감정보이므로 공유하거나 커밋하지 마세요.

세션 저장 위치를 바꾸려면:

```bash
export FLOW_SESSION_PATH="$HOME/.flow-mcp/session.json"
```

### 선택 fallback: 본인 HAR에서 세션 생성

ID/password 자동 로그인이 SSO/2FA/CAPTCHA 등으로 실패할 때만 사용하는 fallback입니다.

1. Chrome에서 Flow를 엽니다.
2. DevTools > Network를 엽니다.
3. `Preserve log`를 체크합니다.
4. Flow에 로그인합니다.
5. 프로젝트 목록 또는 일정 페이지를 엽니다.
6. Network log를 HAR로 export합니다.
7. HAR 파일은 저장소 밖에 보관합니다. 예: `~/Downloads/flow.team.har`
8. 세션을 import합니다.

```bash
cd flow-mcp
uv run python - <<'PY'
from flow_mcp.client import FlowClient
print(FlowClient().import_session_from_har('~/Downloads/flow.team.har'))
PY
```

### 환경변수로 직접 설정

세션 파일 대신 환경변수를 사용할 수도 있습니다.

```bash
export FLOW_USER_ID="your-flow-user-id"
export FLOW_RGSN_DTTM="FLOW_..."
export FLOW_BASE_URL="https://flow.team"
```

특정 프로젝트명을 기본 일정 프로젝트로 사용하려면:

```bash
export FLOW_DEFAULT_SCHEDULE_PROJECT_TITLE="일정 공유"
```

### 빠른 smoke test

```bash
cd flow-mcp
uv run python - <<'PY'
from flow_mcp.client import FlowClient
c = FlowClient()
print(c.list_projects_simple(per_page=3))
PY
```

### MCP 서버 실행

```bash
cd flow-mcp
uv run flow-mcp
```

### MCP tools

- `flow_import_session_from_har(har_path)`
- `flow_set_session(user_id, rgsn_dttm)`
- `flow_login(user_id, password)`
- `flow_list_projects(page=1, per_page=50)`
- `flow_list_projects_raw(page=1, per_page=50, mode='')`
- `flow_get_project_info(colabo_srno)`
- `flow_list_project_posts(colabo_srno, page=1, per_page=20)`
- `flow_list_project_schedules(colabo_srno, first_dt, last_dt)`
- `flow_list_today_schedules(colabo_srno=None, project_title=None)`

날짜는 `YYYYMMDD` 문자열입니다. `flow_list_today_schedules`에서 `project_title`을 생략하면 서버는 `FLOW_DEFAULT_SCHEDULE_PROJECT_TITLE`을 사용합니다.

### Hermes Agent 설정 예시

`~/.hermes/config.yaml`에 다음처럼 추가합니다. 경로는 본인 설치 위치에 맞게 조정하세요.

```yaml
mcp_servers:
  flow:
    command: "uv"
    args: ["--directory", "/absolute/path/to/flow-mcp", "run", "flow-mcp"]
    timeout: 120
    connect_timeout: 60
```

그 다음 Hermes Agent를 재시작하세요.

예상 tool 이름은 MCP 서버명 prefix가 붙습니다.

- `mcp_flow_flow_list_projects`
- `mcp_flow_flow_get_project_info`
- `mcp_flow_flow_list_project_schedules`
- `mcp_flow_flow_list_today_schedules`

### 개발

문법 체크:

```bash
uv run python -m compileall flow_mcp
```

테스트:

```bash
uv run pytest
```

로컬 import 확인:

```bash
uv run python -c 'import flow_mcp, flow_mcp.server; print(flow_mcp.__version__)'
```

### 향후 작업

- RSA `KEY` 기반 로그인 경로가 실제로 필요해지면 구현
- sanitizer fixture를 더 늘려 endpoint별 테스트 강화
- 프로젝트 목록/피드 endpoint pagination helper 확장
- 일정/게시글 응답 정규화 모델 추가
- 팀별 SSO/2FA 정책에 맞는 안전한 대체 로그인 흐름 검토

---

## English

Unofficial MCP server for Flow.team web APIs.

This project is intended for internal/personal automation using your own authorized Flow account session. It does not contain personal credentials, HAR files, cookies, or session tokens.

### Safety and privacy

- Do not commit HAR files.
- Do not commit `.env`.
- Do not commit `session.json`.
- Treat `FLOW_RGSN_DTTM` as a session credential.
- Use this only with accounts and workspaces you are authorized to access.
- This wrapper calls the same web endpoints the Flow web app calls; it is not an official Flow API client.
- Do not use this to bypass CAPTCHA, 2FA, SSO, access controls, or rate limits.

### Observed API shape

Flow web requests observed so far use:

```text
POST https://flow.team/<ENDPOINT>.jct
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
Body: _JSON_=<urlencoded JSON payload>
```

Authenticated requests include these fields inside the JSON payload:

```json
{
  "USER_ID": "...",
  "RGSN_DTTM": "FLOW_..."
}
```

Known endpoints implemented here:

- `POST /FLOW_CUR_TIME_R001.jct` - login preflight/current time seed
- `POST /COLABO2_LOGIN_R003.jct` - ID/password login
- `POST /ACT_PROJECT_LIST.jct` - project list
- `POST /ACT_PROJECT_INFO.jct` - project metadata/settings
- `POST /COLABO2_R104.jct` - project feed/posts
- `POST /COLABO2_SCHD_R005.jct` - project schedules

Password login follows the current Flow web client behavior:

1. `POST /FLOW_CUR_TIME_R001.jct` returns `CUR_DTTM`.
2. The password is AES-256-CBC encrypted with key `aes256-global-flow + CUR_DTTM`.
3. `POST /COLABO2_LOGIN_R003.jct` sends the encrypted password with `ENCRYPT_YN='YC'`.

If Flow starts returning an RSA `KEY` from `FLOW_CUR_TIME_R001`, this client will fail fast because the RSA path is not implemented yet. 2FA, CAPTCHA, or SSO-only accounts can also cause automatic login to fail.

### Requirements

- Python 3.10+
- uv
- git

### One-shot install for teammates

```bash
curl -fsSL https://raw.githubusercontent.com/Allra-Fintech/flow-mcp/main/install.sh | bash
```

The installer will:

1. install `uv` if missing,
2. clone/update this project under `~/.flow-mcp/app`,
3. install dependencies,
4. prompt for Flow ID/password,
5. save only the resulting Flow session token under `~/.flow-mcp/session.json`,
6. upsert the MCP server config into `~/.hermes/config.yaml` by default.

Options:

```bash
FLOW_MCP_LOGIN=0 curl -fsSL https://raw.githubusercontent.com/Allra-Fintech/flow-mcp/main/install.sh | bash
FLOW_MCP_CONFIGURE_HERMES=0 curl -fsSL https://raw.githubusercontent.com/Allra-Fintech/flow-mcp/main/install.sh | bash
FLOW_MCP_INSTALL_DIR="$HOME/dev/flow-mcp" curl -fsSL https://raw.githubusercontent.com/Allra-Fintech/flow-mcp/main/install.sh | bash
FLOW_MCP_SERVER_NAME=flow-team curl -fsSL https://raw.githubusercontent.com/Allra-Fintech/flow-mcp/main/install.sh | bash
```

### Install from a checkout

```bash
git clone git@github.com:Allra-Fintech/flow-mcp.git
cd flow-mcp
uv sync
```

Interactive setup from a checkout:

```bash
uv run flow-mcp-setup setup --login --configure-hermes
```

### Login with Flow ID/password

```bash
cd flow-mcp
uv run flow-mcp-setup login
uv run flow-mcp-setup smoke-test
```

By default, the session is saved to:

```text
~/.flow-mcp/session.json
```

That file is sensitive and should not be shared.

You can override the session path:

```bash
export FLOW_SESSION_PATH="$HOME/.flow-mcp/session.json"
```

### Optional fallback: create a session from your own HAR

Use this only when ID/password login fails because of SSO, 2FA, CAPTCHA, or similar account policy.

1. Open Flow in Chrome.
2. Open DevTools > Network.
3. Check `Preserve log`.
4. Log in to Flow.
5. Open the project list or schedule page.
6. Export the Network log as HAR.
7. Store it outside the repo, for example `~/Downloads/flow.team.har`.
8. Import session:

```bash
cd flow-mcp
uv run python - <<'PY'
from flow_mcp.client import FlowClient
print(FlowClient().import_session_from_har('~/Downloads/flow.team.har'))
PY
```

### Alternative: environment variables

Instead of using a session file, set:

```bash
export FLOW_USER_ID="your-flow-user-id"
export FLOW_RGSN_DTTM="FLOW_..."
export FLOW_BASE_URL="https://flow.team"
```

Set a default project title for today's schedules:

```bash
export FLOW_DEFAULT_SCHEDULE_PROJECT_TITLE="일정 공유"
```

### Quick smoke test

```bash
cd flow-mcp
uv run python - <<'PY'
from flow_mcp.client import FlowClient
c = FlowClient()
print(c.list_projects_simple(per_page=3))
PY
```

### Run MCP server

```bash
cd flow-mcp
uv run flow-mcp
```

### MCP tools

- `flow_import_session_from_har(har_path)`
- `flow_set_session(user_id, rgsn_dttm)`
- `flow_login(user_id, password)`
- `flow_list_projects(page=1, per_page=50)`
- `flow_list_projects_raw(page=1, per_page=50, mode='')`
- `flow_get_project_info(colabo_srno)`
- `flow_list_project_posts(colabo_srno, page=1, per_page=20)`
- `flow_list_project_schedules(colabo_srno, first_dt, last_dt)`
- `flow_list_today_schedules(colabo_srno=None, project_title=None)`

Dates are `YYYYMMDD` strings. If `project_title` is omitted for today's schedules, the server uses `FLOW_DEFAULT_SCHEDULE_PROJECT_TITLE`.

### Hermes Agent config example

Add this to `~/.hermes/config.yaml`, adjusting the path for your checkout:

```yaml
mcp_servers:
  flow:
    command: "uv"
    args: ["--directory", "/absolute/path/to/flow-mcp", "run", "flow-mcp"]
    timeout: 120
    connect_timeout: 60
```

Then restart Hermes Agent.

Expected tool names will be prefixed by the MCP server name, for example:

- `mcp_flow_flow_list_projects`
- `mcp_flow_flow_get_project_info`
- `mcp_flow_flow_list_project_schedules`
- `mcp_flow_flow_list_today_schedules`

### Development

Run syntax check:

```bash
uv run python -m compileall flow_mcp
```

Run tests:

```bash
uv run pytest
```

Run a local import check:

```bash
uv run python -c 'import flow_mcp, flow_mcp.server; print(flow_mcp.__version__)'
```

### Notes for future work

- Implement the RSA `KEY` login path if Flow starts requiring it.
- Add more sanitized fixture tests for each endpoint.
- Add pagination helpers for all project list/feed endpoints.
- Add response models or normalization for schedule/feed records.
- Review a safe alternative login flow for team SSO/2FA policies.
