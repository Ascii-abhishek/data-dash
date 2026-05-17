from __future__ import annotations

from typing import Any

import polars as pl
import streamlit as st

from tick_ticker_dash.app.common import (
    cached_preview,
    cached_sql,
    build_table_sql,
    clear_data_cache,
    default_sql_for_source,
    render_cache_status,
    render_dataframe,
    render_empty_state,
    normalize_where_clause,
    source_display_name,
    source_name,
    source_type_icon,
    source_type_icon_name,
)
from tick_ticker_dash.app.controls import render_control_panel
from tick_ticker_dash.app.query_execution import DEFAULT_QUERY_ROW_LIMIT, persist_query_result, prepare_read_only_sql
from tick_ticker_dash.app.source_navigation import SourceNode, breadcrumbs_for_node, root_node, select_node, source_node, table_node
from tick_ticker_dash.app.source_catalog import refresh_stale_catalogs, source_tables_from_catalog
from tick_ticker_dash.app.state import open_favorite
from tick_ticker_dash.app.styles import action_link, page_title
from tick_ticker_dash.storage.local_store import (
    get_saved_view,
    get_source,
    is_favorite,
    list_favorites,
    list_saved_views,
    list_sources,
    read_query_state,
    save_saved_view,
    toggle_favorite,
    write_query_state,
)


QUERY_TOOL_ROW_LIMIT = DEFAULT_QUERY_ROW_LIMIT


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
    render_data_source_view(source)


def render_data_source_view(source: dict[str, Any]) -> None:
    table_name = _selected_table_for_data_view(source)
    _render_data_view_breadcrumbs(source, table_name)
    if source["type"] == "cloudflare_d1" and not table_name:
        st.info("Select a table from All sources to preview this D1 source.")
        if st.button("Open tables", icon=":material/table_rows:", width="stretch"):
            st.session_state["page"] = "Sources"
            st.session_state["sources_browser_source_id"] = source["id"]
            st.rerun()
        return

    if table_name and source["type"] == "cloudflare_d1":
        st.markdown(f"<div class='section-label'>Table: {table_name}</div>", unsafe_allow_html=True)

    default_refresh_seconds = max(int(source["metadata"].get("refresh_seconds", 60)), 5)
    controls = render_control_panel(
        "Preview controls",
        [
            {"id": "limit", "kind": "number", "label": "Rows", "min_value": 1, "max_value": 10000, "value": 200, "step": 50},
            {"id": "auto_refresh", "kind": "checkbox", "label": "Auto refresh", "value": False},
            {
                "id": "refresh_seconds",
                "kind": "number",
                "label": "Interval (s)",
                "min_value": 5,
                "value": default_refresh_seconds,
                "step": 5,
            },
            {"id": "refresh_now", "kind": "button", "label": "Refresh now", "icon": ":material/refresh:"},
        ],
        key_prefix=f"source_preview_{source['id']}_{table_name or 'data'}",
    )
    if controls["refresh_now"]:
        clear_data_cache(source["id"])
    where_clause = st.text_input(
        "WHERE condition",
        placeholder="<col_name> <operator> <value> (e.g. timestamp > '2024-01-01')",
        key=f"source_preview_where_{source['id']}_{table_name or 'data'}",
    )
    render_table_preview(
        source,
        table_name,
        int(controls["limit"]),
        bool(controls["auto_refresh"]),
        int(controls["refresh_seconds"]),
        normalize_where_clause(where_clause),
    )


def _render_data_view_breadcrumbs(source: dict[str, Any], table_name: str | None) -> None:
    current = (
        SourceNode(label=table_name or "Select table", key=table_name or "select-table", kind="table", source_id=source["id"], table_name=table_name)
        if source["type"] == "cloudflare_d1"
        else source_node(source)
    )
    _render_breadcrumbs(breadcrumbs_for_node(current, source))


def _render_breadcrumbs(items: list[SourceNode]) -> None:
    ratios: list[float] = []
    for index, item in enumerate(items):
        if index:
            ratios.append(0.035)
        ratios.append(min(max(len(item.label) * 0.012, 0.16), 0.34))

    columns = st.columns(ratios, gap="small", vertical_alignment="center")
    column_index = 0
    for index, item in enumerate(items):
        if index:
            columns[column_index].markdown("<div class='breadcrumb-separator'>/</div>", unsafe_allow_html=True)
            column_index += 1

        if index < len(items) - 1:
            if columns[column_index].button(
                item.label,
                icon=item.icon,
                key=f"breadcrumb_{item.kind}_{item.source_id or 'root'}_{item.key}",
                width="stretch",
            ):
                select_node(item)
                st.rerun()
        else:
            columns[column_index].markdown(f"<div class='breadcrumb-current'>{item.label}</div>", unsafe_allow_html=True)
        column_index += 1


