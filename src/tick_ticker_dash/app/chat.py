from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from typing import Any

import httpx
import streamlit as st

from tick_ticker_dash.app.chat_logging import log_chat_event
from tick_ticker_dash.app.query_execution import (
    DEFAULT_QUERY_ROW_LIMIT,
    QueryExecution,
    execute_read_only_query,
    persist_query_result,
    query_result_preview,
)
from tick_ticker_dash.app.source_catalog import catalog_for_prompt
from tick_ticker_dash.config.settings import settings
from tick_ticker_dash.storage.local_store import (
    read_chat_session,
    read_context_memory,
    read_prompt_memory,
    reset_chat_session,
    save_saved_view,
    update_saved_view,
    write_chat_session,
    write_context_memory,
)


MAX_CHAT_TURNS = 10
MAX_CONTEXT_CHARS = 12000
MAX_HISTORY_TURNS_SENT = 6
MAX_CHAT_RESULT_ROWS = 20
ERROR_RESPONSE_PREFIX = "Some error happened"


def render_chat_panel() -> None:
    st.markdown("<div class='chat-rail-shell'>", unsafe_allow_html=True)
    st.markdown("<div class='chat-panel-title'>Data Dash AI</div>", unsafe_allow_html=True)
    top_left, top_right = st.columns([0.5, 0.5], gap="small")
    if top_left.button("New chat", icon=":material/add_comment:", width="stretch", key="chat_new"):
        meta = reset_chat_session()
        log_chat_event("INFO", "Started new chat session", session_meta=meta)
        st.rerun()
    if top_right.button("Close", icon=":material/close:", width="stretch", key="chat_close"):
        st.session_state["layout_only_rerun"] = True
        st.session_state["chat_open"] = False
        st.query_params.pop("chat", None)
        st.rerun()

    session = read_chat_session()
    pending_query = str(st.session_state.get("pending_chat_query") or "").strip()
    turns_used = len(session)
    st.caption(f"{turns_used}/{MAX_CHAT_TURNS} chats used in this session.")

    with st.container(height=640, border=False):
        if not session and not pending_query:
            st.caption("Ask about sources, table schemas, query ideas, or dashboard interpretation.")
        for turn in session:
            with st.chat_message("user"):
                st.markdown(str(turn.get("user", "")))
            with st.chat_message("assistant"):
                st.markdown(str(turn.get("llm", "")))
                _render_turn_query_details(turn)
        if pending_query:
            with st.chat_message("user"):
                st.markdown(pending_query)
            with st.chat_message("assistant"):
                with st.status("Working on it...", expanded=True):
                    st.caption("Planning the query, running safe execution if needed, and preparing the answer.")

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
        st.session_state["pending_chat_query"] = user_query.strip()
        st.rerun()

    if pending_query:
        try:
            _handle_user_query(pending_query)
        except Exception as exc:
            _store_chat_error_turn(pending_query, exc)
        finally:
            st.session_state["pending_chat_query"] = ""
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def _handle_user_query(user_query: str) -> None:
    session = read_chat_session()
    if len(session) >= MAX_CHAT_TURNS:
        log_chat_event("WARNING", "User query ignored because chat turn limit was reached", user_query=user_query, turns=len(session))
        return

    log_chat_event("INFO", "Received user query", user_query=user_query, turns_before=len(session))
    try:
        with st.spinner("Thinking with current data context..."):
            action = plan_chat_action(user_query, session)
            turn = execute_chat_action(user_query, action, session)

        now = datetime.now(UTC).isoformat()
        turn.update({"created_at": now, "provider": "groq", "model": settings.GROQ_MODEL})
        session.append(turn)
        write_chat_session(session)
        log_chat_event("INFO", "Stored chat turn", turn=turn, turns_after=len(session))
    except Exception as exc:
        log_chat_event("ERROR", "Chat query failed", user_query=user_query, error_type=type(exc).__name__, error=str(exc))
        raise


def _store_chat_error_turn(user_query: str, error: Exception) -> None:
    session = read_chat_session()
    message = f"{ERROR_RESPONSE_PREFIX}: `{_error_snippet(error)}`"
    turn = {
        "user": user_query,
        "llm": message,
        "action": "error",
        "error": {
            "type": type(error).__name__,
            "message": str(error),
        },
        "created_at": datetime.now(UTC).isoformat(),
        "provider": "groq",
        "model": settings.GROQ_MODEL,
    }
    session.append(turn)
    write_chat_session(session)
    log_chat_event("ERROR", "Stored chat error turn", turn=turn, turns_after=len(session))


