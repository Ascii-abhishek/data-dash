from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tick_ticker_dash.config.settings import settings

SOURCES_FILE = settings.connections_dir / "sources.json"
UI_STATE_DIR = settings.ui_dir
DASHBOARDS_FILE = UI_STATE_DIR / "dashboards.json"
VIEWS_FILE = UI_STATE_DIR / "views.json"
QUERY_STATE_FILE = UI_STATE_DIR / "query_state.json"
SOURCE_CATALOG_FILE = UI_STATE_DIR / "source_catalog.json"
PROMPT_FILE = settings.memory_dir / "prompt.json"
CONTEXT_FILE = settings.memory_dir / "context.json"
SESSION_FILE = settings.memory_dir / "session.json"


def ensure_storage() -> None:
    settings.connections_dir.mkdir(parents=True, exist_ok=True)
    settings.credentials_dir.mkdir(parents=True, exist_ok=True)
    UI_STATE_DIR.mkdir(parents=True, exist_ok=True)
    settings.memory_dir.mkdir(parents=True, exist_ok=True)
    if not SOURCES_FILE.exists():
        write_json(SOURCES_FILE, [])
    if not DASHBOARDS_FILE.exists():
        write_json(DASHBOARDS_FILE, [])
    if not VIEWS_FILE.exists():
        write_json(VIEWS_FILE, [])
    if not QUERY_STATE_FILE.exists():
        write_json(QUERY_STATE_FILE, {})
    if not SOURCE_CATALOG_FILE.exists():
        write_json(SOURCE_CATALOG_FILE, {})
    if not PROMPT_FILE.exists():
        write_json(
            PROMPT_FILE,
            {
                "system": (
                    "You are a concise data analyst for Tick Ticker Dash. Use the supplied source catalog, "
                    "schema context, and recent chat history to answer. Be clear when data is unavailable."
                )
            },
        )
    if not CONTEXT_FILE.exists():
        write_json(CONTEXT_FILE, {"notes": [], "source_catalog": {}})
    if not SESSION_FILE.exists():
        write_json(SESSION_FILE, [])


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, default=str, indent=2, sort_keys=True))


def read_query_state() -> dict[str, Any]:
    ensure_storage()
    state = read_json(QUERY_STATE_FILE, {})
    return state if isinstance(state, dict) else {}


def write_query_state(state: dict[str, Any]) -> None:
    ensure_storage()
    write_json(QUERY_STATE_FILE, state)


def read_source_catalog() -> dict[str, Any]:
    ensure_storage()
    catalog = read_json(SOURCE_CATALOG_FILE, {})
    return catalog if isinstance(catalog, dict) else {}


def write_source_catalog(catalog: dict[str, Any]) -> None:
    ensure_storage()
    write_json(SOURCE_CATALOG_FILE, catalog)


def read_prompt_memory() -> dict[str, Any]:
    ensure_storage()
    prompt = read_json(PROMPT_FILE, {})
    return prompt if isinstance(prompt, dict) else {}


def read_context_memory() -> dict[str, Any]:
    ensure_storage()
    context = read_json(CONTEXT_FILE, {})
    return context if isinstance(context, dict) else {}


def write_context_memory(context: dict[str, Any]) -> None:
    ensure_storage()
    write_json(CONTEXT_FILE, context)


def read_chat_session() -> list[dict[str, Any]]:
    ensure_storage()
    session = read_json(SESSION_FILE, [])
    return session if isinstance(session, list) else []


def write_chat_session(session: list[dict[str, Any]]) -> None:
    ensure_storage()
    write_json(SESSION_FILE, session)


def make_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    slug = slug or "source"
    return f"{slug}-{uuid.uuid4().hex[:8]}"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def list_sources() -> list[dict[str, Any]]:
    ensure_storage()
    return read_json(SOURCES_FILE, [])


def get_source(source_id: str) -> dict[str, Any] | None:
    return next((source for source in list_sources() if source["id"] == source_id), None)


