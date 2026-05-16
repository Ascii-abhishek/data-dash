from __future__ import annotations

import time
from typing import Any

import streamlit as st

from tick_ticker_dash.connections.registry import list_source_table_schema, list_source_tables, source_table_alias
from tick_ticker_dash.storage.local_store import (
    list_sources,
    read_context_memory,
    read_source_catalog,
    write_context_memory,
    write_source_catalog,
)


CATALOG_TTL_SECONDS = 30 * 60


@st.fragment(run_every=f"{CATALOG_TTL_SECONDS}s")
def render_catalog_refresh_worker() -> None:
    refresh_stale_catalogs()


def refresh_stale_catalogs(max_age_seconds: int = CATALOG_TTL_SECONDS) -> dict[str, Any]:
    catalog = read_source_catalog()
    changed = False
    for source in list_sources():
        entry = catalog.get(source["id"])
        refreshed_at = float(entry.get("refreshed_at") or 0) if isinstance(entry, dict) else 0
        if time.time() - refreshed_at >= max_age_seconds:
            try:
                catalog[source["id"]] = build_source_catalog(source)
            except Exception as exc:
                catalog[source["id"]] = {
                    "source_id": source["id"],
                    "source_name": source["name"],
                    "source_type": source["type"],
                    "refreshed_at": time.time(),
                    "tables": [],
                    "error": str(exc),
                }
            changed = True

    source_ids = {source["id"] for source in list_sources()}
    for source_id in list(catalog):
        if source_id not in source_ids:
            catalog.pop(source_id, None)
            changed = True

    if changed:
        write_source_catalog(catalog)
        _sync_context_catalog(catalog)
    return catalog


def refresh_source_catalog(source: dict[str, Any]) -> dict[str, Any]:
    catalog = read_source_catalog()
    catalog[source["id"]] = build_source_catalog(source)
    write_source_catalog(catalog)
    _sync_context_catalog(catalog)
    return catalog


def build_source_catalog(source: dict[str, Any]) -> dict[str, Any]:
    table_entries = []
    table_names = list_source_tables(source)
    for table_name in table_names:
        alias = source_table_alias(source) if source["type"] == "cloudflare_r2" else source_table_alias(source, table_name)
        try:
            schema = list_source_table_schema(source, table_name)
            error = None
        except Exception as exc:
            schema = []
            error = str(exc)
        table_entries.append(
            {
                "name": table_name,
                "alias": alias,
                "schema": schema,
                "error": error,
            }
        )

    return {
        "source_id": source["id"],
        "source_name": source["name"],
        "source_type": source["type"],
        "refreshed_at": time.time(),
        "tables": table_entries,
    }


def source_tables_from_catalog(source: dict[str, Any], catalog: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    catalog = catalog or refresh_stale_catalogs()
    entry = catalog.get(source["id"], {})
    tables = entry.get("tables", []) if isinstance(entry, dict) else []
    return tables if isinstance(tables, list) else []


def catalog_for_prompt() -> dict[str, Any]:
    catalog = refresh_stale_catalogs()
    compact: dict[str, Any] = {}
    for source_id, entry in catalog.items():
        if not isinstance(entry, dict):
            continue
        compact[source_id] = {
            "source_name": entry.get("source_name"),
            "source_type": entry.get("source_type"),
            "tables": [
                {
                    "name": table.get("name"),
                    "alias": table.get("alias"),
                    "columns": [
                        {
                            "name": column.get("name"),
                            "type": column.get("type"),
                        }
                        for column in table.get("schema", [])[:80]
                    ],
                }
                for table in entry.get("tables", [])[:40]
            ],
        }
    return compact


def _sync_context_catalog(catalog: dict[str, Any]) -> None:
    context = read_context_memory()
    context["source_catalog"] = catalog
    write_context_memory(context)
