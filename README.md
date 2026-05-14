# Data Dash

A lightweight Streamlit BI-style dashboard for market data stored in Cloudflare R2 and D1.

## What v1 includes

- Sidebar navigation for Dashboard, Views, and Query Tool.
- Add-source dialog with configurable fields for Cloudflare R2 and Cloudflare D1.
- Local source metadata in `connections/sources.json`.
- Per-source credentials in `credentials/<source-id>.json`.
- R2 preview/query support through Polars lazy scans.
- D1 query support through the Cloudflare D1 HTTP API.
- Dashboard cards with saved SQL, source selection, chart type, and refresh interval.
- Interactive table display with column selection, sort, and simple text filtering.

## Run

```bash
uv sync
uv run streamlit run app.py
```

Or, with pip:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
streamlit run app.py
```

## R2 SQL

For R2 sources, the app registers the selected file pattern as a Polars SQL table named `data`.
Enter the bucket separately from the object key pattern. For example:

- Bucket: `tick-ticker`
- Object key pattern inside bucket: `futures/ohlcv/**/*.parquet`

```sql
SELECT * FROM data LIMIT 200
```

## Local files

The following are intentionally ignored by git:

- `credentials/`
- `connections/*.json`
- `.env`

Credentials are stored locally for v1. The connector/storage layer is separated so this can later move to a proper secret store.
