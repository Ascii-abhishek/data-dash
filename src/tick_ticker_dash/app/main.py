from __future__ import annotations

import streamlit as st

from tick_ticker_dash.app.dashboard import render_dashboard_page
from tick_ticker_dash.app.sidebar import render_sidebar
from tick_ticker_dash.app.state import apply_route_from_url, handle_action_params, sync_route_to_url
from tick_ticker_dash.app.styles import inject_css, inject_dynamic_button_styles
from tick_ticker_dash.app.views import render_favorites_page, render_query_tool_page, render_views_page
from tick_ticker_dash.config.settings import settings


def main() -> None:
    st.set_page_config(page_title=settings.app_name, page_icon="TT", layout="wide")
    inject_css()

    st.session_state.setdefault("page", "Dashboard")
    st.session_state.setdefault("selected_source_id", None)
    st.session_state.setdefault("selected_view_id", None)
    st.session_state.setdefault("selected_dashboard_name", None)
    st.session_state.setdefault("data_cache", {})
    apply_route_from_url()
    handle_action_params()

    render_sidebar()

    page = st.session_state["page"]
    if page == "Dashboard":
        render_dashboard_page()
    elif page == "Views":
        render_views_page()
    elif page == "Favorites":
        render_favorites_page()
    else:
        render_query_tool_page()
    sync_route_to_url()
    inject_dynamic_button_styles()
