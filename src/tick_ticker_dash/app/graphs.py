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
            tooltip = select_column("Tooltip field", columns, f"{key_prefix}_tooltip", current_config.get("tooltip"))
        return {
            "x": x,
            "open": open_column,
            "high": high_column,
            "low": low_column,
            "close": close_column,
            "tooltip": tooltip,
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
    if card_type == "line":
        st.line_chart(df, x=config.get("x"), y=config.get("y"), color=config.get("color"), use_container_width=True)
        return
    if card_type == "area":
        st.area_chart(df, x=config.get("x"), y=config.get("y"), color=config.get("color"), use_container_width=True)
        return
    if card_type == "bar":
        st.bar_chart(df, x=config.get("x"), y=config.get("y"), color=config.get("color"), use_container_width=True)
        return
    if card_type == "scatter":
        st.scatter_chart(
            df,
            x=config.get("x"),
            y=config.get("y"),
            color=config.get("color"),
            size=config.get("size"),
            use_container_width=True,
        )
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

    data = df.to_pandas()
    if card_type == "candle":
        st.altair_chart(_candlestick_chart(data, config), use_container_width=True, key=key_prefix)
    elif card_type == "histogram":
        st.altair_chart(_histogram_chart(data, config), use_container_width=True, key=key_prefix)
    elif card_type == "pie":
        st.altair_chart(_pie_chart(data, config), use_container_width=True, key=key_prefix)


def _candlestick_chart(data: Any, config: dict[str, Any]) -> alt.Chart:
    x = config["x"]
    open_column = config["open"]
    high_column = config["high"]
    low_column = config["low"]
    close_column = config["close"]
    tooltip = [x, open_column, high_column, low_column, close_column]
    if config.get("tooltip") and config["tooltip"] not in tooltip:
        tooltip.append(config["tooltip"])

    base = alt.Chart(data).encode(
        x=alt.X(f"{x}:T", title=x),
        color=alt.condition(
            alt.datum[open_column] <= alt.datum[close_column],
            alt.value("#2e7d32"),
            alt.value("#d32f2f"),
        ),
        tooltip=tooltip,
    )
    y_scale = alt.Scale(zero=False, nice=False)
    rule = base.mark_rule().encode(y=alt.Y(f"{low_column}:Q", title="Price", scale=y_scale), y2=f"{high_column}:Q")
    bar = base.mark_bar(size=8).encode(y=f"{open_column}:Q", y2=f"{close_column}:Q")
    return (rule + bar).properties(height=360).interactive(bind_y=True)


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
    return chart.properties(height=360)


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
    )


def _matching_defaults(columns: list[str], candidates: dict[str, tuple[str, ...]]) -> dict[str, str]:
    lower_to_column = {column.lower(): column for column in columns}
    defaults = {}
    for field, names in candidates.items():
        for name in names:
            if name in lower_to_column:
                defaults[field] = lower_to_column[name]
                break
    return defaults
