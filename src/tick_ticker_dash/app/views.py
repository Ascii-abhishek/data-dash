from __future__ import annotations

from typing import Any

import streamlit as st

from tick_ticker_dash.app.common import (
    cached_preview,
    cached_sql,
    clear_data_cache,
    default_sql_for_source,
    render_cache_status,
    render_dataframe,
    render_empty_state,
    source_name,
    source_type_icon_name,
)
from tick_ticker_dash.app.state import open_favorite
from tick_ticker_dash.app.styles import action_link, page_title
from tick_ticker_dash.connections.registry import list_source_tables
from tick_ticker_dash.storage.local_store import (
    get_saved_view,
    get_source,
    is_favorite,
    list_favorites,
    list_saved_views,
    list_sources,
    save_saved_view,
    toggle_favorite,
)


def render_views_page() -> None:
    sources = list_sources()
    views = list_saved_views()
    if not sources and not views:
        page_title("Views", "visibility")
        render_empty_state("Select something from the left, or add a new data source.")
        return

    selected_id = st.session_state.get("selected_source_id")
    selected_view_id = st.session_state.get("selected_view_id")
    source_ids = [source["id"] for source in sources]
    if selected_id not in source_ids:
        selected_id = None

    if selected_view_id:
        render_saved_view(selected_view_id)
        return

    if not selected_id:
        page_title("Views", "visibility")
        render_view_index(views)
        return

    source = get_source(selected_id)
    if not source:
        st.error("Source not found.")
        return

    page_title(source["name"], source_type_icon_name(source))
    if source["type"] == "cloudflare_d1":
        render_d1_source_browser(source)
        return

    controls = st.columns([0.28, 0.28, 0.18, 0.26], vertical_alignment="bottom")
    limit = controls[0].number_input("Preview rows", min_value=1, max_value=10000, value=200, step=50)
    refresh_seconds = controls[1].number_input(
        "Refresh interval seconds",
        min_value=5,
        value=max(int(source["metadata"].get("refresh_seconds", 60)), 5),
        step=5,
    )
    if controls[2].button("Refresh now", icon=":material/refresh:", use_container_width=True):
        clear_data_cache(source["id"])
    where_clause = st.text_input("WHERE condition", placeholder="<col_name> <operator> <value> (e.g. timestamp > '2024-01-01')")
    auto_refresh = st.checkbox("Enable auto refresh", value=False)
    render_source_preview(source, int(limit), auto_refresh, int(refresh_seconds), where_clause.strip())


def render_d1_source_browser(source: dict[str, Any]) -> None:
    tables_key = f"d1_tables_{source['id']}"
    selected_key = f"d1_selected_table_{source['id']}"

    if st.button("Refresh tables", icon=":material/refresh:", use_container_width=True):
        st.session_state.pop(tables_key, None)
        clear_data_cache(source["id"])

    if tables_key not in st.session_state:
        try:
            with st.spinner("Loading D1 tables..."):
                st.session_state[tables_key] = list_source_tables(source)
        except Exception as exc:
            st.error(str(exc))
            return

    tables = st.session_state.get(tables_key, [])
    if not tables:
        render_empty_state("No tables found in this D1 database.")
        return

    st.markdown("<div class='section-label'>Tables</div>", unsafe_allow_html=True)
    st.markdown("<div class='d1-table-list'>", unsafe_allow_html=True)
    with st.container(height=180, border=True):
        for table_name in tables:
            selected = st.session_state.get(selected_key) == table_name
            if st.button(
                table_name,
                key=f"d1_table_{source['id']}_{table_name}",
                type="primary" if selected else "secondary",
                use_container_width=True,
            ):
                st.session_state[selected_key] = table_name
                clear_data_cache(source["id"])
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    selected_table = st.session_state.get(selected_key)
    if selected_table not in tables:
        st.caption("Select a table to preview its rows.")
        return

    controls = st.columns([0.28, 0.28, 0.18, 0.26], vertical_alignment="bottom")
    limit = controls[0].number_input("Preview rows", min_value=1, max_value=10000, value=200, step=50)
    refresh_seconds = controls[1].number_input("Refresh interval seconds", min_value=5, value=60, step=5)
    if controls[2].button("Refresh now", icon=":material/refresh:", use_container_width=True):
        clear_data_cache(source["id"])
    where_clause = st.text_input("WHERE condition", placeholder="e.g. name = 'Dev' and created_at > '2024-01-01'")
    auto_refresh = st.checkbox("Enable auto refresh", value=False)

    sql = _build_table_sql(selected_table, int(limit), where_clause.strip())
    st.code(sql, language="sql")
    render_d1_table_preview(source, sql, auto_refresh, int(refresh_seconds))


