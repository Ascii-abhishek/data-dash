from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

import streamlit as st

from tick_ticker_dash.app.common import clear_data_cache
from tick_ticker_dash.storage.local_store import (
    delete_dashboard,
    delete_saved_view,
    get_saved_view,
    get_source,
    list_dashboards,
    toggle_favorite,
)


def apply_route_from_url() -> None:
    current_url = st.context.url or ""
    if isinstance(current_url, bytes | bytearray):
        current_url = current_url.decode()
    else:
        current_url = str(current_url)
    parsed = urlparse(current_url)
    params = parse_qs(parsed.query)
    chat_param = st.query_params.get("chat") or params.get("chat", [None])[0]
    if str(chat_param or "").lower() == "open":
        st.session_state["chat_open"] = True
    route_param = st.query_params.get("route") or params.get("route", [None])[0]
    path = (route_param or parsed.path.strip("/")).strip("/")
    if st.session_state.get("applied_route") == path:
        return
    st.session_state["applied_route"] = path
    parts = [part for part in path.split("/") if part]
    if not parts:
        return

    route = parts[0].lower()
    if route == "dashboard":
        st.session_state["page"] = "Dashboard"
        st.session_state["selected_source_id"] = None
        st.session_state["selected_view_id"] = None
        if len(parts) > 1:
            dashboard = next((item for item in list_dashboards() if item["id"] == parts[1]), None)
            st.session_state["selected_dashboard_id"] = dashboard["id"] if dashboard else None
            st.session_state["selected_dashboard_name"] = dashboard["name"] if dashboard else None
        else:
            st.session_state["selected_dashboard_id"] = None
            st.session_state["selected_dashboard_name"] = None
    elif route == "views":
        st.session_state["page"] = "Views"
        st.session_state["selected_dashboard_id"] = None
        st.session_state["selected_dashboard_name"] = None
        st.session_state["selected_source_id"] = None
        st.session_state["selected_view_id"] = unquote(parts[1]) if len(parts) > 1 else None
    elif route in {"query", "query-tool"}:
        st.session_state["page"] = "Query Tool"
        st.session_state["selected_dashboard_id"] = None
        st.session_state["selected_dashboard_name"] = None
    elif route == "favorites":
        st.session_state["page"] = "Favorites"
        st.session_state["selected_dashboard_id"] = None
        st.session_state["selected_dashboard_name"] = None
    elif route == "sources":
        st.session_state["selected_dashboard_id"] = None
        st.session_state["selected_dashboard_name"] = None
        st.session_state["selected_view_id"] = None
        if len(parts) > 1:
            source_id = unquote(parts[1])
            st.session_state["selected_source_id"] = source_id
            st.session_state["sources_browser_source_id"] = source_id
            if len(parts) > 2:
                table_name = unquote(parts[2])
                st.session_state[f"d1_selected_table_{source_id}"] = table_name
                st.session_state["page"] = "Views"
            else:
                st.session_state["page"] = "Sources"
        else:
            st.session_state["page"] = "Sources"
            st.session_state["selected_source_id"] = None
            st.session_state["sources_browser_source_id"] = None
    elif route == "source" and len(parts) > 1:
        st.session_state["page"] = "Views"
        st.session_state["selected_dashboard_id"] = None
        st.session_state["selected_dashboard_name"] = None
        st.session_state["selected_source_id"] = parts[1]
        st.session_state["selected_view_id"] = None


def sync_route_to_url() -> None:
    route = _current_route()
    next_route = route.strip("/") or "dashboard"
    current_path = _current_url_path()
    chat_in_url = st.query_params.get("chat") == "open"
    chat_matches = bool(st.session_state.get("chat_open")) == chat_in_url
    if current_path == next_route and st.query_params.get("route") is None and chat_matches:
        return
    _replace_browser_path(f"/{next_route}")


