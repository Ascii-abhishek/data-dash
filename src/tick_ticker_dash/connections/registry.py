from __future__ import annotations

import re
from typing import Any

import polars as pl

from tick_ticker_dash.connections import d1, r2
from tick_ticker_dash.storage.local_store import read_credentials


def preview_source(source: dict[str, Any], limit: int = 200, where_clause: str | None = None) -> pl.DataFrame:
    credentials = read_credentials(source)
    if source["type"] == "cloudflare_r2":
        return r2.preview(source, credentials, limit, where_clause)
    if source["type"] == "cloudflare_d1":
        return d1.preview(source, credentials, limit, where_clause)
    raise ValueError(f"Unsupported source type: {source['type']}")


def test_source_connection(source_type: str, metadata: dict[str, Any], credentials: dict[str, Any]) -> tuple[bool, str]:
    if source_type == "cloudflare_r2":
        return r2.test_connection(metadata, credentials)
    if source_type == "cloudflare_d1":
        return d1.test_connection(metadata, credentials)
    raise ValueError(f"Unsupported source type: {source_type}")


def execute_source_sql(source: dict[str, Any], sql: str) -> pl.DataFrame:
    credentials = read_credentials(source)
    if source["type"] == "cloudflare_r2":
        return r2.execute_sql(source, credentials, sql)
    if source["type"] == "cloudflare_d1":
        return d1.execute_sql(source, credentials, sql)
    raise ValueError(f"Unsupported source type: {source['type']}")


def execute_cross_source_sql(sources: list[dict[str, Any]], sql: str) -> pl.DataFrame:
    context = pl.SQLContext(eager=False)
    registered: list[str] = []

    for source in sources:
        credentials = read_credentials(source)
        source_alias = source_table_alias(source)
        if source["type"] == "cloudflare_r2":
            context.register(source_alias, r2.scan_source(source, credentials))
            registered.append(source_alias)
            continue

        if source["type"] == "cloudflare_d1":
            default_query = str(source["metadata"].get("default_query") or "").strip()
            if default_query and _identifier_in_sql(source_alias, sql):
                context.register(source_alias, d1.execute_sql(source, credentials, default_query.rstrip(";")))
                registered.append(source_alias)

            for table_name in d1.list_tables(source, credentials):
                table_alias = source_table_alias(source, table_name)
                if not _identifier_in_sql(table_alias, sql):
                    continue
                query = f"SELECT * FROM {_quote_sql_identifier(table_name)}"
                context.register(table_alias, d1.execute_sql(source, credentials, query))
                registered.append(table_alias)
            continue

        raise ValueError(f"Unsupported source type: {source['type']}")

    if not registered:
        raise ValueError("No queryable tables were registered from the configured sources.")

    result = context.execute(sql)
    if isinstance(result, pl.LazyFrame):
        return result.collect()
    return result


def list_source_tables(source: dict[str, Any]) -> list[str]:
    credentials = read_credentials(source)
    if source["type"] == "cloudflare_d1":
        return d1.list_tables(source, credentials)
    if source["type"] == "cloudflare_r2":
        return [source_table_alias(source)]
    raise ValueError(f"Table listing is unsupported for source type: {source['type']}")


def list_source_table_schema(source: dict[str, Any], table_name: str) -> list[dict[str, Any]]:
    credentials = read_credentials(source)
    if source["type"] == "cloudflare_d1":
        return d1.list_table_schema(source, credentials, table_name)
    if source["type"] == "cloudflare_r2":
        return _r2_schema(source, credentials)
    raise ValueError(f"Schema listing is unsupported for source type: {source['type']}")


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


def _quote_sql_identifier(identifier: str) -> str:
    return f'"{identifier.replace('"', '""')}"'


def _identifier_in_sql(identifier: str, sql: str) -> bool:
    quoted = f'"{identifier.replace('"', '""')}"'
    return bool(re.search(rf"(?<![a-zA-Z0-9_]){re.escape(identifier)}(?![a-zA-Z0-9_])", sql)) or quoted in sql


def _r2_schema(source: dict[str, Any], credentials: dict[str, Any]) -> list[dict[str, Any]]:
    schema = r2.scan_source(source, credentials).collect_schema()
    return [{"name": name, "type": str(dtype)} for name, dtype in schema.items()]
