# flow-mcp

Flow.team 웹 API를 MCP(Model Context Protocol) 서버로 감싼 비공식 내부 자동화 도구입니다.

본인 또는 조직에서 접근 권한이 있는 Flow 계정/워크스페이스에서만 사용하세요. 이 저장소에는 개인 인증정보, HAR 파일, 쿠키, 세션 토큰이 포함되지 않습니다.

## 주의사항

- 공식 Flow API 클라이언트가 아닙니다.
- Flow 웹앱이 호출하는 동일한 endpoint를 사용합니다.
- `.env`, `session.json`, `*.har`, 쿠키 파일을 커밋하지 마세요.
- `FLOW_RGSN_DTTM`과 `~/.flow-mcp/session.json`은 세션 인증정보입니다.
- CAPTCHA, 2FA, SSO, 접근제어, rate limit을 우회하기 위한 용도로 사용하지 마세요.

## 가능한 기능

현재 MCP tool로 제공하는 기능은 다음과 같습니다.

- Flow ID/password로 로그인하고 로컬 세션 저장
- HAR 파일에서 본인 세션 정보 import
- USER_ID/RGSN_DTTM 세션 직접 설정
- 프로젝트 목록 조회
- 프로젝트 원본 목록 조회
- 프로젝트 정보/설정 조회
- 프로젝트 게시글/피드 조회
- 프로젝트 일정 조회
- 오늘 일정 조회

MCP tool 목록:

- `flow_login(user_id, password)`
- `flow_import_session_from_har(har_path)`
- `flow_set_session(user_id, rgsn_dttm)`
- `flow_list_projects(page=1, per_page=50)`
- `flow_list_projects_raw(page=1, per_page=50, mode='')`
- `flow_get_project_info(colabo_srno)`
- `flow_list_project_posts(colabo_srno, page=1, per_page=20)`
- `flow_list_project_schedules(colabo_srno, first_dt, last_dt)`
- `flow_list_today_schedules(colabo_srno=None, project_title=None)`

날짜는 `YYYYMMDD` 문자열을 사용합니다.

`flow_list_today_schedules`에서 `project_title`을 생략하면 `FLOW_DEFAULT_SCHEDULE_PROJECT_TITLE` 환경변수 값을 사용합니다.

## 요구사항

- macOS/Linux
- Python 3.10+
- git
- uv

`install.sh`는 uv가 없으면 자동으로 설치를 시도합니다.

## 설치 방법 1: curl로 원샷 설치

팀원이 가장 쉽게 설치하는 방법입니다.

```bash
curl -fsSL https://raw.githubusercontent.com/Allra-Fintech/flow-mcp/main/install.sh | bash
```

설치 스크립트가 수행하는 일:

1. `uv`가 없으면 설치합니다.
2. 레포지토리를 `~/.flow-mcp/app` 아래에 clone/update합니다.
3. 의존성을 설치합니다.
4. Flow ID/password 입력을 요청합니다.
5. 비밀번호는 저장하지 않고, 로그인 결과 세션만 `~/.flow-mcp/session.json`에 저장합니다.
6. 기본적으로 Hermes Agent config에 MCP 서버 설정을 추가/갱신합니다.

옵션:

```bash
# 로그인 없이 설치만
FLOW_MCP_LOGIN=0 curl -fsSL https://raw.githubusercontent.com/Allra-Fintech/flow-mcp/main/install.sh | bash

# Hermes config 자동 등록 없이 설치
FLOW_MCP_CONFIGURE_HERMES=0 curl -fsSL https://raw.githubusercontent.com/Allra-Fintech/flow-mcp/main/install.sh | bash

# 설치 위치 변경
FLOW_MCP_INSTALL_DIR="$HOME/dev/flow-mcp" curl -fsSL https://raw.githubusercontent.com/Allra-Fintech/flow-mcp/main/install.sh | bash

# MCP 서버 이름 변경
FLOW_MCP_SERVER_NAME=flow-team curl -fsSL https://raw.githubusercontent.com/Allra-Fintech/flow-mcp/main/install.sh | bash
```

## 설치 방법 2: 레포지토리 clone 후 설치

```bash
git clone git@github.com:Allra-Fintech/flow-mcp.git
cd flow-mcp
uv sync
uv run flow-mcp-setup setup --login --configure-hermes
```

로그인만 다시 하고 싶을 때:

