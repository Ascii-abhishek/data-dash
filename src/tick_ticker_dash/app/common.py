from __future__ import annotations

import json
import time
from typing import Any

import polars as pl
import streamlit as st

from tick_ticker_dash.connections.registry import execute_source_sql, preview_source
from tick_ticker_dash.storage.local_store import get_source


def render_field(field: dict[str, Any], key_prefix: str, value: Any = None) -> Any:
    key = f"{key_prefix}_{field['name']}"
    label = field["label"]
    default = field.get("default") if value is None else value
    placeholder = field.get("placeholder")
    help_text = field.get("help")

    if field["type"] == "password":
        return st.text_input(label, value=default or "", type="password", key=key, placeholder=placeholder, help=help_text)
    if field["type"] == "textarea":
        return st.text_area(label, value=default or "", key=key, placeholder=placeholder, help=help_text)
    if field["type"] == "select":
        options = field["options"]
        index = options.index(default) if default in options else 0
        return st.selectbox(label, options, index=index, key=key, help=help_text)
    if field["type"] == "checkbox":
        return st.checkbox(label, value=bool(default), key=key, help=help_text)
    if field["type"] == "number":
        return st.number_input(
            label,
            min_value=int(field.get("min", 0)),
            value=int(default or field.get("min", 0)),
            step=1,
            key=key,
            help=help_text,
        )
    return st.text_input(label, value=default or "", key=key, placeholder=placeholder, help=help_text)


def required_missing(fields: list[dict[str, Any]], values: dict[str, Any]) -> list[str]:
    missing = []
    for field in fields:
        if field.get("required") and values.get(field["name"]) in ("", None):
            missing.append(field["label"])
    return missing


def source_name(source_id: str) -> str:
    source = get_source(source_id)
    return source_display_name(source) if source else source_id


def source_display_name(source: dict[str, Any]) -> str:
    return f"{source['name']} ({source_type_code(source)})"


def source_type_code(source: dict[str, Any]) -> str:
    return {
        "cloudflare_r2": "CFR2",
        "cloudflare_d1": "CFD1",
        "postgres": "PSQL",
    }.get(source.get("type", ""), "DB")


def source_type_icon(source: dict[str, Any]) -> str:
    return f":material/{source_type_icon_name(source)}:"


def source_type_icon_name(source: dict[str, Any]) -> str:
    return {
        "cloudflare_r2": "inventory_2",
        "cloudflare_d1": "database",
        "postgres": "table",
    }.get(source.get("type", ""), "database")


def default_sql_for_source(source_id: str) -> str:
    source = get_source(source_id)
    if not source:
        return ""
    if source["type"] == "cloudflare_r2":
        return "SELECT * FROM data LIMIT 200"
    if source["type"] == "cloudflare_d1":
        return "SELECT name FROM sqlite_schema WHERE type = 'table' ORDER BY name"
    return source["metadata"].get("default_query", "")


def build_table_sql(table_name: str, limit: int = 200, where_clause: str = "") -> str:
    table_ref = quote_sql_identifier(table_name)
    if where_clause:
        return f"SELECT * FROM {table_ref} WHERE {where_clause} LIMIT {limit}"
    return f"SELECT * FROM {table_ref} LIMIT {limit}"


def quote_sql_identifier(identifier: str) -> str:
    return f'"{identifier.replace('"', '""')}"'


def render_empty_state(message: str) -> None:
    st.markdown(f"<div class='empty-state'>{message}</div>", unsafe_allow_html=True)


def cache_key(kind: str, source: dict[str, Any], *parts: Any) -> str:
    payload = {
        "kind": kind,
        "source_id": source["id"],
        "updated_at": source.get("updated_at"),
        "parts": parts,
    }
    return json.dumps(payload, sort_keys=True, default=str)


def get_from_cache(key: str, ttl_seconds: int) -> tuple[pl.DataFrame | None, float | None, bool]:
    item = st.session_state["data_cache"].get(key)
    if not item:
        return None, None, False
    cached_at = float(item["cached_at"])
    if time.time() - cached_at > ttl_seconds:
        st.session_state["data_cache"].pop(key, None)
        return None, None, False
    return item["df"], cached_at, True


def put_in_cache(key: str, df: pl.DataFrame) -> tuple[pl.DataFrame, float, bool]:
    cached_at = time.time()
    st.session_state["data_cache"][key] = {"df": df, "cached_at": cached_at}
    return df, cached_at, False


def cached_preview(
    source: dict[str, Any],
    limit: int,
    where_clause: str,
    ttl_seconds: int,
) -> tuple[pl.DataFrame, float, bool]:
    key = cache_key("preview", source, limit, where_clause)
    cached, cached_at, from_cache = get_from_cache(key, ttl_seconds)
    if cached is not None and cached_at is not None:
        return cached, cached_at, from_cache
    return put_in_cache(key, preview_source(source, limit, where_clause or None))


def cached_sql(source: dict[str, Any], sql: str, ttl_seconds: int) -> tuple[pl.DataFrame, float, bool]:
    key = cache_key("sql", source, sql)
    cached, cached_at, from_cache = get_from_cache(key, ttl_seconds)
    if cached is not None and cached_at is not None:
        return cached, cached_at, from_cache
    return put_in_cache(key, execute_source_sql(source, sql))


def clear_data_cache(source_id: str | None = None) -> None:
    if source_id is None:
        st.session_state["data_cache"] = {}
        return
    st.session_state["data_cache"] = {
        key: value for key, value in st.session_state["data_cache"].items() if f'"source_id": "{source_id}"' not in key
    }


def render_cache_status(cached_at: float, from_cache: bool) -> None:
    age = max(int(time.time() - cached_at), 0)
    label = "Loaded from cache" if from_cache else "Loaded fresh"
    st.caption(f"{label} {age}s ago.")


def render_dataframe(df: pl.DataFrame, key_prefix: str) -> None:
    if df.is_empty():
        st.caption("No rows returned.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True, key=key_prefix)
