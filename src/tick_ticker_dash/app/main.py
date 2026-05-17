from __future__ import annotations

import streamlit as st

from tick_ticker_dash.app.chat import render_chat_panel
from tick_ticker_dash.app.dashboard import render_dashboard_page
from tick_ticker_dash.app.sidebar import render_sidebar
from tick_ticker_dash.app.state import apply_route_from_url, handle_action_params, sync_route_to_url
from tick_ticker_dash.app.styles import inject_css
from tick_ticker_dash.app.views import render_favorites_page, render_query_tool_page, render_sources_page, render_views_page
from tick_ticker_dash.config.settings import settings


def main() -> None:
    st.set_page_config(page_title=settings.APP_NAME, page_icon="TT", layout="wide")
    inject_css()

    st.session_state.setdefault("page", "Dashboard")
    st.session_state.setdefault("selected_source_id", None)
    st.session_state.setdefault("selected_view_id", None)
    st.session_state.setdefault("selected_dashboard_id", None)
    st.session_state.setdefault("selected_dashboard_name", None)
    st.session_state.setdefault("data_cache", {})
    st.session_state.setdefault("chat_open", False)
    st.session_state.setdefault("layout_only_rerun", False)
    apply_route_from_url()
    handle_action_params()

    render_sidebar()
    sync_route_to_url()

    if st.session_state.get("chat_open"):
        main_col, chat_col = st.columns([0.68, 0.32], gap="large")
        with chat_col:
            st.markdown("<div class='chat-rail-start'></div>", unsafe_allow_html=True)
            with st.container():
                render_chat_panel()
        with main_col:
            _render_current_page()
    else:
        _render_current_page()
    st.session_state["layout_only_rerun"] = False
    sync_route_to_url()


def _render_current_page() -> None:
    page = st.session_state["page"]
    if page == "Dashboard":
        render_dashboard_page()
    elif page == "Views":
        render_views_page()
    elif page == "Favorites":
        render_favorites_page()
    elif page == "Sources":
        render_sources_page()
    else:
        render_query_tool_page()