def render_d1_table_preview(source: dict[str, Any], sql: str, auto_refresh: bool, refresh_seconds: int) -> None:
    @st.fragment(run_every=f"{refresh_seconds}s")
    def _render() -> None:
        _render_sql_preview_body(source, sql, refresh_seconds, "d1_table_preview")

    if auto_refresh:
        _render()
    else:
        _render_sql_preview_body(source, sql, refresh_seconds, "d1_table_preview")


def _render_sql_preview_body(source: dict[str, Any], sql: str, refresh_seconds: int, key_prefix: str) -> None:
    try:
        with st.spinner("Loading table rows..."):
            df, cached_at, from_cache = cached_sql(source, sql, refresh_seconds)
        render_cache_status(cached_at, from_cache)
        render_dataframe(df, key_prefix)
    except Exception as exc:
        st.error(str(exc))


def _quote_sql_identifier(identifier: str) -> str:
    return f'"{identifier.replace('"', '""')}"'


def _build_table_sql(table_name: str, limit: int, where_clause: str = "") -> str:
    table_ref = _quote_sql_identifier(table_name)
    if where_clause:
        return f"SELECT * FROM {table_ref} WHERE {where_clause} LIMIT {limit}"
    return f"SELECT * FROM {table_ref} LIMIT {limit}"


def render_view_index(views: list[dict[str, Any]]) -> None:
    top = st.columns([0.18, 0.82], vertical_alignment="bottom")
    if top[0].button("Add view", type="primary", icon=":material/add:", use_container_width=True):
        st.session_state["page"] = "Query Tool"
        st.rerun()

    if not views:
        render_empty_state("Save query results as views from the Query Tool.")
        return

    for view in views:
        with st.container(border=True):
            columns = st.columns([0.52, 0.16, 0.16, 0.16], vertical_alignment="center")
            columns[0].markdown(f"#### {view['name']}")
            columns[1].markdown(
                action_link("Open", "open_in_new", "open", "view", view["id"], "open"),
                unsafe_allow_html=True,
            )
            view_starred = is_favorite("view", view["id"])
            columns[2].markdown(
                action_link(
                    "Starred" if view_starred else "Star",
                    "star" if view_starred else "star_border",
                    "toggle_favorite",
                    "view",
                    view["id"],
                    "starred" if view_starred else "star",
                ),
                unsafe_allow_html=True,
            )
            columns[3].markdown(
                action_link("Delete", "delete", "delete", "view", view["id"], "delete"),
                unsafe_allow_html=True,
            )


def render_saved_view(view_id: str) -> None:
    view = get_saved_view(view_id)
    if not view:
        st.error("Saved view not found.")
        return
    source = get_source(view["source_id"])
    if not source:
        st.error("The data source for this saved view no longer exists.")
        return

    page_title(view["name"], "visibility")
    controls = st.columns([0.22, 0.26, 0.18, 0.34], vertical_alignment="bottom")
    auto_refresh = controls[0].checkbox("Enable auto refresh", value=bool(view.get("auto_refresh", False)))
    refresh_seconds = int(
        controls[1].number_input(
            "Refresh interval seconds",
            min_value=5,
            value=max(int(view.get("refresh_seconds", 60)), 5),
            step=5,
        )
    )
    if controls[2].button("Refresh now", icon=":material/refresh:", use_container_width=True):
        clear_data_cache(source["id"])

    @st.fragment(run_every=f"{refresh_seconds}s")
    def _render() -> None:
        _render_saved_view_body(source, view, refresh_seconds)

    if auto_refresh:
        _render()
    else:
        _render_saved_view_body(source, view, refresh_seconds)


def _render_saved_view_body(source: dict[str, Any], view: dict[str, Any], refresh_seconds: int) -> None:
    try:
        with st.spinner("Loading market data..."):
            df, cached_at, from_cache = cached_sql(source, view["sql"], refresh_seconds)
        render_cache_status(cached_at, from_cache)
        render_dataframe(df, "saved_view_result")
    except Exception as exc:
        st.error(str(exc))


