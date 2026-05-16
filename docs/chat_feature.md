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
