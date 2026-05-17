from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

import polars as pl

from tick_ticker_dash.connections.registry import execute_source_sql
from tick_ticker_dash.storage.local_store import get_source, read_query_state, write_query_state


DEFAULT_QUERY_ROW_LIMIT = 5000
DEFAULT_PERSISTED_ROW_LIMIT = 5000
BLOCKED_SQL_KEYWORDS = {
    "alter",
    "attach",
    "copy",
    "create",
    "delete",
    "detach",
    "drop",
    "insert",
    "merge",
    "pragma",
    "replace",
    "truncate",
    "update",
    "vacuum",
}


@dataclass(frozen=True)
class SafeSql:
    original_sql: str
    execution_sql: str
    was_capped: bool


@dataclass(frozen=True)
class QueryExecution:
    source: dict[str, Any]
    source_id: str
    original_sql: str
    execution_sql: str
    was_capped: bool
    df: pl.DataFrame
    executed_at: float
    duration_seconds: float


def prepare_read_only_sql(sql: str, row_limit: int = DEFAULT_QUERY_ROW_LIMIT) -> SafeSql:
    statement = _normalized_statement(sql)
    _validate_read_only_statement(statement)
    execution_sql, was_capped = cap_read_only_sql(statement, row_limit)
    return SafeSql(original_sql=statement, execution_sql=execution_sql, was_capped=was_capped)


def execute_read_only_query(
    source_id: str,
    sql: str,
    *,
    row_limit: int = DEFAULT_QUERY_ROW_LIMIT,
) -> QueryExecution:
    source = get_source(source_id)
    if not source:
        raise ValueError(f"Source not found: {source_id}")

    safe_sql = prepare_read_only_sql(sql, row_limit)
    start = time.perf_counter()
    df = execute_source_sql(source, safe_sql.execution_sql)
    return QueryExecution(
        source=source,
        source_id=source_id,
        original_sql=safe_sql.original_sql,
        execution_sql=safe_sql.execution_sql,
        was_capped=safe_sql.was_capped,
        df=df,
        executed_at=time.time(),
        duration_seconds=time.perf_counter() - start,
    )


def cap_read_only_sql(sql: str, row_limit: int) -> tuple[str, bool]:
    statement = _normalized_statement(sql)
    if _has_limit_clause(statement):
        return statement, False
    return f"{statement} LIMIT {max(int(row_limit), 1)}", True


def persist_query_result(
    source_id: str,
    sql: str,
    df: pl.DataFrame,
    cached_at: float,
    *,
    row_limit: int = DEFAULT_PERSISTED_ROW_LIMIT,
) -> None:
    state = read_query_state()
    rows = df.head(row_limit).to_dicts()
    state["last_result"] = {
        "source_id": source_id,
        "sql": sql,
        "cached_at": cached_at,
        "rows": rows,
        "truncated": df.height > len(rows),
    }
    write_query_state(state)


def query_result_preview(df: pl.DataFrame, max_rows: int = 20) -> dict[str, Any]:
    rows = df.head(max_rows).to_dicts()
    return {
        "row_count": df.height,
        "columns": [{"name": name, "type": str(dtype)} for name, dtype in df.schema.items()],
        "rows": rows,
        "truncated": df.height > len(rows),
    }


def _normalized_statement(sql: str) -> str:
    statement = str(sql or "").strip()
    while statement.endswith(";"):
        statement = statement[:-1].strip()
    if not statement:
        raise ValueError("SQL is required.")
    return statement


def _validate_read_only_statement(statement: str) -> None:
    lowered = statement.lower()
    if ";" in statement:
        raise ValueError("Only one SQL statement can be executed at a time.")
    if _contains_sql_comment(statement):
        raise ValueError("SQL comments are not allowed in automated query execution.")
    if not re.match(r"^\s*(select|with)\b", statement, flags=re.IGNORECASE):
        raise ValueError("Only read-only SELECT or WITH queries can be executed.")

    tokens = set(re.findall(r"\b[a-z_]+\b", lowered))
    blocked = sorted(tokens.intersection(BLOCKED_SQL_KEYWORDS))
    if blocked:
        raise ValueError(f"Blocked SQL keyword in automated query: {', '.join(blocked)}")


def _contains_sql_comment(statement: str) -> bool:
    return "--" in statement or "/*" in statement or "*/" in statement


def _has_limit_clause(statement: str) -> bool:
    return bool(re.search(r"\blimit\s+\d+\b", statement, flags=re.IGNORECASE))
