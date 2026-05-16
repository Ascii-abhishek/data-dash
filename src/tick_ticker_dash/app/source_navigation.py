from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import streamlit as st


@dataclass(frozen=True)
class SourceNode:
    label: str
    key: str
    kind: str
    icon: str | None = None
    source_id: str | None = None
    table_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def root_node() -> SourceNode:
    return SourceNode(label="Sources", key="sources", kind="root", icon=":material/storage:")


def source_node(source: dict[str, Any]) -> SourceNode:
    return SourceNode(
        label=str(source["name"]),
        key=str(source["id"]),
        kind="source",
        icon=_source_icon(source),
        source_id=str(source["id"]),
        metadata={"source_type": source.get("type")},
    )


def table_node(source: dict[str, Any], table: dict[str, Any]) -> SourceNode:
    table_name = str(table.get("name") or "")
    return SourceNode(
        label=table_name,
        key=table_name,
        kind="table",
        icon=":material/table_rows:",
        source_id=str(source["id"]),
        table_name=table_name,
        metadata={"schema": table.get("schema") or []},
    )


def breadcrumbs_for_node(node: SourceNode, source: dict[str, Any] | None = None) -> list[SourceNode]:
    crumbs = [root_node()]
    if source:
        crumbs.append(source_node(source))
    elif node.kind == "source":
        crumbs.append(node)
    if node.kind == "table":
        crumbs.append(node)
    return crumbs


def select_node(node: SourceNode) -> None:
    if node.kind == "root":
        st.session_state["page"] = "Sources"
        st.session_state["selected_source_id"] = None
        st.session_state["selected_view_id"] = None
        st.session_state["sources_browser_source_id"] = None
        return

    if node.kind == "source":
        if node.metadata.get("source_type") == "cloudflare_r2":
            st.session_state["page"] = "Views"
            st.session_state["selected_source_id"] = node.source_id
            st.session_state["selected_view_id"] = None
            st.session_state["sources_browser_source_id"] = None
            return

        st.session_state["page"] = "Sources"
        st.session_state["selected_source_id"] = None
        st.session_state["selected_view_id"] = None
        st.session_state["sources_browser_source_id"] = node.source_id
        return

    if node.kind == "table":
        st.session_state["page"] = "Views"
        st.session_state["selected_source_id"] = node.source_id
        st.session_state["selected_view_id"] = None
        st.session_state["sources_browser_source_id"] = node.source_id
        if node.source_id and node.table_name:
            st.session_state[f"d1_selected_table_{node.source_id}"] = node.table_name


def _source_icon(source: dict[str, Any]) -> str:
    return {
        "cloudflare_r2": ":material/inventory_2:",
        "cloudflare_d1": ":material/database:",
    }.get(str(source.get("type")), ":material/database:")
