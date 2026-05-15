from __future__ import annotations

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


def list_source_tables(source: dict[str, Any]) -> list[str]:
    credentials = read_credentials(source)
    if source["type"] == "cloudflare_d1":
        return d1.list_tables(source, credentials)
    raise ValueError(f"Table listing is unsupported for source type: {source['type']}")
