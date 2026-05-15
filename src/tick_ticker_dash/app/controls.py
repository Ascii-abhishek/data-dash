from __future__ import annotations

from typing import Any

import streamlit as st


ControlSpec = dict[str, Any]


def render_control_panel(
    title: str,
    controls: list[ControlSpec],
    *,
    expanded: bool = True,
    key_prefix: str,
) -> dict[str, Any]:
    """Render a consistent expandable control panel and return control values."""
    values: dict[str, Any] = {}
    if not controls:
        return values

    with st.expander(title, expanded=expanded):
        st.markdown("<div class='ttd-control-panel'>", unsafe_allow_html=True)
        columns = st.columns(len(controls), gap="medium", vertical_alignment="center")
        for column, spec in zip(columns, controls, strict=True):
            control_id = spec["id"]
            kind = spec["kind"]
            label = spec["label"]
            key = spec.get("key") or f"{key_prefix}_{control_id}"
            with column:
                if kind == "button":
                    values[control_id] = st.button(
                        label,
                        key=key,
                        type=spec.get("type", "secondary"),
                        icon=spec.get("icon"),
                        help=spec.get("help"),
                        width="stretch",
                    )
                elif kind == "checkbox":
                    values[control_id] = st.checkbox(
                        label,
                        value=bool(spec.get("value", False)),
                        key=key,
                        help=spec.get("help"),
                    )
                elif kind == "number":
                    values[control_id] = st.number_input(
                        label,
                        min_value=spec.get("min_value"),
                        max_value=spec.get("max_value"),
                        value=spec.get("value"),
                        step=spec.get("step", 1),
                        key=key,
                        help=spec.get("help"),
                    )
                else:
                    raise ValueError(f"Unsupported control kind: {kind}")
        st.markdown("</div>", unsafe_allow_html=True)
    return values