def _error_snippet(error: Exception, max_chars: int = 320) -> str:
    text = str(error).strip() or type(error).__name__
    text = re.sub(r"\s+", " ", text)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def plan_chat_action(user_query: str, session: list[dict[str, Any]]) -> dict[str, Any]:
    messages = build_llm_messages(user_query, session, mode="action")
    raw_response = call_llm(messages, purpose="plan_chat_action")
    action = _extract_json_object(raw_response)
    log_chat_event("INFO", "Converted LLM response to chat action", user_query=user_query, raw_response=raw_response, action=action)
    if not isinstance(action, dict):
        return {"action": "answer", "response": raw_response}
    return action


def execute_chat_action(user_query: str, action: dict[str, Any], session: list[dict[str, Any]]) -> dict[str, Any]:
    action_name = str(action.get("action") or "answer").strip().lower()
    log_chat_event("INFO", "Executing chat action", user_query=user_query, action_name=action_name, action=action)
    if action_name == "run_query":
        return _execute_chat_query_action(user_query, action, session)
    if action_name == "save_last_query":
        return _execute_save_last_query_action(user_query, action, session)
    response = str(action.get("response") or "").strip()
    if not response:
        response = call_llm(build_llm_messages(user_query, session, mode="answer"), purpose="answer_fallback")
    log_chat_event("INFO", "Completed answer action", response=response)
    return {"user": user_query, "llm": response, "action": "answer"}


