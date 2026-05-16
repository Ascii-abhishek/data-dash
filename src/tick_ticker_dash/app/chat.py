from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

import httpx
import streamlit as st

from tick_ticker_dash.app.source_catalog import catalog_for_prompt
from tick_ticker_dash.config.settings import settings
from tick_ticker_dash.storage.local_store import (
    read_chat_session,
    read_context_memory,
    read_prompt_memory,
    write_chat_session,
    write_context_memory,
)


MAX_CHAT_TURNS = 10
MAX_CONTEXT_CHARS = 12000
MAX_HISTORY_TURNS_SENT = 6
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"


def render_chat_panel() -> None:
    st.markdown("<div class='chat-rail-shell'>", unsafe_allow_html=True)
    st.markdown("<div class='chat-panel-title'>AI Chat</div>", unsafe_allow_html=True)
    top_left, top_right = st.columns([0.5, 0.5], gap="small")
    if top_left.button("New chat", icon=":material/add_comment:", width="stretch", key="chat_new"):
        write_chat_session([])
        st.rerun()
    if top_right.button("Close", icon=":material/close:", width="stretch", key="chat_close"):
        st.session_state["chat_open"] = False
        st.rerun()

    session = read_chat_session()
    turns_used = len(session)
    st.caption(f"{turns_used}/{MAX_CHAT_TURNS} chats used in this session.")

    with st.container(height=640, border=False):
        if not session:
            st.caption("Ask about sources, table schemas, query ideas, or dashboard interpretation.")
        for turn in session:
            with st.chat_message("user"):
                st.markdown(str(turn.get("user", "")))
            with st.chat_message("assistant"):
                st.markdown(str(turn.get("llm", "")))

    if turns_used >= MAX_CHAT_TURNS:
        st.warning("This session has reached 10 chats. Start a new chat to save a fresh context window.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    with st.form("ai_chat_form", clear_on_submit=True):
        user_query = st.text_area(
            "Ask about your data",
            key="ai_chat_text",
            height=96,
            placeholder="Ask about sources, schemas, joins, or analysis.",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("Send", icon=":material/send:", type="primary", width="stretch")

    if submitted and user_query.strip():
        try:
            _handle_user_query(user_query.strip())
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    st.markdown("</div>", unsafe_allow_html=True)


def _handle_user_query(user_query: str) -> None:
    session = read_chat_session()
    if len(session) >= MAX_CHAT_TURNS:
        return

    with st.spinner("Thinking with current data context..."):
        messages = build_llm_messages(user_query, session)
        response = call_llm(messages)

    now = datetime.now(UTC).isoformat()
    session.append(
        {
            "user": user_query,
            "llm": response,
            "created_at": now,
            "provider": "groq",
            "model": _env_value("GROQ_MODEL") or DEFAULT_GROQ_MODEL,
        }
    )
    write_chat_session(session)


def build_llm_messages(user_query: str, session: list[dict[str, Any]]) -> list[dict[str, str]]:
    prompt = read_prompt_memory()
    context = read_context_memory()
    context["source_catalog"] = catalog_for_prompt()
    write_context_memory(context)

    system_prompt = str(prompt.get("system") or "You are a helpful data assistant.")
    context_text = _bounded_json(context, MAX_CONTEXT_CHARS)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": f"Available app memory and data catalog:\n{context_text}"},
    ]

    for turn in session[-MAX_HISTORY_TURNS_SENT:]:
        user = str(turn.get("user") or "").strip()
        assistant = str(turn.get("llm") or "").strip()
        if user:
            messages.append({"role": "user", "content": user})
        if assistant:
            messages.append({"role": "assistant", "content": assistant})

    messages.append({"role": "user", "content": user_query})
    return messages


def call_llm(messages: list[dict[str, str]]) -> str:
    provider = (_env_value("LLM_PROVIDER") or "groq").lower()
    if provider != "groq":
        raise RuntimeError(f"Unsupported LLM provider: {provider}")
    return _call_groq(messages)


def _call_groq(messages: list[dict[str, str]]) -> str:
    api_key = _env_value("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is missing. Add it to .env or the environment.")

    model = _env_value("GROQ_MODEL") or DEFAULT_GROQ_MODEL
    response = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "max_completion_tokens": 1024,
        },
        timeout=60,
    )
    payload = response.json()
    if response.is_error:
        message = _groq_error_message(payload) or response.text
        raise RuntimeError(f"Groq request failed ({response.status_code}): {message}")
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError("Groq returned no choices.")
    return str(choices[0].get("message", {}).get("content") or "").strip()


def _groq_error_message(payload: dict[str, Any]) -> str:
    error = payload.get("error") or {}
    return str(error.get("message") or "")


def _bounded_json(payload: dict[str, Any], max_chars: int) -> str:
    text = json.dumps(payload, default=str, indent=2, sort_keys=True)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 200] + "\n... [context truncated to save tokens]"


def _env_value(name: str) -> str | None:
    value = os.getenv(name)
    if value:
        return value
    env_path = settings.project_dir / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        if key.strip() == name:
            return raw_value.strip().strip('"').strip("'")
    return None
