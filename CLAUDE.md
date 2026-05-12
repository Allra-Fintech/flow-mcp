# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                          # install / refresh dependencies
uv run pytest                    # run all tests
uv run pytest tests/test_client.py::test_name  # run a single test

uv run flow-mcp                  # start the MCP server (stdio)
uv run flow-mcp-setup login      # interactive login → saves session
uv run flow-mcp-setup import-har <path.har>  # import session from HAR
uv run flow-mcp-setup smoke-test # verify saved session works
uv run flow-mcp-setup setup --login --configure-hermes  # full install
uv run flow-mcp-setup claude-config  # print Claude Desktop MCP JSON
```

## Architecture

Three files carry all the logic:

- **`flow_mcp/client.py`** — `FlowClient`: all HTTP calls to `flow.team`. Auth uses `USER_ID` + `RGSN_DTTM` passed in every request body (not cookies). Login (`COLABO2_LOGIN_R003.jct`) requires AES-CBC password encryption via `_flow_password_encrypt`; the key is `"aes256-global-flow" + CUR_DTTM` (32 bytes when CUR_DTTM is `YYYYMMDDHHMMSS`). The session is persisted to `~/.flow-mcp/session.json`.

- **`flow_mcp/server.py`** — thin FastMCP wrapper. Each `@mcp.tool()` function delegates to `FlowClient`. The MCP server entrypoint is `flow-mcp`.

- **`flow_mcp/cli.py`** — setup/management CLI (`flow-mcp-setup`). Handles login, HAR import, Hermes YAML config, and Claude Desktop JSON config generation.

## Session / Auth

Three ways to authenticate (checked in order):
1. `FLOW_USER_ID` + `FLOW_RGSN_DTTM` environment variables
2. `~/.flow-mcp/session.json` (written by `login` or `import-har`)
3. Direct call to `flow_login` / `flow_set_session` MCP tools

The `RGSN_DTTM` token (returned by the login API) is a long-lived session credential — treat it like a password.

## Environment

Copy `.env.example` to `.env` for local development. Key variables:
- `FLOW_BASE_URL` — default `https://flow.team`
- `FLOW_SESSION_PATH` — default `~/.flow-mcp/session.json`
- `FLOW_DEFAULT_SCHEDULE_PROJECT_TITLE` — project name used by `flow_list_today_schedules` when no `colabo_srno` is given
