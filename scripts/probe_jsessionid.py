"""Probe: does Flow require JSESSIONID alongside RGSN_DTTM?

Usage:
    FLOW_PASSWORD='...' uv run python scripts/probe_jsessionid.py
or interactive:
    uv run python scripts/probe_jsessionid.py

Runs login + list_projects on the SAME FlowClient (cookies preserved),
then on a FRESH FlowClient (token only, no cookies). Compares.
"""
import getpass
import os
import sys

from flow_mcp.client import FlowClient, FlowApiError


def main() -> int:
    user_id = os.environ.get("FLOW_USER_ID") or "kts@allra.co.kr"
    password = os.environ.get("FLOW_PASSWORD")
    if not password:
        try:
            password = getpass.getpass(f"Flow password for {user_id}: ")
        except (OSError, EOFError):
            print("ERROR: no TTY and FLOW_PASSWORD env var not set", file=sys.stderr)
            return 2

    # Step 1: login on client A
    a = FlowClient()
    try:
        a.login(user_id, password)
    except FlowApiError as e:
        print(f"login FAILED: {e}", file=sys.stderr)
        return 1
    print(f"login OK. cookies on client A: {list(a.http.cookies.keys())}")
    print(f"  token: {a.session.rgsn_dttm[:30]}...")

    # Step 2: list_projects on SAME client (cookies preserved)
    try:
        r = a.list_projects_simple(per_page=3)
        n = len(r.get("LIST") or r.get("list") or [])
        print(f"SAME-client list_projects: OK ({n} projects)")
        same_ok = True
    except FlowApiError as e:
        print(f"SAME-client list_projects: FAIL — {e}")
        same_ok = False

    # Step 3: list_projects on FRESH client (token only, no cookies)
    b = FlowClient()  # loads saved session from disk
    print(f"cookies on client B (fresh): {list(b.http.cookies.keys())}")
    try:
        r = b.list_projects_simple(per_page=3)
        n = len(r.get("LIST") or r.get("list") or [])
        print(f"FRESH-client list_projects: OK ({n} projects)")
        fresh_ok = True
    except FlowApiError as e:
        print(f"FRESH-client list_projects: FAIL — {e}")
        fresh_ok = False

    print()
    print("=== Verdict ===")
    if same_ok and not fresh_ok:
        print("JSESSIONID required: same-client works, fresh-client fails.")
        print("Fix: persist + reload cookies, or re-login on each new instance.")
        return 0
    if same_ok and fresh_ok:
        print("JSESSIONID NOT required: both work. Bug is elsewhere.")
        return 0
    if not same_ok:
        print("Even same-client fails after login. Encoding or other auth issue.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
