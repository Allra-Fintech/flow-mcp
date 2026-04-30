from __future__ import annotations

from typing import Any, Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .client import DEFAULT_SCHEDULE_PROJECT_TITLE, FlowClient

load_dotenv()

mcp = FastMCP("flow")
_client = FlowClient()


def client() -> FlowClient:
    return _client


@mcp.tool()
def flow_import_session_from_har(har_path: str) -> dict[str, Any]:
    """Import USER_ID/RGSN_DTTM from a HAR captured from your own logged-in Flow session."""
    return client().import_session_from_har(har_path)


@mcp.tool()
def flow_set_session(user_id: str, rgsn_dttm: str) -> dict[str, Any]:
    """Persist a Flow session token manually. Treat rgsn_dttm as sensitive."""
    return client().set_session(user_id, rgsn_dttm)


@mcp.tool()
def flow_login(user_id: str, password: str) -> dict[str, Any]:
    """Log in to Flow with ID/password and persist the session token locally."""
    return client().login(user_id, password)


@mcp.tool()
def flow_list_projects(page: int = 1, per_page: int = 50) -> dict[str, Any]:
    """List Flow projects in simplified form."""
    return client().list_projects_simple(page=page, per_page=per_page)


@mcp.tool()
def flow_list_projects_raw(page: int = 1, per_page: int = 50, mode: str = "") -> dict[str, Any]:
    """List Flow projects with the raw API response."""
    return client().list_projects(page=page, per_page=per_page, mode=mode)


@mcp.tool()
def flow_get_project_info(colabo_srno: str) -> dict[str, Any]:
    """Get raw Flow project metadata/settings by COLABO_SRNO."""
    return client().get_project_info(colabo_srno)


@mcp.tool()
def flow_list_project_posts(colabo_srno: str, page: int = 1, per_page: int = 20) -> dict[str, Any]:
    """List raw posts/feed items for a Flow project."""
    return client().list_project_posts(colabo_srno=colabo_srno, page=page, per_page=per_page)


@mcp.tool()
def flow_list_project_schedules(colabo_srno: str, first_dt: str, last_dt: str) -> dict[str, Any]:
    """List raw schedules for a Flow project.

    Dates are YYYYMMDD strings, e.g. 20260430.
    """
    return client().list_project_schedules(colabo_srno=colabo_srno, first_dt=first_dt, last_dt=last_dt)


@mcp.tool()
def flow_list_today_schedules(colabo_srno: Optional[str] = None, project_title: Optional[str] = None) -> dict[str, Any]:
    """List today's schedules. If colabo_srno is omitted, finds a project by title first.

    If project_title is omitted, FLOW_DEFAULT_SCHEDULE_PROJECT_TITLE is used.
    """
    return client().list_today_schedules(colabo_srno=colabo_srno, project_title=project_title or DEFAULT_SCHEDULE_PROJECT_TITLE)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