```bash
cd flow-mcp
uv run flow-mcp-setup login
```

설정 확인:

```bash
uv run flow-mcp-setup smoke-test
```

세션은 기본적으로 아래 파일에 저장됩니다.

```text
~/.flow-mcp/session.json
```

이 파일은 민감정보이므로 공유하거나 커밋하지 마세요.

## Claude Desktop에서 MCP로 사용하기

Claude Desktop에서 사용하려면 Claude Desktop 설정 파일에 flow MCP 서버를 직접 추가합니다.

설정 파일 위치:

```text
~/Library/Application Support/Claude/claude_desktop_config.json
```

`mcpServers` 아래에 아래 설정을 붙여넣으세요.

주의: JSON 파일이므로 실제 설정에는 Python 표현식인 `str(Path.home() / ...)`를 그대로 넣을 수 없습니다. 아래 예시는 이미 실제 문자열 경로로 적어둔 Claude Desktop용 JSON입니다.

```json
{
  "flow": {
    "command": "/Users/gnoyes/.local/bin/uv",
    "args": [
      "--directory",
      "/Users/gnoyes/allra/flow-mcp",
      "run",
      "flow-mcp"
    ],
    "env": {
      "FLOW_SESSION_PATH": "/Users/gnoyes/.flow-mcp/session.json",
      "FLOW_DEFAULT_SCHEDULE_PROJECT_TITLE": "일정 공유"
    }
  }
}
```

기존 설정 파일에 `mcpServers`가 없다면 전체 파일은 다음처럼 만들면 됩니다.

```json
{
  "mcpServers": {
    "flow": {
      "command": "/Users/gnoyes/.local/bin/uv",
      "args": [
        "--directory",
        "/Users/gnoyes/allra/flow-mcp",
        "run",
        "flow-mcp"
      ],
      "env": {
        "FLOW_SESSION_PATH": "/Users/gnoyes/.flow-mcp/session.json",
        "FLOW_DEFAULT_SCHEDULE_PROJECT_TITLE": "일정 공유"
      }
    }
  }
}
```

이미 다른 MCP 서버가 있다면 기존 `mcpServers` 안에 `flow` 항목만 추가하세요. 기존 서버 설정을 지우면 안 됩니다.

설정 후 Claude Desktop을 완전히 종료했다가 다시 실행하세요.

macOS에서는 창만 닫지 말고 `Cmd+Q`로 종료한 뒤 다시 실행하는 것을 권장합니다.

Claude Desktop에서 테스트할 프롬프트 예시:

```text
Flow에서 프로젝트 목록 3개만 가져와줘.
```

```text
Flow에서 오늘 일정 공유 프로젝트의 오늘 일정을 조회해줘.
```

## Hermes Agent에서 MCP로 사용하기

`flow-mcp-setup`으로 자동 등록할 수 있습니다.

```bash
cd flow-mcp
uv run flow-mcp-setup setup --configure-hermes
```

수동 설정이 필요하면 `~/.hermes/config.yaml`에 다음을 추가합니다.

```yaml
mcp_servers:
  flow:
    command: "uv"
    args: ["--directory", "/absolute/path/to/flow-mcp", "run", "flow-mcp"]
    timeout: 120
    connect_timeout: 60
```

Hermes Agent를 재시작하면 다음과 같은 이름으로 tool이 노출됩니다.

- `mcp_flow_flow_list_projects`
- `mcp_flow_flow_get_project_info`
- `mcp_flow_flow_list_project_schedules`
- `mcp_flow_flow_list_today_schedules`

## ID/password 로그인이 실패하는 경우

회사 계정 정책에 따라 다음 상황에서는 자동 로그인이 실패할 수 있습니다.

- SSO 전용 계정
- 2FA 필요 계정
- CAPTCHA 발생
- Flow 로그인 방식 변경

이 경우 본인 브라우저 세션에서 HAR을 export한 뒤 세션만 import하는 fallback을 사용할 수 있습니다.

```bash
cd flow-mcp
uv run flow-mcp-setup import-har ~/Downloads/flow.team.har
uv run flow-mcp-setup smoke-test
```

HAR 파일은 저장소 밖에 보관하고 공유하지 마세요.

## 개발

문법 체크:

```bash
uv run python -m compileall flow_mcp
```

테스트:

```bash
uv run pytest
```

MCP 서버 실행:

```bash
uv run flow-mcp
```
