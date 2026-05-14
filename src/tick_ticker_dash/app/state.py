from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import streamlit as st
import streamlit.components.v1 as components

from tick_ticker_dash.app.common import clear_data_cache
from tick_ticker_dash.storage.local_store import (
    delete_dashboard,
    delete_saved_view,
    get_saved_view,
    list_dashboards,
    toggle_favorite,
)


def apply_route_from_url() -> None:
    if st.session_state.get("route_initialized"):
        return
    st.session_state["route_initialized"] = True

    path = urlparse(st.context.url).path.strip("/")
    parts = [part for part in path.split("/") if part]
    if not parts:
        return

    route = parts[0].lower()
    if route == "dashboard":
        st.session_state["page"] = "Dashboard"
        st.session_state["selected_source_id"] = None
        st.session_state["selected_view_id"] = None
        st.session_state["selected_dashboard_name"] = None
    elif route == "views":
        st.session_state["page"] = "Views"
        st.session_state["selected_source_id"] = None
        st.session_state["selected_view_id"] = None
    elif route in {"query", "query-tool"}:
        st.session_state["page"] = "Query Tool"
    elif route == "favorites":
        st.session_state["page"] = "Favorites"
    elif route == "source" and len(parts) > 1:
        st.session_state["page"] = "Views"
        st.session_state["selected_source_id"] = parts[1]
        st.session_state["selected_view_id"] = None


def sync_route_to_url() -> None:
    route = _current_route()
    components.html(
        f"""
        <script>
        const route = {route!r};
        const current = window.parent.location.pathname;
        if (current !== route) {{
          window.parent.history.replaceState(null, "", route + window.parent.location.search);
        }}
        </script>
        """,
        height=0,
        width=0,
    )


def _current_route() -> str:
    if st.session_state.get("selected_source_id"):
        return f"/source/{st.session_state['selected_source_id']}"

    page = st.session_state.get("page", "Dashboard")
    if page == "Views":
        return "/views"
    if page == "Query Tool":
        return "/query-tool"
    if page == "Favorites":
        return "/favorites"
    return "/dashboard"


def handle_action_params() -> None:
    action = st.query_params.get("action")
    item_type = st.query_params.get("item_type")
    item_id = st.query_params.get("item_id")
    if not action or not item_type or not item_id:
        return

    if action == "open" and item_type == "dashboard":
        dashboard = next((item for item in list_dashboards() if item["id"] == item_id), None)
        if dashboard:
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
        if dashboard and st.session_state.get("selected_dashboard_name") == dashboard["name"]:
            st.session_state["selected_dashboard_name"] = None
        clear_data_cache()
    elif action == "delete" and item_type == "view":
        delete_saved_view(item_id)
        if st.session_state.get("selected_view_id") == item_id:
            st.session_state["selected_view_id"] = None
        clear_data_cache()

    st.query_params.clear()
    st.rerun()


def open_favorite(favorite: dict[str, Any]) -> None:
    if favorite["type"] == "dashboard":
        dashboard = next((item for item in list_dashboards() if item["id"] == favorite["item_id"]), None)
        if dashboard:
            st.session_state["selected_dashboard_name"] = dashboard["name"]
            st.session_state["page"] = "Dashboard"
        return
    if favorite["type"] == "view":
        st.session_state["selected_view_id"] = favorite["item_id"]
        st.session_state["selected_source_id"] = None
        st.session_state["page"] = "Views"
