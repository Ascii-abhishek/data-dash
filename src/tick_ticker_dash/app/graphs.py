from __future__ import annotations

from typing import Any

import altair as alt
import polars as pl
import streamlit as st

from tick_ticker_dash.app.common import render_dataframe

NATIVE_CHART_TYPES = {"line", "area", "bar", "scatter"}
CUSTOM_CHART_TYPES = {"candle", "histogram", "pie"}
CHART_TYPE_LABELS = {
    "table": "Table",
    "line": "Line chart",
    "area": "Area chart",
    "bar": "Bar chart",
    "scatter": "Scatter chart",
    "candle": "Candle chart",
    "histogram": "Histogram",
    "pie": "Pie chart",
}


def chart_type_options() -> list[str]:
    return list(CHART_TYPE_LABELS)


def chart_type_label(chart_type: str) -> str:
    return CHART_TYPE_LABELS.get(chart_type, chart_type.title())


def select_column(
    label: str,
    columns: list[str],
    key: str,
    default: str | None = None,
    required: bool = False,
    help_text: str | None = None,
) -> str | None:
    options = columns if required else [""] + columns
    if default in options:
        index = options.index(default)
    elif required and options:
        index = 0
    else:
        index = 0
    value = st.selectbox(label, options, index=index, key=key, help=help_text)
    return value or None


