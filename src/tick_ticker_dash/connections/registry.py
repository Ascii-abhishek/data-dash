from __future__ import annotations

import re
from typing import Any, Callable

import polars as pl

from tick_ticker_dash.connections import d1, r2
from tick_ticker_dash.storage.local_store import read_credentials

SourceHandler = dict[str, Callable[..., Any]]


def preview_source(source: dict[str, Any], limit: int = 200, where_clause: str | None = None) -> pl.DataFrame:
    credentials = read_credentials(source)
    return _source_handler(source["type"])["preview"](source, credentials, limit, where_clause)


def test_source_connection(source_type: str, metadata: dict[str, Any], credentials: dict[str, Any]) -> tuple[bool, str]:
    return _source_handler(source_type)["test_connection"](metadata, credentials)


def execute_source_sql(source: dict[str, Any], sql: str) -> pl.DataFrame:
    credentials = read_credentials(source)
    return _source_handler(source["type"])["execute_sql"](source, credentials, sql)


def source_sql_columns(source: dict[str, Any], sql: str) -> list[str]:
    credentials = read_credentials(source)
    handler = _source_handler(source["type"])
    if "sql_columns" in handler:
        return handler["sql_columns"](source, credentials, sql)
    return handler["execute_sql"](source, credentials, sql).columns


def list_source_tables(source: dict[str, Any]) -> list[str]:
    credentials = read_credentials(source)
    return _source_handler(source["type"])["list_tables"](source, credentials)


def list_source_table_schema(source: dict[str, Any], table_name: str) -> list[dict[str, Any]]:
    credentials = read_credentials(source)
    return _source_handler(source["type"])["list_schema"](source, credentials, table_name)


def source_table_alias(source: dict[str, Any], table_name: str | None = None) -> str:
    parts = [source.get("name") or source.get("id") or "source"]
    if table_name:
        parts.append(table_name)
    alias = "__".join(_sql_safe_name(part) for part in parts)
    return alias or "source"


def _sql_safe_name(value: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value)).strip("_").lower()
    if not name:
        return "table"
    if name[0].isdigit():
        return f"t_{name}"
    return name


def _r2_schema(
    source: dict[str, Any],
    credentials: dict[str, Any],
    table_name: str | None = None,
) -> list[dict[str, Any]]:
    schema = r2.scan_source(source, credentials).collect_schema()
    return [{"name": name, "type": str(dtype)} for name, dtype in schema.items()]


def _r2_tables(source: dict[str, Any], credentials: dict[str, Any]) -> list[str]:
    return [source_table_alias(source)]


SOURCE_HANDLERS: dict[str, SourceHandler] = {
    "cloudflare_r2": {
        "preview": r2.preview,
        "test_connection": r2.test_connection,
        "execute_sql": r2.execute_sql,
        "sql_columns": r2.sql_columns,
        "list_tables": _r2_tables,
        "list_schema": _r2_schema,
    },
    "cloudflare_d1": {
        "preview": d1.preview,
        "test_connection": d1.test_connection,
        "execute_sql": d1.execute_sql,
        "list_tables": d1.list_tables,
        "list_schema": d1.list_table_schema,
    },
}


def _source_handler(source_type: str) -> SourceHandler:
    try:
        return SOURCE_HANDLERS[source_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported source type: {source_type}") from exc