def render_sources_page() -> None:
    page_title("Sources", "storage")
    sources = list_sources()
    if not sources:
        render_empty_state("Add a source to browse its tables.")
        return

    catalog = refresh_stale_catalogs()
    selected_source_id = st.session_state.get("sources_browser_source_id")
    selected_source = get_source(selected_source_id) if selected_source_id else None

    if selected_source:
        _render_source_tables_grid(selected_source, catalog)
        return

    st.markdown("<div class='source-browser-grid'>", unsafe_allow_html=True)
    columns = st.columns(3, gap="medium")
    for index, source in enumerate(sources):
        with columns[index % 3]:
            table_count = len(source_tables_from_catalog(source, catalog))
            label = f"{source_display_name(source)}\n\n{table_count or 1} table{'s' if (table_count or 1) != 1 else ''}"
            if st.button(
                label,
                key=f"sources_grid_source_{source['id']}",
                icon=source_type_icon(source),
                width="stretch",
            ):
                select_node(source_node(source))
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def _render_source_tables_grid(source: dict[str, Any], catalog: dict[str, Any]) -> None:
    _render_breadcrumbs(breadcrumbs_for_node(source_node(source)))

    tables = source_tables_from_catalog(source, catalog)
    if not tables:
        render_empty_state("No tables found for this source.")
        return

    st.markdown("<div class='source-browser-grid'>", unsafe_allow_html=True)
    columns = st.columns(3, gap="medium")
    for index, table in enumerate(tables):
        node = table_node(source, table)
        schema = node.metadata.get("schema") or []
        with columns[index % 3]:
            label = f"{node.label}\n\n{len(schema)} columns"
            if st.button(
                label,
                key=f"sources_grid_table_{source['id']}_{node.key}",
                icon=node.icon,
                width="stretch",
            ):
                select_node(node)
                st.session_state[f"d1_tables_{source['id']}"] = [str(item.get("name")) for item in tables if item.get("name")]
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_view_index(views: list[dict[str, Any]]) -> None:
    top = st.columns([0.18, 0.82], vertical_alignment="bottom")
    if top[0].button("Add view", type="primary", icon=":material/add:", width="stretch"):
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
    controls = render_control_panel(
        "View controls",
        [
            {"id": "auto_refresh", "kind": "checkbox", "label": "Auto refresh", "value": bool(view.get("auto_refresh", False))},
            {
                "id": "refresh_seconds",
                "kind": "number",
                "label": "Interval (s)",
                "min_value": 5,
                "value": max(int(view.get("refresh_seconds", 60)), 5),
                "step": 5,
            },
            {"id": "refresh_now", "kind": "button", "label": "Refresh now", "icon": ":material/refresh:"},
        ],
        key_prefix=f"saved_view_{view_id}",
    )
    auto_refresh = bool(controls["auto_refresh"])
    refresh_seconds = int(controls["refresh_seconds"])
    if controls["refresh_now"]:
        clear_data_cache(source["id"])

    @st.fragment(run_every=f"{refresh_seconds}s")
    def _render() -> None:
        _render_saved_view_body(source, view, refresh_seconds)

    if auto_refresh:
        _render()
    else:
        _render_saved_view_body(source, view, None)


