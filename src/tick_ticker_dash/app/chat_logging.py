from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from tick_ticker_dash.config.settings import settings
from tick_ticker_dash.storage.local_store import read_chat_session_id


def log_chat_event(level: str, message: str, **fields: Any) -> None:
    """Append a single-line chat log record.

    Chat logs are diagnostic artifacts, so logging must never break the user flow.
    """
    try:
        session_id = read_chat_session_id()
        log_dir = settings.LOGS_DIR / "chat"
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).isoformat()
        line = f"{timestamp} - {level.upper()} - {message}"
        if fields:
            line = f"{line} | {json.dumps(fields, default=str, sort_keys=True, separators=(',', ':'))}"
        with (log_dir / f"{session_id}.log").open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        return
