# flow-mcp

Flow.team 웹 API를 MCP(Model Context Protocol) 서버로 감싼 비공식 내부 자동화 도구입니다.

본인 또는 조직에서 접근 권한이 있는 Flow 계정/워크스페이스에서만 사용하세요. 이 저장소에는 개인 인증정보, HAR 파일, 쿠키, 세션 토큰이 포함되지 않습니다.

<table>
  <tr>
    <td>
      <img width="390" alt="image" src="https://github.com/user-attachments/assets/8002e629-e846-4550-bc79-97cdaa6ee73a" />
    </td>
    <td>
      <img width="390" alt="image" src="https://github.com/user-attachments/assets/d8ddfc00-73dc-4127-a1ac-47c3cb880dfa" />
    </td>
  </tr>
</table>


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
- 게시글/하위 업무 본문+댓글 단건 조회 (댓글 미리보기)
- 게시글 댓글 페이지네이션
- 게시글 본문+전체 댓글 자동 수집(슬림 응답)
- 게시글 본문+전체 댓글 자동 수집(원본 응답)

MCP tool 목록:

- `flow_login(user_id, password)`
- `flow_import_session_from_har(har_path)`
- `flow_set_session(user_id, rgsn_dttm)`
- `flow_list_projects(page=1, per_page=50)`
- `flow_list_projects_raw(page=1, per_page=50, mode='')`
- `flow_get_project_info(colabo_srno)`
- `flow_list_project_posts(colabo_srno, page=1, per_page=20)`
- `flow_get_post_detail(colabo_srno, colabo_commt_srno, remark_per_page=999, remark_anchor_srno='-1')`
- `flow_list_post_remarks(colabo_srno, colabo_commt_srno, anchor_srno='-1', order_type='P')`
- `flow_get_post_full(colabo_srno, colabo_commt_srno, max_remark_pages=20)`
- `flow_extract_post(colabo_srno, colabo_commt_srno, max_remark_pages=20)`
- `flow_list_project_schedules(colabo_srno, first_dt, last_dt)`
- `flow_list_today_schedules(colabo_srno=None, project_title=None)`

날짜는 `YYYYMMDD` 문자열을 사용합니다.

`flow_list_today_schedules`에서 `project_title`을 생략하면 `FLOW_DEFAULT_SCHEDULE_PROJECT_TITLE` 환경변수 값을 사용합니다.

## 요구사항

- macOS/Linux/Windows
- Python 3.10+
- git
- uv

Windows는 WSL2 Ubuntu 사용을 권장합니다. Windows native PowerShell 설치도 가능하지만 아직 실험적입니다.

`install.sh`는 macOS/Linux/WSL2 환경에서 uv가 없으면 자동으로 설치를 시도합니다.

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
curl -fsSL https://raw.githubusercontent.com/Allra-Fintech/flow-mcp/main/install.sh | FLOW_MCP_LOGIN=0 bash

# Hermes config 자동 등록 없이 설치
curl -fsSL https://raw.githubusercontent.com/Allra-Fintech/flow-mcp/main/install.sh | FLOW_MCP_CONFIGURE_HERMES=0 bash

# 설치 위치 변경
curl -fsSL https://raw.githubusercontent.com/Allra-Fintech/flow-mcp/main/install.sh | FLOW_MCP_INSTALL_DIR="$HOME/dev/flow-mcp" bash

