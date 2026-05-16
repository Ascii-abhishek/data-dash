from __future__ import annotations

import re
from typing import Any

import polars as pl

DEFAULT_PARTITION_ALIASES = {
    "stock": "stock",
    "stock_code": "stock",
    "symbol": "stock",
    "expiry": "expiry",
    "expiry_date": "expiry",
}


def _storage_options(credentials: dict[str, Any]) -> dict[str, Any]:
    options = {
        "aws_access_key_id": credentials.get("access_key_id"),
        "aws_secret_access_key": credentials.get("secret_access_key"),
        "aws_region": credentials.get("region") or "auto",
    }
    if credentials.get("endpoint_url"):
        options["endpoint_url"] = credentials["endpoint_url"]
    return {key: value for key, value in options.items() if value}


def normalize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(metadata)
    bucket = str(normalized.get("bucket", "")).strip().strip("/")
    pattern = str(normalized.get("file_pattern", "")).strip().lstrip("/")
    bucket_prefix = f"{bucket}/"
    if bucket and pattern.startswith(bucket_prefix):
        pattern = pattern[len(bucket_prefix) :]
    normalized["bucket"] = bucket
    normalized["file_pattern"] = pattern
    if "partitioning" not in normalized:
        normalized["partitioning"] = "hive" if normalized.get("hive_partitioning", True) else "none"
    normalized.pop("hive_partitioning", None)
    normalized.pop("file_format", None)
    return normalized


def source_uri(metadata: dict[str, Any]) -> str:
    normalized = normalize_metadata(metadata)
    return f"s3://{normalized['bucket']}/{normalized['file_pattern']}"


def scan_source(source: dict[str, Any], credentials: dict[str, Any]) -> pl.LazyFrame:
    metadata = normalize_metadata(source["metadata"])
    uri = source_uri(metadata)
    file_format = infer_file_format(metadata["file_pattern"])
    storage_options = _storage_options(credentials)

    if file_format == "csv":
        scan = pl.scan_csv(uri, storage_options=storage_options)
    else:
        scan = pl.scan_parquet(
            uri,
            hive_partitioning=metadata.get("partitioning") == "hive",
            storage_options=storage_options,
        )
    return _with_partition_alias_columns(source, scan)


def infer_file_format(pattern: str) -> str:
    lowered = pattern.lower()
    if ".csv" in lowered:
        return "csv"
    return "parquet"


def test_connection(metadata: dict[str, Any], credentials: dict[str, Any]) -> tuple[bool, str]:
    metadata = normalize_metadata(metadata)
    sample = preview({"metadata": metadata}, credentials, limit=1)
    uri = source_uri(metadata)
    if sample.height:
        return True, f"Connected. The pattern returned data from {uri}"
    return True, f"Connected. The pattern exists but returned no rows from {uri}"


def preview(
    source: dict[str, Any],
    credentials: dict[str, Any],
    limit: int = 200,
    where_clause: str | None = None,
) -> pl.DataFrame:
    where_clause = _normalize_where_clause(where_clause)
    partition_source = _source_for_simple_partition_filters(source, where_clause)
    if partition_source is not None:
        return scan_source(partition_source, credentials).limit(limit).collect()
    if where_clause:
        return execute_sql(source, credentials, f"SELECT * FROM data WHERE {where_clause} LIMIT {limit}")
    return scan_source(source, credentials).limit(limit).collect()


def execute_sql(source: dict[str, Any], credentials: dict[str, Any], sql: str) -> pl.DataFrame:
    optimized = _execute_simple_partition_select(source, credentials, sql)
    if optimized is not None:
        return optimized

    partition_source = _source_for_sql_partition_filters(source, sql)
    if partition_source is not None:
        source = partition_source

    result = _execute_sql_lazy(source, credentials, sql)
    if isinstance(result, pl.LazyFrame):
        return result.collect()
    return result


def sql_columns(source: dict[str, Any], credentials: dict[str, Any], sql: str) -> list[str]:
    partition_source = _source_for_sql_partition_filters(source, sql)
    if partition_source is not None:
        source = partition_source

    result = _execute_sql_lazy(source, credentials, sql)
    if isinstance(result, pl.LazyFrame):
        return list(result.collect_schema().names())
    return result.columns


def _execute_sql_lazy(source: dict[str, Any], credentials: dict[str, Any], sql: str) -> pl.LazyFrame | pl.DataFrame:
    context = pl.SQLContext(eager=False)
    scan = scan_source(source, credentials)
    context.register("data", scan)
    source_alias = re.sub(r"[^a-zA-Z0-9_]+", "_", source.get("name", "")).strip("_")
    if source_alias and not source_alias[0].isdigit() and source_alias != "data":
        context.register(source_alias, scan)
    return context.execute(sql)


def _normalize_where_clause(where_clause: str | None) -> str:
    clause = str(where_clause or "").strip().rstrip(";").strip()
    if clause.lower().startswith("where "):
        clause = clause[6:].strip()
    return clause