def render_chart_config_controls(
    card_type: str,
    columns: list[str],
    key_prefix: str,
    current_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current_config = current_config or {}
    if card_type == "table" or not columns:
        return {}

    st.markdown("##### Chart fields")
    if card_type in NATIVE_CHART_TYPES:
        left, middle, right = st.columns(3)
        with left:
            x = select_column("X axis", columns, f"{key_prefix}_x", current_config.get("x"))
        with middle:
            y = select_column("Y axis", columns, f"{key_prefix}_y", current_config.get("y"))
        with right:
            color = select_column("Color field", columns, f"{key_prefix}_color", current_config.get("color"))
        config = {"x": x, "y": y, "color": color}
        if card_type == "scatter":
            size_options = [""] + columns
            size_index = size_options.index(current_config.get("size")) if current_config.get("size") in size_options else 0
            config["size"] = left.selectbox("Size field", size_options, index=size_index, key=f"{key_prefix}_size") or None
        return {key: value for key, value in config.items() if value}

    if card_type == "candle":
        defaults = _matching_defaults(columns, {"x": ("time", "date", "timestamp"), "open": ("open",), "high": ("high",), "low": ("low",), "close": ("close",)})
        c1, c2 = st.columns(2)
        with c1:
            x = select_column("X axis", columns, f"{key_prefix}_x", current_config.get("x") or defaults.get("x"), required=True)
            open_column = select_column("Open", columns, f"{key_prefix}_open", current_config.get("open") or defaults.get("open"), required=True)
            high_column = select_column("High", columns, f"{key_prefix}_high", current_config.get("high") or defaults.get("high"), required=True)
        with c2:
            low_column = select_column("Low", columns, f"{key_prefix}_low", current_config.get("low") or defaults.get("low"), required=True)
            close_column = select_column("Close", columns, f"{key_prefix}_close", current_config.get("close") or defaults.get("close"), required=True)
            lower_field = select_column("Lower bar field", columns, f"{key_prefix}_lower", current_config.get("lower") or current_config.get("volume"))
        return {
            "x": x,
            "open": open_column,
            "high": high_column,
            "low": low_column,
            "close": close_column,
            "lower": lower_field,
        }

    if card_type == "histogram":
        left, middle, right = st.columns(3)
        with left:
            x = select_column("Value field", columns, f"{key_prefix}_x", current_config.get("x"), required=True)
        with middle:
            color = select_column("Color field", columns, f"{key_prefix}_color", current_config.get("color"))
        with right:
            bins = st.number_input("Bins", min_value=5, max_value=100, value=int(current_config.get("bins") or 30), step=5, key=f"{key_prefix}_bins")
        return {"x": x, "color": color, "bins": int(bins)}

    if card_type == "pie":
        left, right = st.columns(2)
        with left:
            theta = select_column("Value field", columns, f"{key_prefix}_theta", current_config.get("theta"), required=True)
        with right:
            color = select_column("Category/color field", columns, f"{key_prefix}_color", current_config.get("color"), required=True)
        return {"theta": theta, "color": color}

    return {}


def validate_chart_config(card_type: str, config: dict[str, Any]) -> list[str]:
    required_fields = {
        "candle": ["x", "open", "high", "low", "close"],
        "histogram": ["x"],
        "pie": ["theta", "color"],
    }.get(card_type, [])
    missing = [field for field in required_fields if not config.get(field)]
    return [field.replace("_", " ").title() for field in missing]


def render_result(df: pl.DataFrame, card_type: str, key_prefix: str, config: dict[str, Any] | None = None) -> None:
    if df.is_empty():
        st.caption("No rows returned.")
        return

    config = config or {}
    if card_type in NATIVE_CHART_TYPES:
        st.altair_chart(_native_chart(df.to_pandas(), card_type, config), width="stretch", key=key_prefix)
        return
    if card_type in CUSTOM_CHART_TYPES:
        render_custom_chart(df, card_type, config, key_prefix)
        return
    render_dataframe(df, key_prefix)


def render_custom_chart(df: pl.DataFrame, card_type: str, config: dict[str, Any], key_prefix: str) -> None:
    missing = validate_chart_config(card_type, config)
    if missing:
        st.warning(f"Missing chart fields: {', '.join(missing)}.")
        render_dataframe(df, f"{key_prefix}_table_fallback")
        return

    data = _prepare_chart_data(df.to_pandas(), config)
    if card_type == "candle":
        st.altair_chart(_candlestick_chart(data, config), width="stretch", height="stretch", key=key_prefix)
    elif card_type == "histogram":
        st.altair_chart(_histogram_chart(data, config), width="stretch", key=key_prefix)
    elif card_type == "pie":
        st.altair_chart(_pie_chart(data, config), width="stretch", key=key_prefix)


def _candlestick_chart(data: Any, config: dict[str, Any]) -> alt.Chart:
    x = config["x"]
    open_column = config["open"]
    high_column = config["high"]
    low_column = config["low"]
    close_column = config["close"]
    tooltip = [x, open_column, high_column, low_column, close_column]
    if config.get("lower") and config["lower"] not in tooltip:
        tooltip.append(config["lower"])

    x_field = _typed_field(data, x)
    x_axis = alt.Axis(format="%H:%M", labelOverlap=True, tickCount=10) if _looks_temporal_column(x) else alt.Axis(labelOverlap=True)
    base = alt.Chart(data).encode(
        x=alt.X(x_field, title=None, axis=x_axis, scale=alt.Scale(nice=False)),
        color=alt.condition(
            alt.datum[open_column] <= alt.datum[close_column],
            alt.value("#2e7d32"),
            alt.value("#d32f2f"),
        ),
        tooltip=tooltip,
    )
    y_scale = alt.Scale(zero=False, nice=False)
    rule = base.mark_rule().encode(y=alt.Y(f"{low_column}:Q", title="Price", scale=y_scale), y2=f"{high_column}:Q")
    candle_size = _candle_size(len(data))
    bar = base.mark_bar(size=candle_size).encode(y=f"{open_column}:Q", y2=f"{close_column}:Q")
    price = (rule + bar).properties(height=560)
    price = price.interactive(name="price_zoom", bind_x=True, bind_y=True)
    if not config.get("lower"):
        return price

    lower = (
        alt.Chart(data)
        .mark_bar(color="#1976d2", opacity=0.55)
        .encode(
            x=alt.X(x_field, title=x, axis=x_axis, scale=alt.Scale(nice=False)),
            y=alt.Y(f"{config['lower']}:Q", title=config["lower"]),
            tooltip=tooltip,
        )
        .properties(height=180)
    )
    return alt.vconcat(price, lower.interactive(name="volume_zoom", bind_x=False, bind_y=True)).resolve_scale(x="shared")


def _prepare_chart_data(data: Any, config: dict[str, Any]) -> Any:
    x = config.get("x")
    if not x or x not in data.columns or not _looks_temporal_column(x):
        return data

    converted = data.copy()
    parsed = converted[x]
    if getattr(parsed.dtype, "kind", "") != "M":
        parsed = parsed.astype("datetime64[ns]", errors="ignore")
    converted[x] = parsed
    return converted


def _candle_size(row_count: int) -> int:
    if row_count > 500:
        return 3
    if row_count > 260:
        return 4
    if row_count > 140:
        return 5
    return 8


def _native_chart(data: Any, card_type: str, config: dict[str, Any]) -> alt.Chart:
    x = config.get("x")
    y = config.get("y")
    if not x or not y:
        return (
            alt.Chart(data)
            .mark_text(text="Select X and Y fields for this chart.")
            .properties(height=260)
        )

    base = alt.Chart(data).encode(
        x=alt.X(_typed_field(data, x), title=x),
        y=alt.Y(_typed_field(data, y), title=y),
        tooltip=[column for column in [x, y, config.get("color"), config.get("size")] if column],
    )
    if config.get("color"):
        base = base.encode(color=alt.Color(_typed_field(data, config["color"]), title=config["color"]))

    if card_type == "line":
        return base.mark_line(point=True).properties(height=360).interactive()
    if card_type == "area":
        return base.mark_area(opacity=0.72).properties(height=360).interactive()
    if card_type == "bar":
        return base.mark_bar().properties(height=360).interactive()
    if card_type == "scatter":
        chart = base
        if config.get("size"):
            chart = chart.encode(size=alt.Size(_typed_field(data, config["size"]), title=config["size"]))
        return chart.mark_circle(size=72, opacity=0.78).properties(height=360).interactive()
    return base.mark_point().properties(height=360).interactive()


def _histogram_chart(data: Any, config: dict[str, Any]) -> alt.Chart:
    x = config["x"]
    bins = int(config.get("bins") or 30)
    chart = alt.Chart(data).mark_bar().encode(
        x=alt.X(f"{x}:Q", bin=alt.Bin(maxbins=bins), title=x),
        y=alt.Y("count():Q", title="Count"),
        tooltip=[alt.Tooltip("count():Q", title="Count")],
    )
    if config.get("color"):
        chart = chart.encode(color=alt.Color(f"{config['color']}:N", title=config["color"]))
    return chart.properties(height=360).interactive()


def _pie_chart(data: Any, config: dict[str, Any]) -> alt.Chart:
    theta = config["theta"]
    color = config["color"]
    return (
        alt.Chart(data)
        .mark_arc(innerRadius=45)
        .encode(
            theta=alt.Theta(f"{theta}:Q", aggregate="sum", title=theta),
            color=alt.Color(f"{color}:N", title=color),
            tooltip=[alt.Tooltip(f"{color}:N", title=color), alt.Tooltip(f"sum({theta}):Q", title=theta)],
        )
        .properties(height=360)
        .interactive()
    )


def _typed_field(data: Any, column: str) -> str:
    series = data[column]
    kind = getattr(series.dtype, "kind", "")
    if kind == "M" or _looks_temporal_column(column):
        field_type = "T"
    elif kind in {"b", "i", "u", "f", "c"}:
        field_type = "Q"
    else:
        field_type = "N"
    return f"{column}:{field_type}"


def _looks_temporal_column(column: str) -> bool:
    normalized = column.lower()
    return any(part in normalized for part in ("date", "time", "timestamp", "datetime"))


def _matching_defaults(columns: list[str], candidates: dict[str, tuple[str, ...]]) -> dict[str, str]:
    lower_to_column = {column.lower(): column for column in columns}
    defaults = {}
    for field, names in candidates.items():
        for name in names:
            if name in lower_to_column:
                defaults[field] = lower_to_column[name]
                break
    return defaults
