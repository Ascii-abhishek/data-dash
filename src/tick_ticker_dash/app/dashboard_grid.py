from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import streamlit as st


@dataclass(frozen=True)
class DashboardGridConfig:
    columns: int = 2
    gap: str = "medium"


def render_dashboard_grid(
    cards: list[dict[str, Any]],
    render_card: Callable[[dict[str, Any]], None],
    config: DashboardGridConfig = DashboardGridConfig(),
) -> None:
    st.markdown("<div class='dashboard-card-grid'></div>", unsafe_allow_html=True)
    for row in _card_rows(cards, config.columns):
        columns = st.columns(len(row), gap=config.gap)
        for column, card in zip(columns, row, strict=False):
            with column:
                with st.container(border=True):
                    render_card(card)


def _card_rows(cards: list[dict[str, Any]], columns: int) -> list[list[dict[str, Any]]]:
    column_count = max(columns, 1)
    return [cards[index : index + column_count] for index in range(0, len(cards), column_count)]
