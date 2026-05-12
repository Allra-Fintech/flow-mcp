from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from .client import DEFAULT_SESSION_PATH, FlowApiError, FlowClient


DEFAULT_INSTALL_DIR = Path(os.environ.get("FLOW_MCP_INSTALL_DIR", "~/.flow-mcp/app")).expanduser()


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _input_tty(prompt: str) -> str:
    """Like input() but reads from /dev/tty so it works when stdin is a pipe."""
    if sys.stdin.isatty():
        return input(prompt).strip()
    with open("/dev/tty") as tty:
        sys.stderr.write(prompt)
        sys.stderr.flush()
        return tty.readline().rstrip("\n").strip()


def cmd_login(args: argparse.Namespace) -> int:
    load_dotenv()
    user_id = args.user_id or _input_tty("Flow ID/email: ")
    password = args.password or getpass.getpass("Flow password: ")
    client = FlowClient(session_path=args.session_path or None)
    try:
        result = client.login(user_id, password)
    except FlowApiError as exc:
        print(f"Flow login failed: {exc}", file=sys.stderr)
        return 1
    print(f"Saved Flow session to {client.session_path}")
    _print_json(result)
    return 0


def cmd_import_har(args: argparse.Namespace) -> int:
    client = FlowClient(session_path=args.session_path or None)
    try:
        result = client.import_session_from_har(args.har_path)
    except FlowApiError as exc:
        print(f"Flow HAR import failed: {exc}", file=sys.stderr)
        return 1
    _print_json(result)
    return 0


def cmd_smoke_test(args: argparse.Namespace) -> int:
    client = FlowClient(session_path=args.session_path or None)
    try:
        result = client.list_projects_simple(per_page=args.per_page)
    except Exception as exc:
        print(f"Flow smoke test failed: {exc}", file=sys.stderr)
        return 1
    _print_json(result)
    return 0


def _install_uv_if_missing() -> None:
    if shutil.which("uv"):
        return
    print("uv not found; installing uv with Astral's installer...")
    subprocess.run("curl -LsSf https://astral.sh/uv/install.sh | sh", shell=True, check=True)


def _write_hermes_config(project_dir: Path, server_name: str = "flow") -> Path:
    config_path = Path(os.environ.get("HERMES_CONFIG", "~/.hermes/config.yaml")).expanduser()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise RuntimeError(f"Hermes config is not a YAML mapping: {config_path}")
    else:
        data = {}

    servers = data.setdefault("mcp_servers", {})
    if not isinstance(servers, dict):
        raise RuntimeError("Hermes config key 'mcp_servers' exists but is not a mapping")

    servers[server_name] = {
        "command": "uv",
        "args": ["--directory", str(project_dir), "run", "flow-mcp"],
        "timeout": 120,
        "connect_timeout": 60,
    }
    config_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return config_path


def cmd_setup(args: argparse.Namespace) -> int:
    project_dir = Path(args.project_dir or os.getcwd()).resolve()
    _install_uv_if_missing()
    print(f"Installing dependencies in {project_dir} ...")
    subprocess.run(["uv", "sync"], cwd=project_dir, check=True)

    if args.login:
        rc = cmd_login(argparse.Namespace(user_id=args.user_id, password=None, session_path=args.session_path))
        if rc != 0:
            return rc
        rc = cmd_smoke_test(argparse.Namespace(session_path=args.session_path, per_page=3))
        if rc != 0:
            return rc

    if args.configure_hermes:
        config_path = _write_hermes_config(project_dir, args.server_name)
        print(f"Hermes MCP config updated: {config_path}")
        print("Restart Hermes Agent for MCP tool discovery.")

    print("flow-mcp setup complete.")
    return 0


def cmd_claude_config(args: argparse.Namespace) -> int:
    project_dir = Path(args.project_dir or os.getcwd()).resolve()
    session_path = Path(args.session_path or DEFAULT_SESSION_PATH).expanduser().resolve()
    uv_command = args.uv_command or shutil.which("uv") or "uv"
    config = {
        "mcpServers": {
            args.server_name: {
                "command": uv_command,
                "args": ["--directory", str(project_dir), "run", "flow-mcp"],
                "env": {
                    "FLOW_SESSION_PATH": str(session_path),
                    "FLOW_DEFAULT_SCHEDULE_PROJECT_TITLE": args.default_schedule_project_title,
                },
            }
        }
    }
    _print_json(config)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Setup and manage the Flow MCP server")
    parser.add_argument("--session-path", default=None, help=f"Session file path; default: {DEFAULT_SESSION_PATH}")
    sub = parser.add_subparsers(dest="command", required=True)

    login = sub.add_parser("login", help="Log in with Flow ID/password and save a session token")
    login.add_argument("--user-id", default=None, help="Flow ID/email. If omitted, prompts interactively.")
    login.add_argument("--password", default=None, help="Flow password. Avoid this in shared shell history.")
    login.set_defaults(func=cmd_login)

    har = sub.add_parser("import-har", help="Import USER_ID/RGSN_DTTM from a local HAR file")
    har.add_argument("har_path")
    har.set_defaults(func=cmd_import_har)

    smoke = sub.add_parser("smoke-test", help="Call project list with the saved session")
    smoke.add_argument("--per-page", type=int, default=3)
    smoke.set_defaults(func=cmd_smoke_test)

    setup = sub.add_parser("setup", help="Install dependencies, optionally login, optionally configure Hermes MCP")
    setup.add_argument("--project-dir", default=None, help="Project directory; default: current directory")
    setup.add_argument("--login", action="store_true", help="Prompt for Flow credentials and save a session")
    setup.add_argument("--user-id", default=None, help="Flow ID/email for --login")
    setup.add_argument("--configure-hermes", action="store_true", help="Append this server to ~/.hermes/config.yaml")
    setup.add_argument("--server-name", default="flow", help="Hermes MCP server name")
    setup.set_defaults(func=cmd_setup)

    claude = sub.add_parser("claude-config", help="Print Claude Desktop MCP JSON for this machine")
    claude.add_argument("--project-dir", default=None, help="Project directory; default: current directory")
    claude.add_argument("--server-name", default="flow", help="Claude MCP server name")
    claude.add_argument("--uv-command", default=None, help="uv executable path; default: detected with PATH")
    claude.add_argument("--default-schedule-project-title", default="일정 공유")
    claude.set_defaults(func=cmd_claude_config)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