def save_source(name: str, source_type: str, metadata: dict[str, Any], credentials: dict[str, Any]) -> dict[str, Any]:
    ensure_storage()
    source_id = make_id(name)
    source = {
        "id": source_id,
        "name": name,
        "type": source_type,
        "metadata": metadata,
        "credential_file": f"{source_id}.json",
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    sources = list_sources()
    sources.append(source)
    write_json(SOURCES_FILE, sources)
    write_json(settings.credentials_dir / source["credential_file"], credentials)
    return source


def update_source(
    source_id: str,
    name: str,
    source_type: str,
    metadata: dict[str, Any],
    credentials: dict[str, Any],
) -> dict[str, Any]:
    ensure_storage()
    sources = list_sources()
    source = next((item for item in sources if item["id"] == source_id), None)
    if not source:
        raise ValueError(f"Source not found: {source_id}")

    source.update(
        {
            "name": name,
            "type": source_type,
            "metadata": metadata,
            "updated_at": utc_now(),
        }
    )
    source.setdefault("credential_file", f"{source_id}.json")
    write_json(SOURCES_FILE, sources)
    write_json(settings.credentials_dir / source["credential_file"], credentials)
    return source


def delete_source(source_id: str) -> None:
    ensure_storage()
    sources = list_sources()
    source = next((item for item in sources if item["id"] == source_id), None)
    write_json(SOURCES_FILE, [item for item in sources if item["id"] != source_id])

    if source and source.get("credential_file"):
        credential_path = settings.credentials_dir / source["credential_file"]
        if credential_path.exists():
            credential_path.unlink()

    views = [view for view in list_saved_views() if view.get("source_id") != source_id]
    write_json(VIEWS_FILE, views)

    state = _dashboard_state()
    state["cards"] = [card for card in state["cards"] if card.get("source_id") != source_id]
    write_dashboard_state(state)


def read_credentials(source: dict[str, Any]) -> dict[str, Any]:
    return read_json(settings.credentials_dir / source["credential_file"], {})


def _dashboard_state() -> dict[str, list[dict[str, Any]]]:
    ensure_storage()
    state = read_json(DASHBOARDS_FILE, [])
    if isinstance(state, list):
        dashboards = []
        seen = set()
        for card in state:
            dashboard_name = card.get("dashboard_name") or "Default"
            if dashboard_name not in seen:
                dashboards.append(
                    {
                        "id": make_id(dashboard_name),
                        "name": dashboard_name,
                        "created_at": card.get("created_at") or utc_now(),
                        "updated_at": card.get("updated_at") or utc_now(),
                    }
                )
                seen.add(dashboard_name)
            card["dashboard_name"] = dashboard_name
        migrated = {"dashboards": dashboards, "cards": state}
        write_json(DASHBOARDS_FILE, migrated)
        return migrated
    return {
        "dashboards": state.get("dashboards", []),
        "cards": state.get("cards", []),
    }


def write_dashboard_state(state: dict[str, list[dict[str, Any]]]) -> None:
    write_json(DASHBOARDS_FILE, state)


def list_dashboards() -> list[dict[str, Any]]:
    return _dashboard_state()["dashboards"]


def save_dashboard(name: str) -> dict[str, Any]:
    state = _dashboard_state()
    existing = next((dashboard for dashboard in state["dashboards"] if dashboard["name"] == name), None)
    if existing:
        return existing
    dashboard = {
        "id": make_id(name),
        "name": name,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    state["dashboards"].append(dashboard)
    write_dashboard_state(state)
    return dashboard


def rename_dashboard(old_name: str, new_name: str) -> dict[str, Any]:
    new_name = new_name.strip()
    if not new_name:
        raise ValueError("Dashboard name is required.")
    state = _dashboard_state()
    dashboard = next((item for item in state["dashboards"] if item["name"] == old_name), None)
    if not dashboard:
        raise ValueError(f"Dashboard not found: {old_name}")
    duplicate = next((item for item in state["dashboards"] if item["name"] == new_name and item["id"] != dashboard["id"]), None)
    if duplicate:
        raise ValueError(f"Dashboard already exists: {new_name}")

    dashboard["name"] = new_name
    dashboard["updated_at"] = utc_now()
    for card in state["cards"]:
        if (card.get("dashboard_name") or "Default") == old_name:
            card["dashboard_name"] = new_name
            card["updated_at"] = utc_now()
    write_dashboard_state(state)
    return dashboard


def delete_dashboard(dashboard_id: str) -> None:
    state = _dashboard_state()
    dashboard = next((item for item in state["dashboards"] if item["id"] == dashboard_id), None)
    if not dashboard:
        return
    dashboard_name = dashboard["name"]
    state["dashboards"] = [item for item in state["dashboards"] if item["id"] != dashboard_id]
    state["cards"] = [card for card in state["cards"] if (card.get("dashboard_name") or "Default") != dashboard_name]
    write_dashboard_state(state)


def list_dashboard_cards() -> list[dict[str, Any]]:
    return _dashboard_state()["cards"]


def get_dashboard_card(card_id: str) -> dict[str, Any] | None:
    return next((card for card in list_dashboard_cards() if card["id"] == card_id), None)


def list_dashboard_names() -> list[str]:
    names = {dashboard["name"] for dashboard in list_dashboards()}
    names.update(card.get("dashboard_name") or "Default" for card in list_dashboard_cards())
    return sorted(names)


def save_dashboard_card(card: dict[str, Any]) -> dict[str, Any]:
    ensure_storage()
    dashboard_name = card.get("dashboard_name") or "Default"
    save_dashboard(dashboard_name)
    state = _dashboard_state()
    card = {
        "id": make_id(card["name"]),
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "dashboard_name": dashboard_name,
        **card,
    }
    state["cards"].append(card)
    write_dashboard_state(state)
    return card


def update_dashboard_card(card_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    dashboard_name = updates.get("dashboard_name") or "Default"
    save_dashboard(dashboard_name)
    state = _dashboard_state()
    card = next((item for item in state["cards"] if item["id"] == card_id), None)
    if not card:
        raise ValueError(f"Dashboard card not found: {card_id}")
    dashboard_name = updates.get("dashboard_name") or card.get("dashboard_name") or "Default"
    card.update({**updates, "dashboard_name": dashboard_name, "updated_at": utc_now()})
    write_dashboard_state(state)
    return card


def delete_dashboard_card(card_id: str) -> None:
    state = _dashboard_state()
    state["cards"] = [card for card in state["cards"] if card["id"] != card_id]
    write_dashboard_state(state)


def list_saved_views() -> list[dict[str, Any]]:
    ensure_storage()
    return read_json(VIEWS_FILE, [])


def get_saved_view(view_id: str) -> dict[str, Any] | None:
    return next((view for view in list_saved_views() if view["id"] == view_id), None)


def save_saved_view(view: dict[str, Any]) -> dict[str, Any]:
    ensure_storage()
    view = {
        "id": make_id(view["name"]),
        "created_at": utc_now(),
        "updated_at": utc_now(),
        **view,
    }
    views = list_saved_views()
    views.append(view)
    write_json(VIEWS_FILE, views)
    return view


def delete_saved_view(view_id: str) -> None:
    ensure_storage()
    views = [view for view in list_saved_views() if view["id"] != view_id]
    write_json(VIEWS_FILE, views)


def list_favorites() -> list[dict[str, Any]]:
    dashboard_favorites = [
        {
            "key": f"dashboard:{dashboard['id']}",
            "type": "dashboard",
            "item_id": dashboard["id"],
            "name": dashboard["name"],
            "created_at": dashboard.get("updated_at") or dashboard.get("created_at") or utc_now(),
        }
        for dashboard in list_dashboards()
        if dashboard.get("favorite", False)
    ]
    view_favorites = [
        {
            "key": f"view:{view['id']}",
            "type": "view",
            "item_id": view["id"],
            "name": view["name"],
            "created_at": view.get("updated_at") or view.get("created_at") or utc_now(),
        }
        for view in list_saved_views()
        if view.get("favorite", False)
    ]
    return sorted(dashboard_favorites + view_favorites, key=lambda item: item["created_at"], reverse=True)


def is_favorite(item_type: str, item_id: str) -> bool:
    if item_type == "dashboard":
        dashboard = next((item for item in list_dashboards() if item["id"] == item_id), None)
        return bool(dashboard and dashboard.get("favorite", False))
    if item_type == "view":
        view = get_saved_view(item_id)
        return bool(view and view.get("favorite", False))
    return False


def toggle_favorite(item_type: str, item_id: str, name: str) -> bool:
    new_value = not is_favorite(item_type, item_id)
    if item_type == "dashboard":
        state = _dashboard_state()
        for dashboard in state["dashboards"]:
            if dashboard["id"] == item_id:
                dashboard["favorite"] = new_value
                dashboard["updated_at"] = utc_now()
                break
        write_dashboard_state(state)
        return new_value
    if item_type == "view":
        views = list_saved_views()
        for view in views:
            if view["id"] == item_id:
                view["favorite"] = new_value
                view["updated_at"] = utc_now()
                break
        write_json(VIEWS_FILE, views)
        return new_value
    return False
