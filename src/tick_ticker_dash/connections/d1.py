from __future__ import annotations

import uuid
from typing import Any

import httpx
import polars as pl


def execute_sql(source: dict[str, Any], credentials: dict[str, Any], sql: str) -> pl.DataFrame:
    metadata = source["metadata"]
    database_id = resolve_database_id(metadata, credentials)
    url = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{metadata['account_id']}/d1/database/{database_id}/query"
    )
    response = httpx.post(
        url,
        headers={"Authorization": f"Bearer {credentials['api_token']}"},
        json={"sql": sql},
        timeout=60,
    )
    payload = response.json()

    if response.is_error:
        message = _cloudflare_error_message(payload) or response.text
        raise RuntimeError(f"D1 query failed ({response.status_code}): {message}")

    if not payload.get("success", False):
        raise RuntimeError(_cloudflare_error_message(payload) or "D1 query failed")

    results: list[dict[str, Any]] = []
    for item in payload.get("result", []):
        results.extend(item.get("results") or [])

    return pl.DataFrame(results) if results else pl.DataFrame()


def resolve_database_id(metadata: dict[str, Any], credentials: dict[str, Any]) -> str:
    if metadata.get("database_id"):
        return str(metadata["database_id"])

    database_name = str(metadata.get("database_name") or "").strip()
    if not database_name:
        raise ValueError("D1 database name is required.")
    if _looks_like_uuid(database_name):
        return database_name

    url = f"https://api.cloudflare.com/client/v4/accounts/{metadata['account_id']}/d1/database"
    response = httpx.get(
        url,
        headers={"Authorization": f"Bearer {credentials['api_token']}"},
        params={"name": database_name, "per_page": 100},
        timeout=60,
    )
    payload = response.json()

    if response.is_error:
        message = _cloudflare_error_message(payload) or response.text
        raise RuntimeError(f"D1 database lookup failed ({response.status_code}): {message}")

    if not payload.get("success", False):
        raise RuntimeError(_cloudflare_error_message(payload) or "D1 database lookup failed")

    databases = payload.get("result") or []
    match = next((item for item in databases if item.get("name") == database_name), None)
    if not match:
        raise ValueError(f"D1 database not found: {database_name}")
    database_id = match.get("uuid") or match.get("id")
    if not database_id:
        raise ValueError(f"D1 database lookup did not return an ID for: {database_name}")
    return str(database_id)


def _looks_like_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def _cloudflare_error_message(payload: dict[str, Any]) -> str:
    errors = payload.get("errors") or []
    messages = [str(error.get("message")) for error in errors if error.get("message")]
    return "; ".join(messages)


def test_connection(metadata: dict[str, Any], credentials: dict[str, Any]) -> tuple[bool, str]:
    source = {"metadata": metadata}
    execute_sql(source, credentials, "SELECT 1 AS ok")
    return True, "Connected. D1 returned a test query successfully."


def list_tables(source: dict[str, Any], credentials: dict[str, Any]) -> list[str]:
    df = execute_sql(
        source,
        credentials,
        "SELECT name FROM sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name",
    )
    if df.is_empty() or "name" not in df.columns:
        return []
    return [str(name) for name in df.get_column("name").to_list() if name]


def preview(
    source: dict[str, Any],
    credentials: dict[str, Any],
    limit: int = 200,
    where_clause: str | None = None,
) -> pl.DataFrame:
    query = source["metadata"].get("default_query") or "SELECT name FROM sqlite_schema WHERE type = 'table' ORDER BY name"
    base_query = query.rstrip(";")
    if where_clause:
        base_query = f"SELECT * FROM ({base_query}) WHERE {where_clause}"
    limited_query = base_query if "limit" in base_query.lower() else f"{base_query} LIMIT {limit}"
    return execute_sql(source, credentials, limited_query)