# MCP 서버 이름 변경
curl -fsSL https://raw.githubusercontent.com/Allra-Fintech/flow-mcp/main/install.sh | FLOW_MCP_SERVER_NAME=flow-team bash
```

파이프라인에서는 `FLOW_MCP_LOGIN=0 curl ... | bash`처럼 쓰면 환경변수가 `curl`에만 적용되고 `bash`에는 전달되지 않습니다. 위 예시처럼 `| FLOW_MCP_LOGIN=0 bash` 형태로 실행하세요.

## Windows 사용자 설치 방법

Windows에서는 WSL2 Ubuntu 사용을 권장합니다. Flow MCP 서버와 세션 파일은 WSL 안에 두고, Windows Claude Desktop은 `wsl.exe`를 통해 MCP 서버를 실행하는 방식입니다.

PowerShell에서 WSL2 Ubuntu 설치:

```powershell
wsl --install -d Ubuntu
```

설치 후 Windows를 재시작해야 할 수 있습니다. Ubuntu 터미널을 열고 아래 명령을 실행합니다.

```bash
curl -fsSL https://raw.githubusercontent.com/Allra-Fintech/flow-mcp/main/install.sh | bash
```

동작 확인:

```bash
cd ~/.flow-mcp/app
uv run flow-mcp-setup smoke-test
```

Windows Claude Desktop 설정 파일 위치:

```text
%APPDATA%\Claude\claude_desktop_config.json
```

Windows Claude Desktop에서 WSL 안의 Flow MCP를 실행하려면 `mcpServers`에 다음 형태를 추가합니다.

```json
{
  "mcpServers": {
    "flow": {
      "command": "wsl.exe",
      "args": [
        "-d",
        "Ubuntu",
        "--",
        "bash",
        "-lc",
        "cd ~/.flow-mcp/app && uv run flow-mcp"
      ],
      "env": {
        "FLOW_DEFAULT_SCHEDULE_PROJECT_TITLE": "일정 공유"
      }
    }
  }
}
```

WSL 배포판 이름이 `Ubuntu`가 아니면 PowerShell에서 아래 명령으로 이름을 확인한 뒤 `args`의 `Ubuntu` 값을 바꾸세요.

```powershell
wsl -l -v
```

Windows native PowerShell에 직접 설치하는 방식은 아직 실험적입니다. 가능하면 WSL2 방식을 사용하세요.

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

설정 파일 위치는 OS마다 다릅니다.

```text
macOS:   ~/Library/Application Support/Claude/claude_desktop_config.json
Windows: %APPDATA%\Claude\claude_desktop_config.json
Linux:   ~/.config/Claude/claude_desktop_config.json
```

설치 경로와 `uv` 경로도 OS/설치 방식마다 다르므로, 고정된 예시를 그대로 복사하지 말고 설치된 위치에서 설정 JSON을 생성하세요.

macOS/Linux/WSL 안에서 Claude Desktop 설정용 JSON 생성:

```bash
cd ~/.flow-mcp/app
uv run flow-mcp-setup claude-config
```

출력 예시는 다음과 같습니다. 실제 출력에는 현재 머신의 `uv`, 프로젝트, 세션 파일 절대경로가 들어갑니다.

```json
{
  "mcpServers": {
    "flow": {
      "command": "/absolute/path/to/uv",
      "args": [
        "--directory",
        "/absolute/path/to/flow-mcp",
        "run",
        "flow-mcp"
      ],
      "env": {
        "FLOW_SESSION_PATH": "/absolute/path/to/session.json",
        "FLOW_DEFAULT_SCHEDULE_PROJECT_TITLE": "일정 공유"
      }
    }
  }
}
```

기존 설정 파일에 다른 MCP 서버가 있다면 전체 파일을 덮어쓰지 말고, 출력된 JSON의 `mcpServers.flow` 항목만 기존 `mcpServers` 안에 추가하세요.

주의: Claude Desktop 설정은 JSON 파일입니다. `~`, `$HOME`, `%USERPROFILE%`, `str(Path.home() / ...)` 같은 shell/Python 표현식은 쓰지 말고 실제 절대경로 문자열로 바꿔서 넣어야 합니다.

Windows에서 WSL2 Ubuntu에 설치한 경우에는 위의 `Windows 사용자 설치 방법` 섹션에 있는 `wsl.exe` 설정 예시를 사용하세요.

Windows native에 직접 설치한 경우에는 `command`, `--directory`, `FLOW_SESSION_PATH`를 Windows 절대경로로 넣어야 합니다. 예: `C:\\Users\\<YOUR_USER>\\.flow-mcp\\app`. Windows native 방식은 아직 실험적으로 보고, 가능하면 WSL2 사용을 권장합니다.

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

## 사용 팁

Flow MCP를 다루며 자주 마주치는 함정과 노하우를 모았습니다. Flow 공식 문서가 없는 영역이라 실측 기준으로 정리했습니다.

### 1. 세션이 자주 만료된다 (`S0002`)

도구 호출 첫 시도에서 다음 에러가 자주 발생합니다.

```text
Flow error from /COLABO2_R104.jct: {'CODE': 'S0002', 'MESSAGE': '로그인 세션이 만료되었습니다...'}
```

`FlowClient._post`에 짧은 재시도가 있지만 동일 토큰으로만 재시도하므로, 토큰이 진짜 무효화된 경우엔 회복되지 않습니다. 대처법은 둘 중 하나입니다.

- `flow_login(user_id, password)`을 다시 호출해 세션을 갱신
- 브라우저 세션에서 새 HAR을 export 한 뒤 `flow_import_session_from_har(path)`로 import

LLM 에이전트가 자동화하는 경우, `S0002`를 만나면 곧바로 `flow_login`을 한 번 호출하고 원래 작업을 재시도하도록 흐름을 짜는 것을 권장합니다.

### 2. 게시글 종류는 `TMPL_TYPE`으로 구분한다

`flow_list_project_posts` 응답의 `COMMT_REC[]` 항목은 모두 같은 게시글 객체지만, 종류가 섞여 있습니다.

| `TMPL_TYPE` | 의미 |
| --- | --- |
| `1` | 시스템 메시지 (멤버 초대 등) |
| `91` | 주간 업무 보고/노트 |
| `92` | **업무(Task)** — `SUBTASK_REC[]`에 하위 업무 메타가 들어있음 |

업무 트리만 필터링하려면 `select(.TMPL_TYPE == "92")`를 쓰면 됩니다.

### 3. 상태값은 `STTS` 정수 코드로 들어온다

업무/하위 업무의 상태는 `STTS` 필드에 문자열 코드로 옵니다. 매핑은 다음과 같습니다(웹 UI의 상태 칩과 대조해 검증한 결과).

| `STTS` | 상태 | UI 색상 |
| --- | --- | --- |
| `0` | 요청 | 하늘색 |
| `1` | 진행 | 초록 |
| `2` | 완료 | 보라 |
| `3` | 보류 | 회색 |

데이터를 사람이 읽는 형태로 가공할 때 이 매핑을 우선 적용하세요.

### 4. 섹션(그룹) 이름은 `TASK_REC[0].SECTION_NAME`에 있다

업무 탭의 "그룹" 헤더(예: `올라 - 초간편 자금관리 서비스`)는 `COMMT_REC[i].TASK_REC[0].SECTION_NAME`에서 읽을 수 있습니다.

- `COMMT_REC[i].GROUP_SRNO`는 거의 `null`이라 사용 불가
- 응답 최상위의 `SECTION_CNT`는 섹션 개수일 뿐 매핑 정보가 아님

특정 섹션만 추출하려면 다음 패턴을 씁니다.

```bash
jq '[.COMMT_REC[]
     | select(.TMPL_TYPE == "92")
     | select(.TASK_REC[0].SECTION_NAME == "원하는 섹션 이름")]'