def render_favorites_page() -> None:
    page_title("Favorites", "star")
    favorites = list_favorites()
    if not favorites:
        render_empty_state("Star dashboards or views to pin them here.")
        return

    for favorite in favorites:
        with st.container(border=True):
            columns = st.columns([0.56, 0.18, 0.18], vertical_alignment="center")
            columns[0].markdown(f"#### {favorite['name']}")
            columns[0].caption("Dashboard" if favorite["type"] == "dashboard" else "View")
            if columns[1].button(
                "Open",
                key=f"open_all_favorite_{favorite['key']}",
                icon=":material/open_in_new:",
                use_container_width=True,
            ):
                open_favorite(favorite)
                st.rerun()
            if columns[2].button(
                "Unstar",
                key=f"unstar_all_favorite_{favorite['key']}",
                icon=":material/star:",
                use_container_width=True,
            ):
                toggle_favorite(favorite["type"], favorite["item_id"], favorite["name"])
                st.rerun()


def render_query_tool_page() -> None:
    page_title("Query Tool", "science")
    sources = list_sources()
    if not sources:
        render_empty_state("Select something from the left, or add a new data source.")
        return

    source_ids = [source["id"] for source in sources]
    selected_id = st.session_state.get("selected_source_id")
    index = source_ids.index(selected_id) if selected_id in source_ids else 0
    source_id = st.selectbox("Data source", source_ids, index=index, format_func=source_name)
    sql = st.text_area("SQL", value=default_sql_for_source(source_id), height=180)
    auto_refresh = st.checkbox("Enable auto refresh for saved view", value=False)
    refresh_seconds = st.number_input("Refresh interval seconds", min_value=5, value=60, step=5)

    actions = st.columns([0.16, 0.2, 0.64], vertical_alignment="bottom")
    run_query = actions[0].button("Run query", type="primary", icon=":material/play_arrow:", use_container_width=True)
    save_result = actions[1].button("Save as view", icon=":material/save:", use_container_width=True)

    if save_result:
        st.session_state["show_save_view"] = True

    if st.session_state.get("show_save_view"):
        with st.form("save_view_form"):
            view_name = st.text_input("View name", placeholder="Filtered futures")
            submitted = st.form_submit_button("Save view", icon=":material/save:")
        if submitted:
            if not view_name or not sql:
                st.error("View name and SQL are required.")
            else:
                view = save_saved_view(
                    {
                        "name": view_name,
                        "source_id": source_id,
                        "sql": sql,
                        "auto_refresh": bool(auto_refresh),
                        "refresh_seconds": int(refresh_seconds),
                    }
                )
                st.session_state["selected_view_id"] = view["id"]
                st.session_state["selected_source_id"] = None
                st.session_state["page"] = "Views"
                st.session_state["show_save_view"] = False
                st.success("Saved view.")
                st.rerun()

    if run_query:
        source = get_source(source_id)
        if not source:
            st.error("Source not found.")
            return
        try:
            with st.spinner("Loading market data..."):
                df, cached_at, from_cache = cached_sql(source, sql, int(refresh_seconds))
            render_cache_status(cached_at, from_cache)
            render_dataframe(df, "query_result")
        except Exception as exc:
            st.error(str(exc))


def render_source_preview(
    source: dict[str, Any],
    limit: int,
    auto_refresh: bool,
    refresh_seconds: int,
    where_clause: str,
) -> None:
    refresh_seconds = max(refresh_seconds, 5)
    if auto_refresh:
        st.caption(f"Refreshes every {refresh_seconds} seconds.")

    @st.fragment(run_every=f"{refresh_seconds}s")
    def _render() -> None:
        _render_source_preview_body(source, limit, where_clause, refresh_seconds)

    if auto_refresh:
        _render()
    else:
        _render_source_preview_body(source, limit, where_clause, refresh_seconds)


def _render_source_preview_body(source: dict[str, Any], limit: int, where_clause: str, refresh_seconds: int) -> None:
    try:
        with st.spinner("Loading market data..."):
            df, cached_at, from_cache = cached_preview(source, limit, where_clause, refresh_seconds)
        render_cache_status(cached_at, from_cache)
        render_dataframe(df, "source_preview")
    except Exception as exc:
        st.error(str(exc))
