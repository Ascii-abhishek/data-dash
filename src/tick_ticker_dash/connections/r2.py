from __future__ import annotations

import re
from typing import Any

import polars as pl


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
        return pl.scan_csv(uri, storage_options=storage_options)

    return pl.scan_parquet(
        uri,
        hive_partitioning=metadata.get("partitioning") == "hive",
        storage_options=storage_options,
    )


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
    if where_clause:
        return execute_sql(source, credentials, f"SELECT * FROM data WHERE {where_clause} LIMIT {limit}")
    return scan_source(source, credentials).limit(limit).collect()


def execute_sql(source: dict[str, Any], credentials: dict[str, Any], sql: str) -> pl.DataFrame:
    context = pl.SQLContext(eager=False)
    scan = scan_source(source, credentials)
    context.register("data", scan)
    source_alias = re.sub(r"[^a-zA-Z0-9_]+", "_", source.get("name", "")).strip("_")
    if source_alias and not source_alias[0].isdigit() and source_alias != "data":
        context.register(source_alias, scan)
    result = context.execute(sql)
    if isinstance(result, pl.LazyFrame):
        return result.collect()
    return result
