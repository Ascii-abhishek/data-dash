SOURCE_TYPES = {
    "cloudflare_r2": {
        "label": "Cloudflare R2",
        "metadata_fields": [
            {"name": "bucket", "label": "Bucket", "type": "text", "required": True},
            {
                "name": "file_pattern",
                "label": "Object key pattern inside bucket",
                "type": "text",
                "help": "Do not include the bucket name. Example: futures/ohlcv/**/*.parquet",
                "placeholder": "futures/ohlcv/**/*.parquet",
                "required": True,
            },
            {
                "name": "partitioning",
                "label": "Partitioning",
                "type": "select",
                "options": ["none", "hive"],
                "default": "hive",
            },
        ],
        "credential_fields": [
            {"name": "access_key_id", "label": "Access key ID", "type": "text", "required": True},
            {"name": "secret_access_key", "label": "Secret access key", "type": "password", "required": True},
            {
                "name": "endpoint_url",
                "label": "S3 endpoint URL",
                "type": "text",
                "placeholder": "https://<ACCOUNT_ID>.r2.cloudflarestorage.com",
                "required": True,
            },
            {"name": "region", "label": "Region", "type": "text", "default": "auto"},
        ],
    },
    "cloudflare_d1": {
        "label": "Cloudflare D1",
        "metadata_fields": [
            {"name": "account_id", "label": "Account ID", "type": "text", "required": True},
            {"name": "database_name", "label": "Database name", "type": "text", "required": True},
        ],
        "credential_fields": [
            {"name": "api_token", "label": "Cloudflare API token", "type": "password", "required": True},
        ],
    },
}


def source_type_options() -> dict[str, str]:
    return {key: value["label"] for key, value in SOURCE_TYPES.items()}