def _execute_chat_query_action(user_query: str, action: dict[str, Any], session: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        return _run_chat_query_action(user_query, action, session, repair_attempt=False)
    except Exception as exc:
        log_chat_event(
            "WARNING",
            "Chat query execution failed; requesting one SQL repair",
            user_query=user_query,
            action=action,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        repaired_action = repair_chat_query_action(user_query, action, exc, session)
        if not repaired_action:
            return _query_failure_turn(user_query, action, exc)
        try:
            return _run_chat_query_action(user_query, repaired_action, session, repair_attempt=True, original_error=str(exc))
        except Exception as repaired_exc:
            log_chat_event(
                "ERROR",
                "Repaired chat query execution failed",
                user_query=user_query,
                original_action=action,
                repaired_action=repaired_action,
                original_error=str(exc),
                error_type=type(repaired_exc).__name__,
                error=str(repaired_exc),
            )
            return _query_failure_turn(user_query, repaired_action, repaired_exc, original_error=str(exc))


def _run_chat_query_action(
    user_query: str,
    action: dict[str, Any],
    session: list[dict[str, Any]],
    *,
    repair_attempt: bool,
    original_error: str | None = None,
) -> dict[str, Any]:
    source_id = str(action.get("source_id") or "").strip()
    sql = str(action.get("sql") or "").strip()
    if not source_id or not sql:
        log_chat_event("WARNING", "Run query action missing source or SQL", action=action)
        return {
            "user": user_query,
            "llm": "I need a specific source and read-only SQL before I can run this.",
            "action": "answer",
        }

    log_chat_event("INFO", "Starting guarded query execution", source_id=source_id, sql=sql, repair_attempt=repair_attempt)
    execution = execute_read_only_query(source_id, sql, row_limit=DEFAULT_QUERY_ROW_LIMIT)
    log_chat_event(
        "INFO",
        "Finished guarded query execution",
        source_id=source_id,
        sql=execution.original_sql,
        execution_sql=execution.execution_sql,
        was_capped=execution.was_capped,
        row_count=execution.df.height,
        duration_seconds=execution.duration_seconds,
        executed_at=execution.executed_at,
        repair_attempt=repair_attempt,
    )
    persist_query_result(source_id, sql, execution.df, execution.executed_at)
    preview = query_result_preview(execution.df, MAX_CHAT_RESULT_ROWS)
    log_chat_event("INFO", "Persisted chat query result preview", source_id=source_id, sql=sql, preview=preview)
    view = _save_view_if_requested(action, source_id, execution.original_sql, session, user_query)
    response = summarize_query_result(user_query, execution, preview, view, repaired=repair_attempt, original_error=original_error)
    return {
        "user": user_query,
        "llm": response,
        "action": "run_query",
        "query": {
            "source_id": source_id,
            "source_name": execution.source.get("name"),
            "sql": execution.original_sql,
            "execution_sql": execution.execution_sql,
            "was_capped": execution.was_capped,
            "row_count": execution.df.height,
            "duration_seconds": execution.duration_seconds,
            "view_id": view.get("id") if view else None,
            "view_name": view.get("name") if view else None,
            "repaired": repair_attempt,
        },
        "result_preview": preview,
    }


def repair_chat_query_action(
    user_query: str,
    action: dict[str, Any],
    error: Exception,
    session: list[dict[str, Any]],
) -> dict[str, Any]:
    context = read_context_memory()
    context["source_catalog"] = catalog_for_prompt()
    latest_query = _latest_chat_query(session)
    if latest_query:
        context["latest_chat_query"] = latest_query
    repair_payload = {
        "user_query": user_query,
        "failed_action": action,
        "error_type": type(error).__name__,
        "error": str(error),
        "context": context,
    }
    messages = [
        {
            "role": "system",
            "content": (
                "Repair a failed Tick Ticker Dash SQL action. Return only one JSON object with no markdown. "
                "Allowed shapes are {\"action\":\"run_query\",\"source_id\":\"...\",\"sql\":\"SELECT ...\",\"save_view_name\":null,\"save_view_mode\":\"new|update\"} "
                "or {\"action\":\"answer\",\"response\":\"...\"}. The SQL must remain one read-only SELECT or WITH statement. "
                "For Cloudflare R2 sources this uses Polars SQL. In Polars SQL, date subtraction returns a duration; "
                "to convert a day duration to a number, use CAST(date_expr_2 - date_expr_1 AS INT64) / 86400000000."
            ),
        },
        {"role": "user", "content": _bounded_json(repair_payload, MAX_CONTEXT_CHARS)},
    ]
    raw_response = call_llm(messages, purpose="repair_chat_query")
    repaired_action = _extract_json_object(raw_response)
    log_chat_event(
        "INFO",
        "Converted LLM repair response to chat action",
        user_query=user_query,
        raw_response=raw_response,
        repaired_action=repaired_action,
    )
    if str(repaired_action.get("action") or "").strip().lower() != "run_query":
        return {}
    return repaired_action


def _query_failure_turn(
    user_query: str,
    action: dict[str, Any],
    error: Exception,
    *,
    original_error: str | None = None,
) -> dict[str, Any]:
    message = (
        f"{ERROR_RESPONSE_PREFIX}: I tried to run the query, but it failed after validation/execution. "
        f"Error: `{error}`"
    )
    if original_error:
        message = f"{message}\n\nOriginal error before repair: `{original_error}`"
    return {
        "user": user_query,
        "llm": message,
        "action": "run_query_failed",
        "query": {
            "source_id": action.get("source_id"),
            "sql": action.get("sql"),
            "error": str(error),
            "original_error": original_error,
        },
    }


def _execute_save_last_query_action(user_query: str, action: dict[str, Any], session: list[dict[str, Any]]) -> dict[str, Any]:
    latest = _latest_chat_query(session)
    if not latest:
        log_chat_event("WARNING", "Save last query requested without a previous chat query", user_query=user_query, action=action)
        return {"user": user_query, "llm": "I do not have a recent chat query to save as a view yet.", "action": "answer"}
    view_name = str(action.get("view_name") or latest.get("view_name") or "AI saved query").strip()
    view = save_saved_view(
        {
            "name": view_name,
            "source_id": latest["source_id"],
            "sql": latest["sql"],
            "auto_refresh": False,
            "refresh_seconds": 60,
        }
    )
    log_chat_event("INFO", "Saved latest chat query as view", view=view, latest_query=latest)
    return {
        "user": user_query,
        "llm": f"Saved **{view['name']}** as a View.",
        "action": "save_last_query",
        "query": {**latest, "view_id": view["id"], "view_name": view["name"]},
    }


def summarize_query_result(
    user_query: str,
    execution: QueryExecution,
    preview: dict[str, Any],
    view: dict[str, Any] | None,
    *,
    repaired: bool = False,
    original_error: str | None = None,
) -> str:
    summary_context = {
        "source_id": execution.source_id,
        "source_name": execution.source.get("name"),
        "sql": execution.original_sql,
        "execution_sql": execution.execution_sql,
        "was_capped": execution.was_capped,
        "duration_seconds": round(execution.duration_seconds, 3),
        "result": preview,
        "saved_view": {"id": view["id"], "name": view["name"]} if view else None,
        "repaired": repaired,
        "original_error": original_error,
    }
    messages = [
        {
            "role": "system",
            "content": (
                "You are Tick Ticker Dash's data analyst. Answer from the query result only. "
                "Be concise. Mention when the preview is truncated or the SQL was capped."
            ),
        },
        {"role": "user", "content": f"Original request:\n{user_query}"},
        {"role": "user", "content": f"Executed query context:\n{_bounded_json(summary_context, MAX_CONTEXT_CHARS)}"},
    ]
    log_chat_event("INFO", "Calling LLM to summarize query result", user_query=user_query, summary_context=summary_context)
    return call_llm(messages, purpose="summarize_query_result")


def build_llm_messages(user_query: str, session: list[dict[str, Any]], mode: str = "answer") -> list[dict[str, str]]:
    prompt = read_prompt_memory()
    context = read_context_memory()
    context["source_catalog"] = catalog_for_prompt()
    latest_query = _latest_chat_query(session)
    if latest_query:
        context["latest_chat_query"] = latest_query
    write_context_memory(context)

    system_prompt = _prompt_text(prompt)
    if mode == "action":
        system_prompt = _action_prompt(system_prompt)
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


def _action_prompt(base_prompt: str) -> str:
    return (
        f"{base_prompt}\n\n"
        "Decide the next app action for the user's message. Return only one JSON object, with no markdown.\n"
        "Allowed shapes:\n"
        '{"action":"answer","response":"..."}\n'
        '{"action":"run_query","source_id":"...","sql":"SELECT ... LIMIT 200","save_view_name":null,"save_view_mode":"new|update"}\n'
        '{"action":"save_last_query","view_name":"..."}\n'
        "Use run_query only when the user asks for data that can be answered from exactly one available source. "
        "Use the source_id keys from the source catalog. SQL must be one read-only SELECT or WITH query. "
        "Never include INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, PRAGMA, or multiple statements. "
        "Include a LIMIT unless the user's requested aggregate guarantees a small result. "
        "Use save_view_name only when the user clearly asks to save or update a view. "
        "Use save_view_mode='new' when the user asks for a new view, separate view, another view, or save as new. "
        "Use save_view_mode='update' when the user asks to update/modify/change the existing, latest, previous, or above view. "
        "For Cloudflare R2 sources this uses Polars SQL. In Polars SQL, date subtraction returns a duration; "
        "to convert a day duration to a number, use CAST(date_expr_2 - date_expr_1 AS INT64) / 86400000000."
    )


def _prompt_text(prompt: dict[str, Any]) -> str:
    parts = [str(prompt.get("system") or "You are a helpful data assistant.")]
    if prompt.get("sql_rules"):
        parts.append("SQL/query rules:\n" + _bullets(prompt["sql_rules"]))
    if prompt.get("chart_rules"):
        parts.append("Chart/dashboard rules:\n" + _bullets(prompt["chart_rules"]))
    if prompt.get("legacy_system"):
        parts.append("Legacy project instruction:\n" + str(prompt["legacy_system"]))
    return "\n\n".join(parts)


def _bullets(items: Any) -> str:
    if not isinstance(items, list):
        return str(items)
    return "\n".join(f"- {item}" for item in items)


def call_llm(messages: list[dict[str, str]], purpose: str = "chat") -> str:
    provider = settings.LLM_PROVIDER.lower()
    if provider != "groq":
        log_chat_event("ERROR", "Unsupported LLM provider", purpose=purpose, provider=provider)
        raise RuntimeError(f"Unsupported LLM provider: {provider}")
    return _call_groq(messages, purpose)


def _call_groq(messages: list[dict[str, str]], purpose: str) -> str:
    if not settings.GROQ_API_KEY:
        log_chat_event("ERROR", "Groq API key missing", purpose=purpose, model=settings.GROQ_MODEL)
        raise RuntimeError("GROQ_API_KEY is missing. Add it to .env or the environment.")

    request_payload = {
        "model": settings.GROQ_MODEL,
        "messages": messages,
        "temperature": 0.2,
        "max_completion_tokens": 1024,
    }
    log_chat_event("INFO", "LLM request started", purpose=purpose, provider="groq", request=request_payload)
    start = time.perf_counter()
    try:
        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json=request_payload,
            timeout=60,
        )
        duration_seconds = time.perf_counter() - start
        payload = response.json()
    except Exception as exc:
        log_chat_event(
            "ERROR",
            "LLM request failed before response handling",
            purpose=purpose,
            provider="groq",
            duration_seconds=time.perf_counter() - start,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        raise

    if response.is_error:
        message = _groq_error_message(payload) or response.text
        log_chat_event(
            "ERROR",
            "LLM request returned error",
            purpose=purpose,
            provider="groq",
            status_code=response.status_code,
            duration_seconds=duration_seconds,
            response=payload,
            error=message,
        )
        raise RuntimeError(f"Groq request failed ({response.status_code}): {message}")
    choices = payload.get("choices") or []
    if not choices:
        log_chat_event(
            "ERROR",
            "LLM request returned no choices",
            purpose=purpose,
            provider="groq",
            status_code=response.status_code,
            duration_seconds=duration_seconds,
            response=payload,
        )
        raise RuntimeError("Groq returned no choices.")
    content = str(choices[0].get("message", {}).get("content") or "").strip()
    log_chat_event(
        "INFO",
        "LLM request completed",
        purpose=purpose,
        provider="groq",
        status_code=response.status_code,
        duration_seconds=duration_seconds,
        response=payload,
        content=content,
    )
    return content


def _groq_error_message(payload: dict[str, Any]) -> str:
    error = payload.get("error") or {}
    return str(error.get("message") or "")


def _bounded_json(payload: dict[str, Any], max_chars: int) -> str:
    text = json.dumps(payload, default=str, indent=2, sort_keys=True)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 200] + "\n... [context truncated to save tokens]"


def _extract_json_object(text: str) -> dict[str, Any]:
    payload = str(text or "").strip()
    if payload.startswith("```"):
        payload = re.sub(r"^```(?:json)?\s*", "", payload, flags=re.IGNORECASE)
        payload = re.sub(r"\s*```$", "", payload)
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", payload, flags=re.DOTALL)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    return parsed if isinstance(parsed, dict) else {}


def _save_view_if_requested(
    action: dict[str, Any],
    source_id: str,
    sql: str,
    session: list[dict[str, Any]],
    user_query: str,
) -> dict[str, Any] | None:
    view_name = str(action.get("save_view_name") or "").strip()
    if not view_name:
        return None
    save_mode = _view_save_mode(action, user_query)
    latest = _latest_chat_query(session)
    if save_mode == "update" and latest and latest.get("view_id"):
        try:
            view = update_saved_view(
                str(latest["view_id"]),
                {
                    "name": view_name,
                    "source_id": source_id,
                    "sql": sql,
                    "auto_refresh": False,
                    "refresh_seconds": 60,
                },
            )
            log_chat_event("INFO", "Updated chat query view", view=view, source_id=source_id, sql=sql, latest_query=latest)
            return view
        except ValueError as exc:
            log_chat_event("WARNING", "Could not update latest chat view; creating a new view", error=str(exc), latest_query=latest)
    view = save_saved_view(
        {
            "name": view_name,
            "source_id": source_id,
            "sql": sql,
            "auto_refresh": False,
            "refresh_seconds": 60,
        }
    )
    log_chat_event("INFO", "Saved chat query as requested view", view=view, source_id=source_id, sql=sql)
    return view


def _view_save_mode(action: dict[str, Any], user_query: str) -> str:
    requested = str(action.get("save_view_mode") or action.get("view_save_mode") or "").strip().lower()
    if requested in {"new", "create", "create_new"}:
        return "new"
    if requested in {"update", "replace", "existing"}:
        return "update"

    user_text = user_query.lower()
    if re.search(r"\b(new|separate|another)\s+view\b|\bsave\s+(it|this|that)?\s*as\s+(a\s+)?new\b", user_text):
        return "new"
    if re.search(r"\b(update|modify|change|replace)\b.*\b(view|above|previous|latest)\b|\b(update|modify|change|replace)\s+(above|previous|latest)\b", user_text):
        return "update"
    return "new"


def _latest_chat_query(session: list[dict[str, Any]]) -> dict[str, Any] | None:
    for turn in reversed(session):
        query = turn.get("query")
        if isinstance(query, dict) and query.get("source_id") and query.get("sql"):
            return {
                "source_id": query["source_id"],
                "source_name": query.get("source_name"),
                "sql": query["sql"],
                "view_id": query.get("view_id"),
                "view_name": query.get("view_name"),
            }
    return None


def _render_turn_query_details(turn: dict[str, Any]) -> None:
    query = turn.get("query")
    if not isinstance(query, dict):
        return
    with st.expander("Query details", expanded=False):
        source_name = query.get("source_name") or query.get("source_id")
        st.caption(f"Source: {source_name}")
        st.code(str(query.get("sql") or ""), language="sql")
        row_count = query.get("row_count")
        duration = query.get("duration_seconds")
        if row_count is not None:
            duration_text = f" in {float(duration):.2f}s" if duration is not None else ""
            st.caption(f"Returned {row_count:,} rows{duration_text}.")
        if query.get("was_capped"):
            st.caption(f"Result was capped at {DEFAULT_QUERY_ROW_LIMIT:,} rows.")
        if query.get("view_name"):
            st.caption(f"Saved view: {query['view_name']}")