```

### 5. 본문 `CNTN`이 JSON 문자열일 수 있다

게시글 본문은 단순 문자열일 때도 있지만, 다음과 같은 구조화된 JSON 문자열이 그대로 들어 있을 수도 있습니다.

```json
{
  "COMPS": [
    {
      "COMP_TYPE": "TEXT",
      "COMP_DETAIL": { "CONTENTS": "본문 텍스트", "MENTIONS": [], "HASHTAGS": [] }
    }
  ]
}
```

LLM이나 화면에 그대로 보여 주면 가독성이 떨어지므로, `CNTN`이 `{`로 시작하면 파싱하여 `.COMPS[].COMP_DETAIL.CONTENTS`를 합쳐 사용하는 것을 권장합니다.

### 6. `TOT_CNT`는 게시글 수가 아니다

페이지 끝 판단을 `TOT_CNT`로 하면 안 됩니다. `TOT_CNT`는 댓글/이벤트 등을 포함한 다른 합계로 보이며 공식 문서가 없습니다. 페이지 끝은 응답 최상위의 `NEXT_YN`을 사용하세요.

- `NEXT_YN == "Y"` → 더 받을 페이지 있음
- `NEXT_YN == "N"` → 마지막 페이지

### 7. 댓글에는 시스템/사용자 두 종류가 섞인다

상태 변경, 담당자 추가, 마감일 변경 같은 액션도 댓글(remark)로 기록됩니다. 사용자 코멘트와 분리하려면 다음 둘 중 하나를 확인하세요.

- `SYSTEM_REMARK_YN == "Y"` (가장 정확)
- 또는 `CNTN`이 `'요청' → '진행' 상태를 변경하였습니다.`, `'YYYY-MM-DD' 마감일을 추가하였습니다.` 같은 자동 메시지 패턴

`flow_extract_post`는 각 댓글에 `is_system` 불리언을 채워서 반환하므로, 통계나 요약이 필요할 때 그대로 활용할 수 있습니다.

### 8. 업무 트리 + 본문/댓글 한꺼번에 수집

`flow_list_project_posts`는 부모 업무(TMPL_TYPE=92)의 `SUBTASK_REC` 안에 하위 업무 메타데이터만 담아 줍니다(`TASK_NM`, `STTS`, `WORKER_REC`, `END_DT`, `REMARK_CNT` 등). 하위 업무의 **본문(`CNTN`)과 댓글 전체**는 같은 응답에 들어오지 않고, 각 하위 업무가 독립된 게시글(`COLABO_COMMT_SRNO`)로 따로 존재합니다.

이 데이터를 채우려면 하위 업무마다 다음 도구를 호출하면 됩니다.

```text
flow_extract_post(colabo_srno, colabo_commt_srno)
```

`flow_extract_post`는 `flow_get_post_full`을 슬림하게 감싼 버전입니다. 내부적으로

1. `/COLABO2_R104.jct?mode=DETAIL`로 본문 + 미리보기 댓글 2개를 받고
2. 더 받을 댓글이 있으면 `/COLABO2_REMARK_R101.jct?mode=M`을 `anchor_srno` 커서로 페이지네이션하여
3. 댓글을 시간순으로 합친 뒤
4. `{post_srno, title, content, comments[], remark_expected, remark_fetched}` 형태로 정리해 반환합니다.

`flow_get_post_full`은 동일한 페이지네이션 로직을 따르지만 Flow 원본 응답 키를 유지하므로 후속 가공 자유도가 필요할 때 사용하세요. 단일 페이지 댓글만 직접 다룰 때는 `flow_list_post_remarks`를 쓰면 됩니다.

> 응답 크기 차이: 댓글 7개 기준 `flow_get_post_full`은 약 40 KB, `flow_extract_post`는 약 1.4 KB입니다. 많은 하위 업무를 일괄 순회할 때는 `flow_extract_post`를 권장합니다.

응답에서 `remark_expected`와 `remark_fetched` 값을 비교해 누락이 있는지 확인할 수 있습니다. 누락된 항목이 있으면 `flow_list_post_remarks`로 anchor를 바꿔 추가 페이지를 더 받아 보강할 수 있습니다.

### 9. 새 endpoint를 찾고 도구로 추가하는 패턴

Flow에 새 동작을 호출하는 endpoint를 추가하고 싶을 때의 작업 절차입니다.

1. Chrome/Edge 개발자 도구 → Network 탭 → "Preserve log" 켜기
2. Flow 웹에서 해당 흐름을 한 번 수행 (예: 게시글 클릭, 댓글 더보기 등)
3. Network 탭 우클릭 → "Save all as HAR with content"로 HAR 저장
4. `jq '.log.entries[] | select(.request.url | test("flow\\.team.*\\.jct"))'`로 호출된 endpoint 추출
5. 페이로드(`request.postData.text`의 `_JSON_` 디코드)와 응답 구조 확인
6. `flow_mcp/client.py`에 메서드, `flow_mcp/server.py`에 `@mcp.tool()` 추가
7. MCP 서버 재시작 (Claude Code에서 `/mcp` 또는 `pkill -f flow-mcp`)