def _current_route() -> str:
    page = st.session_state.get("page", "Dashboard")
    if page == "Views" and st.session_state.get("selected_view_id"):
        return f"/views/{quote(str(st.session_state['selected_view_id']), safe='')}"
    if page == "Views" and st.session_state.get("selected_source_id"):
        source_id = quote(str(st.session_state["selected_source_id"]), safe="")
        source = get_source(str(st.session_state["selected_source_id"]))
        table_name = (
            st.session_state.get(f"d1_selected_table_{st.session_state['selected_source_id']}")
            if source and source.get("type") == "cloudflare_d1"
            else None
        )
        if table_name:
            return f"/sources/{source_id}/{quote(str(table_name), safe='')}"
        return f"/sources/{source_id}"
    if page == "Views":
        return "/views"
    if page == "Query Tool":
        return "/query-tool"
    if page == "Favorites":
        return "/favorites"
    if page == "Sources":
        source_id = st.session_state.get("sources_browser_source_id")
        if source_id:
            return f"/sources/{quote(str(source_id), safe='')}"
        return "/sources"
    if page == "Dashboard" and st.session_state.get("selected_dashboard_id"):
        return f"/dashboard/{st.session_state['selected_dashboard_id']}"
    return "/dashboard"


def _current_url_path() -> str:
    current_url = st.context.url or ""
    if isinstance(current_url, bytes | bytearray):
        current_url = current_url.decode()
    parsed = urlparse(str(current_url))
    return parsed.path.strip("/")


def _replace_browser_path(path: str) -> None:
    chat_open = bool(st.session_state.get("chat_open"))
    st.iframe(
        f"""
        <script>
        const targetPath = {path!r};
        const chatOpen = {str(chat_open).lower()};
        const params = new URLSearchParams(window.parent.location.search);
        params.delete("route");
        if (chatOpen) {{
            params.set("chat", "open");
        }} else {{
            params.delete("chat");
        }}
        const query = params.toString();
        const nextUrl = targetPath + (query ? "?" + query : "");
        if (window.parent.location.pathname + window.parent.location.search !== nextUrl) {{
            window.parent.history.replaceState(null, "", nextUrl);
        }}
        </script>
        """,
        height=1,
    )


def handle_action_params() -> None:
    action = st.query_params.get("action")
    item_type = st.query_params.get("item_type")
    item_id = st.query_params.get("item_id")
    if not action or not item_type or not item_id:
        return

    if action == "open" and item_type == "dashboard":
        dashboard = next((item for item in list_dashboards() if item["id"] == item_id), None)
        if dashboard:
            st.session_state["selected_dashboard_id"] = dashboard["id"]
            st.session_state["selected_dashboard_name"] = dashboard["name"]
            st.session_state["page"] = "Dashboard"
    elif action == "open" and item_type == "view":
        st.session_state["selected_view_id"] = item_id
        st.session_state["selected_source_id"] = None
        st.session_state["page"] = "Views"
    elif action == "toggle_favorite" and item_type == "dashboard":
        dashboard = next((item for item in list_dashboards() if item["id"] == item_id), None)
        if dashboard:
            toggle_favorite("dashboard", item_id, dashboard["name"])
    elif action == "toggle_favorite" and item_type == "view":
        view = get_saved_view(item_id)
        if view:
            toggle_favorite("view", item_id, view["name"])
    elif action == "delete" and item_type == "dashboard":
        dashboard = next((item for item in list_dashboards() if item["id"] == item_id), None)
        delete_dashboard(item_id)
        if dashboard and st.session_state.get("selected_dashboard_id") == dashboard["id"]:
            st.session_state["selected_dashboard_id"] = None
            st.session_state["selected_dashboard_name"] = None
        clear_data_cache()
    elif action == "delete" and item_type == "view":
        delete_saved_view(item_id)
        if st.session_state.get("selected_view_id") == item_id:
            st.session_state["selected_view_id"] = None
        clear_data_cache()

    st.query_params.clear()
    if st.session_state.get("chat_open"):
        st.query_params["chat"] = "open"


def open_favorite(favorite: dict[str, Any]) -> None:
    if favorite["type"] == "dashboard":
        dashboard = next((item for item in list_dashboards() if item["id"] == favorite["item_id"]), None)
        if dashboard:
            st.session_state["selected_dashboard_id"] = dashboard["id"]
            st.session_state["selected_dashboard_name"] = dashboard["name"]
            st.session_state["page"] = "Dashboard"
        return
    if favorite["type"] == "view":
        st.session_state["selected_view_id"] = favorite["item_id"]
        st.session_state["selected_source_id"] = None
        st.session_state["page"] = "Views"