def _execute_simple_partition_select(source: dict[str, Any], credentials: dict[str, Any], sql: str) -> pl.DataFrame | None:
    source_alias = re.sub(r"[^a-zA-Z0-9_]+", "_", source.get("name", "")).strip("_")
    table_names = ["data"]
    if source_alias and not source_alias[0].isdigit():
        table_names.append(source_alias)
    table_pattern = "|".join(re.escape(table_name) for table_name in table_names)
    match = re.fullmatch(
        rf"\s*select\s+\*\s+from\s+(?:{table_pattern})\s+where\s+(.+?)\s+limit\s+(\d+)\s*;?\s*",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    partition_source = _source_for_simple_partition_filters(source, match.group(1))
    if partition_source is None:
        return None
    return scan_source(partition_source, credentials).limit(int(match.group(2))).collect()


def _source_for_simple_partition_filters(source: dict[str, Any], where_clause: str) -> dict[str, Any] | None:
    filters = _simple_partition_filters(source, where_clause)
    if not filters:
        return None
    return _source_for_partitions(source, filters)


def _source_for_sql_partition_filters(source: dict[str, Any], sql: str) -> dict[str, Any] | None:
    where_clause = _where_clause(sql)
    if not where_clause:
        return None
    filters = _partition_filters_in_where(source, where_clause)
    if not filters:
        return None
    return _source_for_partitions(source, filters)


def _simple_partition_filters(source: dict[str, Any], where_clause: str) -> dict[str, str] | None:
    if not where_clause:
        return None

    aliases = _partition_aliases(source)
    filters: dict[str, str] = {}
    for part in re.split(r"\s+and\s+", where_clause, flags=re.IGNORECASE):
        match = re.fullmatch(
            r"\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(?:'([^']*)'|\"([^\"]*)\"|([^\s()]+))\s*",
            part,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        column = match.group(1).lower()
        partition_name = aliases.get(column)
        if not partition_name:
            return None
        filters[partition_name] = match.group(2) or match.group(3) or match.group(4) or ""
    return filters or None


def _partition_filters_in_where(source: dict[str, Any], where_clause: str) -> dict[str, str]:
    aliases = _partition_aliases(source)
    filters: dict[str, str] = {}
    for part in re.split(r"\s+and\s+", where_clause, flags=re.IGNORECASE):
        match = re.fullmatch(
            r"\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(?:'([^']*)'|\"([^\"]*)\"|([^\s()]+))\s*",
            part,
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        column = match.group(1).lower()
        partition_name = aliases.get(column)
        if partition_name:
            filters[partition_name] = match.group(2) or match.group(3) or match.group(4) or ""
    return filters


def _where_clause(sql: str) -> str:
    match = re.search(
        r"\bwhere\b\s+(.+?)(?=\border\s+by\b|\bgroup\s+by\b|\blimit\b|$)",
        sql.rstrip(";"),
        flags=re.IGNORECASE | re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def _with_partition_alias_columns(source: dict[str, Any], scan: pl.LazyFrame) -> pl.LazyFrame:
    try:
        columns = set(scan.collect_schema().names())
    except Exception:
        return scan

    expressions = []
    for alias, partition_name in _partition_aliases(source).items():
        if alias != partition_name and partition_name in columns and alias not in columns:
            expressions.append(pl.col(partition_name).alias(alias))
    if not expressions:
        return scan
    return scan.with_columns(expressions)


def _partition_aliases(source: dict[str, Any]) -> dict[str, str]:
    metadata = normalize_metadata(source["metadata"])
    aliases = dict(DEFAULT_PARTITION_ALIASES)
    configured = metadata.get("partition_columns") or metadata.get("partition_aliases") or {}
    if isinstance(configured, dict):
        aliases.update({str(column).lower(): str(partition) for column, partition in configured.items() if column and partition})
    return aliases


def _source_for_partitions(source: dict[str, Any], filters: dict[str, str]) -> dict[str, Any] | None:
    metadata = normalize_metadata(source["metadata"])
    pattern = str(metadata.get("file_pattern", "")).strip().lstrip("/")
    if not pattern or not filters:
        return None

    prefix = pattern.split("**", 1)[0].rstrip("/")
    if not prefix:
        return None

    existing_partitions = set(re.findall(r"(?:^|/)([a-zA-Z_][a-zA-Z0-9_]*)=", prefix))
    ordered_filters = _ordered_partition_filters(metadata, filters)
    if not ordered_filters:
        return None
    partition_path = "/".join(
        f"{name}={value}" for name, value in ordered_filters if name not in existing_partitions and value
    )
    if not partition_path:
        return source if set(filters).issubset(existing_partitions) else None

    narrowed = dict(source)
    narrowed_metadata = dict(metadata)
    narrowed_metadata["file_pattern"] = f"{prefix}/{partition_path}/**/*.parquet"
    narrowed["metadata"] = narrowed_metadata
    return narrowed


def _ordered_partition_filters(metadata: dict[str, Any], filters: dict[str, str]) -> list[tuple[str, str]]:
    order = metadata.get("partition_order")
    if isinstance(order, list):
        names = [str(name) for name in order]
    else:
        names = _partition_names_from_pattern(str(metadata.get("file_pattern", "")))
    if not names:
        names = ["stock", "expiry"]
    for name in names:
        if name in filters:
            break
        if any(later_name in filters for later_name in names[names.index(name) + 1 :]):
            return []

    ordered = [(name, filters[name]) for name in names if name in filters]
    ordered.extend((name, value) for name, value in filters.items() if name not in names)
    return ordered


def _partition_names_from_pattern(pattern: str) -> list[str]:
    names = re.findall(r"(?:^|/)([a-zA-Z_][a-zA-Z0-9_]*)=[^/]+", pattern)
    return list(dict.fromkeys(names))
