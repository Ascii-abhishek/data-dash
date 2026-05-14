from __future__ import annotations

from typing import Any

import streamlit as st

from tick_ticker_dash.app.common import (
    clear_data_cache,
    default_sql_for_source,
    render_field,
    required_missing,
    source_name,
)
from tick_ticker_dash.app.graphs import (
    chart_type_label,
    chart_type_options,
    render_chart_config_controls,
    validate_chart_config,
)
from tick_ticker_dash.app.styles import material_icon
from tick_ticker_dash.config.source_schemas import SOURCE_TYPES, source_type_options
from tick_ticker_dash.connections import r2
from tick_ticker_dash.connections.registry import execute_source_sql, test_source_connection
from tick_ticker_dash.storage.local_store import (
    delete_source,
    get_source,
    list_dashboard_names,
    list_sources,
    read_credentials,
    save_dashboard,
    save_dashboard_card,
    save_source,
    update_source,
)


@st.dialog("Data source")
def render_source_dialog(source_id: str | None = None) -> None:
    existing = get_source(source_id) if source_id else None
    existing_credentials = read_credentials(existing) if existing else {}
    source_labels = source_type_options()
    source_keys = list(source_labels.keys())
    default_source_type = existing["type"] if existing else source_keys[0]
    source_type = st.selectbox(
        "Source",
        options=source_keys,
        index=source_keys.index(default_source_type),
        format_func=lambda value: source_labels[value],
    )
    schema = SOURCE_TYPES[source_type]
    metadata_values = existing.get("metadata", {}) if existing and existing["type"] == source_type else {}
    if source_type == "cloudflare_r2":
        metadata_values = r2.normalize_metadata(metadata_values)
    if source_type == "cloudflare_d1" and "database_name" not in metadata_values:
        metadata_values = {**metadata_values, "database_name": metadata_values.get("database_id", "")}
    credential_values = existing_credentials if existing and existing["type"] == source_type else {}

    with st.form("source_form", clear_on_submit=False):
        name = st.text_input("Name", value=existing["name"] if existing else "", placeholder="NIFTY options R2")
        st.markdown("##### Connection")
        metadata = {
            field["name"]: render_field(field, f"metadata_{source_id or 'new'}", metadata_values.get(field["name"]))
            for field in schema["metadata_fields"]
        }
        if source_type == "cloudflare_r2" and metadata.get("bucket") and metadata.get("file_pattern"):
            normalized = r2.normalize_metadata(metadata)
            st.caption(f"R2 URI: `{r2.source_uri(normalized)}`")
            if normalized["file_pattern"] != metadata["file_pattern"]:
                st.info("The bucket name was removed from the object key pattern for this source.")
        st.markdown("##### Credentials")
        credentials = {
            field["name"]: render_field(field, f"credentials_{source_id or 'new'}", credential_values.get(field["name"]))
            for field in schema["credential_fields"]
        }

        left, middle, right = st.columns(3)
        tested = left.form_submit_button("Test", icon=":material/network_check:", use_container_width=True)
        submitted = middle.form_submit_button(
            "Save" if existing else "Add",
            icon=":material/save:" if existing else ":material/add:",
            use_container_width=True,
        )
        cancelled = right.form_submit_button("Cancel", icon=":material/close:", use_container_width=True)

    if cancelled:
        st.rerun()

    if tested or submitted:
        missing = required_missing(schema["metadata_fields"], metadata)
        missing.extend(required_missing(schema["credential_fields"], credentials))
        if not name:
            missing.insert(0, "Name")
        if missing:
            st.error(f"Missing required fields: {', '.join(missing)}")
            return
        if source_type == "cloudflare_r2":
            metadata = r2.normalize_metadata(metadata)

    if tested:
        try:
            ok, message = test_source_connection(source_type, metadata, credentials)
            if ok:
                st.success(message)
        except Exception as exc:
            st.error(f"Connection failed: {exc}")
        return

    if submitted:
        if existing:
            update_source(existing["id"], name, source_type, metadata, credentials)
        else:
            save_source(name, source_type, metadata, credentials)
        clear_data_cache()
        st.success("Source saved.")
        st.rerun()

    if existing:
        st.divider()
        st.warning("Deleting this source also removes saved views and dashboard cards that use it.")
        if st.button("Delete source", icon=":material/delete:", use_container_width=True):
            delete_source(existing["id"])
            if st.session_state.get("selected_source_id") == existing["id"]:
                st.session_state["selected_source_id"] = None
            clear_data_cache()
            st.success("Source deleted.")
            st.rerun()


