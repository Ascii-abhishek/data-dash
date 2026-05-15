from __future__ import annotations

import streamlit as st

from tick_ticker_dash.app.common import source_display_name, source_type_icon
from tick_ticker_dash.app.dialogs import render_source_dialog
from tick_ticker_dash.app.state import open_favorite
from tick_ticker_dash.config.settings import settings
from tick_ticker_dash.storage.local_store import list_favorites, list_sources


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(f"<div class='sidebar-brand'>{settings.app_name}</div>", unsafe_allow_html=True)
        sources = list_sources()
        favorites = list_favorites()

        st.markdown("<div class='sidebar-section'>", unsafe_allow_html=True)
        st.markdown("<div class='section-label'>Home</div>", unsafe_allow_html=True)
        if st.button("Dashboards", key="nav_dashboard", icon=":material/dashboard:", use_container_width=True):
            st.session_state["page"] = "Dashboard"
        if st.button("Views", key="nav_views", icon=":material/visibility:", use_container_width=True):
            st.session_state["page"] = "Views"
            st.session_state["selected_source_id"] = None
            st.session_state["selected_view_id"] = None
        if st.button("Query Tool", key="nav_query", icon=":material/science:", use_container_width=True):
            st.session_state["page"] = "Query Tool"
        st.markdown("</div>", unsafe_allow_html=True)

        if favorites:
            st.markdown("<div class='sidebar-section'>", unsafe_allow_html=True)
            st.markdown("<div class='section-label'>Favorites</div>", unsafe_allow_html=True)
            for favorite in favorites[:10]:
                icon = ":material/dashboard:" if favorite["type"] == "dashboard" else ":material/table_view:"
                if st.button(favorite["name"], key=f"favorite_{favorite['key']}", icon=icon, use_container_width=True):
                    open_favorite(favorite)
            if len(favorites) > 10 and st.button(
                "Show all",
                key="show_all_favorites",
                icon=":material/star:",
                use_container_width=True,
            ):
                st.session_state["page"] = "Favorites"
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='sidebar-section'>", unsafe_allow_html=True)
        st.markdown("<div class='section-label'>Sources</div>", unsafe_allow_html=True)
        if st.button("Add source", key="add_source", type="primary", icon=":material/add:", use_container_width=True):
            render_source_dialog()

        if not sources:
            st.caption("No sources added yet.")
        st.markdown("<div class='source-list'>", unsafe_allow_html=True)
        for source in sources:
            left, right = st.columns([0.78, 0.22], gap="small", vertical_alignment="center")
            with left:
                if st.button(
                    source_display_name(source),
                    key=f"source_{source['id']}",
                    icon=source_type_icon(source),
                    use_container_width=True,
                ):
                    st.session_state["selected_source_id"] = source["id"]
                    st.session_state["selected_view_id"] = None
                    st.session_state["page"] = "Views"
            with right:
                st.markdown("<div class='icon-only-button'>", unsafe_allow_html=True)
                if st.button(
                    "",
                    key=f"edit_source_{source['id']}",
                    icon=":material/edit:",
                    help=f"Edit {source['name']}",
                    use_container_width=True,
                ):
                    render_source_dialog(source["id"])
                st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
