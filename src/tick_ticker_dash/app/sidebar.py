from __future__ import annotations

import streamlit as st

from tick_ticker_dash.app.dialogs import render_source_dialog
from tick_ticker_dash.app.source_catalog import render_catalog_refresh_worker
from tick_ticker_dash.app.state import open_favorite
from tick_ticker_dash.config.settings import settings
from tick_ticker_dash.storage.local_store import list_favorites, list_sources


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(f"<div class='sidebar-brand'>{settings.app_name}</div>", unsafe_allow_html=True)
        sources = list_sources()
        favorites = list_favorites()
        render_catalog_refresh_worker()

        st.markdown("<div class='sidebar-section'>", unsafe_allow_html=True)
        st.markdown("<div class='section-label'>Home</div>", unsafe_allow_html=True)
        if st.button("Dashboards", key="nav_dashboard", icon=":material/dashboard:", width="stretch"):
            st.session_state["page"] = "Dashboard"
            st.session_state["selected_dashboard_id"] = None
            st.session_state["selected_dashboard_name"] = None
        if st.button("Views", key="nav_views", icon=":material/visibility:", width="stretch"):
            st.session_state["page"] = "Views"
            st.session_state["selected_dashboard_id"] = None
            st.session_state["selected_dashboard_name"] = None
            st.session_state["selected_source_id"] = None
            st.session_state["selected_view_id"] = None
        if st.button("Query Tool", key="nav_query", icon=":material/science:", width="stretch"):
            st.session_state["page"] = "Query Tool"
            st.session_state["selected_dashboard_id"] = None
            st.session_state["selected_dashboard_name"] = None
        if st.button("Chat with AI", key="nav_chat", icon=":material/chat:", width="stretch"):
            st.session_state["chat_open"] = True
        st.markdown("</div>", unsafe_allow_html=True)

        if favorites:
            st.markdown("<div class='sidebar-section'>", unsafe_allow_html=True)
            st.markdown("<div class='section-label'>Favorites</div>", unsafe_allow_html=True)
            for favorite in favorites[:10]:
                icon = ":material/dashboard:" if favorite["type"] == "dashboard" else ":material/table_view:"
                if st.button(favorite["name"], key=f"favorite_{favorite['key']}", icon=icon, width="stretch"):
                    open_favorite(favorite)
            if len(favorites) > 10 and st.button(
                "Show all",
                key="show_all_favorites",
                icon=":material/star:",
                width="stretch",
            ):
                st.session_state["page"] = "Favorites"
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='sidebar-section'>", unsafe_allow_html=True)
        st.markdown("<div class='section-label'>Sources</div>", unsafe_allow_html=True)
        if st.button("Add source", key="add_source", type="primary", icon=":material/add:", width="stretch"):
            render_source_dialog()
        if st.button("All sources", key="all_sources", icon=":material/storage:", width="stretch"):
            st.session_state["page"] = "Sources"
            st.session_state["selected_source_id"] = None
            st.session_state["selected_view_id"] = None
            st.session_state["sources_browser_source_id"] = None
        if not sources:
            st.caption("No sources added yet.")
        st.markdown("</div>", unsafe_allow_html=True)