@st.dialog("Create dashboard")
def render_create_dashboard_dialog() -> None:
    st.markdown(f"### {material_icon('dashboard')} New dashboard", unsafe_allow_html=True)
    with st.form("create_dashboard_form"):
        name = st.text_input("Dashboard name", placeholder="Market overview")
        submitted = st.form_submit_button("Create", type="primary", icon=":material/add:", use_container_width=True)

    if submitted:
        if not name:
            st.error("Dashboard name is required.")
            return
        dashboard = save_dashboard(name)
        st.session_state["selected_dashboard_name"] = dashboard["name"]
        st.success("Dashboard created.")
        st.rerun()


@st.dialog("Add dashboard card")
def render_dashboard_dialog(dashboard_name: str | None = None) -> None:
    sources = list_sources()
    if not sources:
        st.info("Add a data source first.")
        return

    dashboard_names = list_dashboard_names()
    locked_dashboard = dashboard_name or st.session_state.get("selected_dashboard_name")
    st.markdown(f"### {material_icon('add_chart')} Add card", unsafe_allow_html=True)

    dashboard_choice = locked_dashboard or st.selectbox("Dashboard", ["Create new"] + dashboard_names)
    new_dashboard_name = ""
    if locked_dashboard:
        st.info(f"This card will be added to dashboard: {locked_dashboard}")
    elif dashboard_choice == "Create new":
        new_dashboard_name = st.text_input("Dashboard name", placeholder="Market overview")

    name = st.text_input("Card name", placeholder="Latest options rows")
    card_type = st.selectbox("Card type", chart_type_options(), format_func=chart_type_label)
    source_id = st.selectbox("Data source", [source["id"] for source in sources], format_func=source_name)
    sql = st.text_area("SQL query", value=default_sql_for_source(source_id), height=140)

    columns_key = "dashboard_card_columns"
    error_key = "dashboard_card_field_error"
    if st.button("Load fields", icon=":material/view_column:", use_container_width=True):
        source = get_source(source_id)
        if not source:
            st.error("Source not found.")
        else:
            try:
                df = execute_source_sql(source, sql)
                st.session_state[columns_key] = {
                    "source_id": source_id,
                    "sql": sql,
                    "columns": df.columns,
                }
                st.session_state.pop(error_key, None)
            except Exception as exc:
                st.session_state[error_key] = str(exc)

    if st.session_state.get(error_key):
        st.error(st.session_state[error_key])

    loaded = st.session_state.get(columns_key, {})
    columns = loaded.get("columns", []) if loaded.get("source_id") == source_id and loaded.get("sql") == sql else []
    if card_type != "table" and not columns:
        st.caption("Load fields to configure axes, color, and custom chart columns.")

    chart_config = render_chart_config_controls(card_type, columns, "new_dashboard_card")
    left, right = st.columns(2)
    submitted = left.button("Add", icon=":material/add_chart:", use_container_width=True)
    cancelled = right.button("Cancel", icon=":material/close:", use_container_width=True)

    if cancelled:
        st.rerun()

    if submitted:
        selected_dashboard_name = new_dashboard_name if dashboard_choice == "Create new" else dashboard_choice
        if not selected_dashboard_name or not name or not sql:
            st.error("Dashboard name, card name, and SQL query are required.")
            return
        missing = validate_chart_config(card_type, chart_config)
        if missing:
            st.error(f"Missing chart fields: {', '.join(missing)}")
            return
        save_dashboard_card(
            {
                "dashboard_name": selected_dashboard_name,
                "name": name,
                "type": card_type,
                "chart_config": _clean_config(chart_config),
                "source_id": source_id,
                "sql": sql,
            }
        )
        st.session_state["selected_dashboard_name"] = selected_dashboard_name
        st.session_state.pop(columns_key, None)
        st.session_state.pop(error_key, None)
        st.success("Dashboard card saved.")
        st.rerun()


def _clean_config(config: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in config.items() if value not in ("", None)}