def _render_saved_view_body(source: dict[str, Any], view: dict[str, Any], ttl_seconds: int | None) -> None:
    try:
        safe_sql = prepare_read_only_sql(view["sql"], QUERY_TOOL_ROW_LIMIT)
        with st.spinner("Loading market data..."):
            df, cached_at, from_cache, duration_seconds = cached_sql(source, safe_sql.execution_sql, ttl_seconds)
        render_cache_status(cached_at, from_cache, duration_seconds)
        if safe_sql.was_capped:
            st.caption(f"Result capped at {QUERY_TOOL_ROW_LIMIT:,} rows because the saved query did not include LIMIT.")
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
                width="stretch",
            ):
                open_favorite(favorite)
                st.rerun()
            if columns[2].button(
                "Unstar",
                key=f"unstar_all_favorite_{favorite['key']}",
                icon=":material/star:",
                width="stretch",
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
    selected_query_source_id = selected_id if selected_id in source_ids else source_ids[0]
    if st.session_state.get("query_tool_source_id") not in source_ids:
        st.session_state["query_tool_source_id"] = selected_query_source_id
    source_id = st.selectbox("Data source", source_ids, format_func=source_name, key="query_tool_source_id")
    st.session_state["selected_source_id"] = source_id

    persisted_state = read_query_state()
    sql_key = f"query_tool_sql_{source_id}"
    if sql_key not in st.session_state:
        st.session_state[sql_key] = persisted_state.get("drafts", {}).get(source_id) or default_sql_for_source(source_id)
    sql = st.text_area(
        "SQL",
        height=180,
        key=sql_key,
        placeholder="Write SQL here.",
    )
    _save_query_draft(source_id, sql)

    actions = render_control_panel(
        "Query controls",
        [
            {"id": "run_query", "kind": "button", "label": "Run query", "type": "primary", "icon": ":material/play_arrow:"},
            {"id": "save_result", "kind": "button", "label": "Save as view", "icon": ":material/save:"},
            {"id": "auto_refresh", "kind": "checkbox", "label": "Auto refresh", "value": False},
            {"id": "refresh_seconds", "kind": "number", "label": "Interval (s)", "min_value": 5, "value": 60, "step": 5},
        ],
        key_prefix=f"query_tool_{source_id}",
    )
    run_query = bool(actions["run_query"])
    save_result = bool(actions["save_result"])
    auto_refresh = bool(actions["auto_refresh"])
    refresh_seconds = int(actions["refresh_seconds"])

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
                try:
                    safe_sql = prepare_read_only_sql(sql, QUERY_TOOL_ROW_LIMIT)
                    view = save_saved_view(
                        {
                            "name": view_name,
                            "source_id": source_id,
                            "sql": safe_sql.original_sql,
                            "auto_refresh": False,
                            "refresh_seconds": 60,
                        }
                    )
                except Exception as exc:
                    st.error(str(exc))
                    return
                st.session_state["selected_view_id"] = view["id"]
                st.session_state["selected_source_id"] = None
                st.session_state["page"] = "Views"
                st.session_state["show_save_view"] = False
                st.success("Saved view.")
                st.rerun()

    if auto_refresh:
        _render_auto_query_result(source_id, sql, int(refresh_seconds))
    elif run_query:
        _render_query_result(source_id, sql, int(refresh_seconds))
    else:
        _render_persisted_query_result(source_id, sql)


def _save_query_draft(source_id: str, sql: str) -> None:
    state = read_query_state()
    drafts = state.setdefault("drafts", {})
    if drafts.get(source_id) == sql:
        return
    drafts[source_id] = sql
    write_query_state(state)


def _render_auto_query_result(source_id: str, sql: str, refresh_seconds: int) -> None:
    @st.fragment(run_every=f"{max(refresh_seconds, 5)}s")
    def _render() -> None:
        _render_query_result(source_id, sql, refresh_seconds)

    _render()


def _render_query_result(source_id: str, sql: str, refresh_seconds: int) -> None:
    source = get_source(source_id)
    if not source:
        st.error("Source not found.")
        return
    try:
        safe_sql = prepare_read_only_sql(sql, QUERY_TOOL_ROW_LIMIT)
        with st.spinner("Loading market data..."):
            df, cached_at, from_cache, duration_seconds = cached_sql(source, safe_sql.execution_sql, refresh_seconds)
        persist_query_result(source_id, sql, df, cached_at)
        render_cache_status(cached_at, from_cache, duration_seconds)
        if safe_sql.was_capped:
            st.caption(f"Result capped at {QUERY_TOOL_ROW_LIMIT:,} rows because the query did not include LIMIT.")
        render_dataframe(df, "query_result")
    except Exception as exc:
        st.error(str(exc))


def _render_persisted_query_result(source_id: str, sql: str) -> None:
    result = read_query_state().get("last_result", {})
    if result.get("source_id") != source_id or result.get("sql") != sql:
        return
    rows = result.get("rows") or []
    if not rows:
        st.caption("Last result had no rows.")
        return
    cached_at = float(result.get("cached_at") or 0)
    if cached_at:
        render_cache_status(cached_at, True)
    render_dataframe(pl.DataFrame(rows), "query_result")
    if result.get("truncated"):
        st.caption("Persisted result preview is limited to the first 5000 rows.")


def _selected_table_for_data_view(source: dict[str, Any]) -> str | None:
    if source["type"] == "cloudflare_r2":
        return None
    if source["type"] != "cloudflare_d1":
        return None

    selected_key = f"d1_selected_table_{source['id']}"
    selected_table = st.session_state.get(selected_key)
    catalog = refresh_stale_catalogs()
    tables = source_tables_from_catalog(source, catalog)
    table_names = [str(table.get("name")) for table in tables if table.get("name")]
    if selected_table in table_names:
        st.session_state[f"d1_tables_{source['id']}"] = table_names
        return str(selected_table)
    if table_names:
        st.session_state[selected_key] = table_names[0]
        st.session_state[f"d1_tables_{source['id']}"] = table_names
        return table_names[0]
    return None


def render_table_preview(
    source: dict[str, Any],
    table_name: str | None,
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
        _render_table_preview_body(source, table_name, limit, where_clause, refresh_seconds)

    if auto_refresh:
        _render()
    else:
        _render_table_preview_body(source, table_name, limit, where_clause, refresh_seconds)


def _render_table_preview_body(
    source: dict[str, Any],
    table_name: str | None,
    limit: int,
    where_clause: str,
    refresh_seconds: int,
) -> None:
    try:
        with st.spinner("Loading market data..."):
            if source["type"] == "cloudflare_d1":
                if not table_name:
                    st.caption("Select a table to preview rows.")
                    return
                sql = build_table_sql(table_name, limit, where_clause)
                df, cached_at, from_cache, duration_seconds = cached_sql(source, sql, refresh_seconds)
            else:
                df, cached_at, from_cache, duration_seconds = cached_preview(source, limit, where_clause, refresh_seconds)
        render_cache_status(cached_at, from_cache, duration_seconds)
        render_dataframe(df, "source_preview")
    except Exception as exc:
        st.error(str(exc))
