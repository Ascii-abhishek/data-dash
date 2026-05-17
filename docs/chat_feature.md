# Chat with AI

The app includes a single-session AI chat panel opened from the sidebar with **Chat with AI**. When open, the layout becomes three panes: the normal Streamlit sidebar on the left, the current app page in the middle, and a bordered chat pane on the right. When closed, the right pane is not rendered.

## Local Memory Files

Runtime memory is stored in `memory/`, which is ignored by git:

- `prompt.json`: system prompt and durable assistant behavior.
- `context.json`: reusable app context, including the latest source catalog snapshot.
- `session.json`: the active chat session as a list of turns with `user`, `llm`, `created_at`, `provider`, and `model`.

The app creates these files automatically on startup if they do not exist.

## Session Policy

The current implementation keeps one active session and limits it to 10 user chats. Each LLM call sends:

- the system prompt from `prompt.json`;
- bounded context from `context.json`;
- the latest source catalog and table schemas;
- the last 6 saved turns from `session.json`;
- the current user query.

This keeps responses contextual without sending an unbounded history. The context JSON is capped before sending to reduce token usage.

`context.json` is refreshed automatically from the persisted source catalog whenever the chat prompt is built. Sources added in a previous app session still appear in chat context as long as they exist in `connections/sources.json` and the catalog can be read or refreshed.

`prompt.json` includes SQL rules for the app's execution formats:

- The Query Tool runs against one selected source at a time.
- R2 source queries can use `data`.
- D1 single-source queries use the real table name.
- Generated exploratory SQL should be read-only and include a `LIMIT` unless the user asks otherwise.

## Provider Design

The first provider is Groq, using its OpenAI-compatible chat completions endpoint through `httpx`. The app reads `LLM_PROVIDER`, `GROQ_API_KEY`, and `GROQ_MODEL` through `AppSettings`, with `TTD_`-prefixed aliases also supported. This keeps the project free of a provider SDK dependency and leaves a small `call_llm()` boundary for adding other providers later.

Default model:

```text
llama-3.3-70b-versatile
```

## Streamlit Patterns Used

The UI renders prior turns with `st.chat_message`. Input uses a contained bottom form instead of `st.chat_input` so the right pane does not overlay the main app view. Session persistence is file-backed rather than only `st.session_state`, so refreshes do not wipe chat history. `st.session_state` is still used for UI-only state such as opening and closing the panel.

## Query Execution from Chat

Chat can execute source queries through a guarded action pipeline. The LLM does not execute free-form SQL directly. It first returns a structured JSON action such as `run_query`, `answer`, or `save_last_query`. The app then validates the action and runs it through `tick_ticker_dash.app.query_execution`.

The execution guard is intentionally strict:

- only a single statement is allowed;
- only `SELECT` and `WITH` statements are allowed;
- comments and multiple statements are rejected;
- destructive or metadata-changing keywords such as `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `PRAGMA`, and `VACUUM` are blocked in code;
- exploratory queries without `LIMIT` are capped before execution;
- query results are persisted into the same `ui/query_state.json` last-result shape used by the Query Tool.

When a chat query succeeds, the app stores the source, SQL, row count, duration, result preview, and optional saved view metadata in `memory/session.json`. Follow-up messages such as "save that as a view" can use the latest chat query metadata without asking the model to reconstruct the SQL.

## Chat Logs

Each chat session has a stable session id stored in `memory/session_meta.json`. Runtime diagnostics are appended to `logs/chat/<session_id>.log` using plain one-line records:

```text
timestamp - LOG_LEVEL - message | {"structured":"details"}
```

The log records user prompts, LLM request payloads, LLM responses, parsed action JSON, guarded query execution start/completion, execution timestamps, row counts, saved-view actions, stored chat turns, and failures. Secrets such as API keys are not logged.

If a generated query passes safety validation but fails during execution, chat performs one repair attempt. It sends the failed SQL, execution error, and source context back to the LLM, validates the repaired SQL with the same read-only guard, and logs both the failed and repaired attempts. If the repair also fails, the chat turn is stored as a query failure instead of losing the diagnostic context.

When a query action includes `save_view_name`, chat also respects `save_view_mode`. `new` creates a separate saved view, while `update` updates the latest saved view from chat when available. If the model omits the mode, the app infers it from the user's wording so "save in a new view" creates a new view and "update the above view" updates the existing one.

## Source Context

D1 table names and schemas are cached in `ui/source_catalog.json` and refreshed when stale after 30 minutes. A lightweight Streamlit fragment keeps the catalog warm while the app is open, and the normal sidebar/chat reads also refresh stale entries. The sidebar reads this catalog to show D1 tables under each D1 source. Clicking a table opens the source view and selects that table.

R2 sources appear as a single queryable table, using the source alias already used by the cross-source SQL executor.

## Source Browser

The sidebar keeps only **Add source** and **All sources** under Sources. **All sources** opens a Metabase-style grid page. R2 sources open directly into their data preview, while D1 sources first open a table grid; selecting a D1 table opens the existing source preview with that table selected.

The data preview itself is shared for all source types. R2 uses its single file-pattern table, and D1 uses the selected table, but both render the same preview controls, WHERE condition, cache status, and dataframe view.

Clean routes mirror the source hierarchy: `/sources` for the source grid, `/sources/<source-id>` for a source, and `/sources/<source-id>/<table-name>` for a D1 table. Older `/source/<source-id>` links still route to the same data view.

Source navigation is modeled as generic nodes rather than hardcoded source/table UI. The same node model renders grid items, breadcrumbs, and click behavior, so future source types can add deeper children while keeping the same UI path rendering.

## References

- Streamlit chat elements: https://docs.streamlit.io/develop/api-reference/chat
- Groq chat completions: https://console.groq.com/docs/text-chat
