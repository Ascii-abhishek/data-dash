from __future__ import annotations

from typing import Any

import streamlit as st

from tick_ticker_dash.app.common import cached_sql, clear_data_cache, render_cache_status, render_empty_state
from tick_ticker_dash.app.controls import render_control_panel
from tick_ticker_dash.app.dialogs import render_create_dashboard_dialog, render_dashboard_dialog, render_rename_dashboard_dialog
from tick_ticker_dash.app.graphs import render_result
from tick_ticker_dash.app.styles import action_link, page_title
from tick_ticker_dash.storage.local_store import (
    delete_dashboard_card,
    get_source,
    is_favorite,
    list_dashboard_cards,
    list_dashboards,
)


def render_dashboard_page() -> None:
    cards = list_dashboard_cards()
    dashboards = list_dashboards()
    if not dashboards:
        page_title("Dashboards", "dashboard")
        if st.button("Add dashboard", type="primary", icon=":material/add:"):
            render_create_dashboard_dialog()
        render_empty_state("Add a dashboard to start building your market workspace.")
        return

    selected_name = st.session_state.get("selected_dashboard_name")
    if not selected_name:
        render_dashboard_index(cards, dashboards)
        return

    title_columns = st.columns([0.94, 0.06], vertical_alignment="center")
    with title_columns[0]:
        page_title(selected_name, "dashboard")
    with title_columns[1]:
        st.markdown("<div class='icon-only-button'>", unsafe_allow_html=True)
        if st.button(
            "",
            key=f"rename_dashboard_{selected_name}",
            icon=":material/edit:",
            help=f"Rename {selected_name}",
            use_container_width=True,
        ):
            render_rename_dashboard_dialog(selected_name)
        st.markdown("</div>", unsafe_allow_html=True)
    controls = render_control_panel(
        "Dashboard controls",
        [
            {"id": "auto_refresh", "kind": "checkbox", "label": "Auto refresh", "value": False},
            {"id": "refresh_seconds", "kind": "number", "label": "Interval (s)", "min_value": 5, "value": 60, "step": 5},
            {"id": "refresh_now", "kind": "button", "label": "Refresh now", "icon": ":material/refresh:"},
            {"id": "add_card", "kind": "button", "label": "Add card", "type": "primary", "icon": ":material/add_chart:"},
        ],
        key_prefix=f"dashboard_{selected_name}",
    )
    auto_refresh = bool(controls["auto_refresh"])
    refresh_seconds = int(controls["refresh_seconds"])
    if controls["refresh_now"]:
        clear_data_cache()
    if controls["add_card"]:
        render_dashboard_dialog(selected_name)
    dashboard_cards = [card for card in cards if (card.get("dashboard_name") or "Default") == selected_name]
    if not dashboard_cards:
        render_empty_state("This dashboard has no cards yet. Add a card from the top.")
        return

    for row_start in range(0, len(dashboard_cards), 2):
        columns = st.columns(2)
        for column, card in zip(columns, dashboard_cards[row_start : row_start + 2], strict=False):
            with column.container(border=True):
                header = st.columns([0.7, 0.15, 0.15], vertical_alignment="center")
                header[0].markdown(f"#### {card['name']}")
                if header[1].button(
                    "",
                    key=f"edit_card_{card['id']}",
                    icon=":material/edit:",
                    help=f"Edit {card['name']}",
                    use_container_width=True,
                ):
                    render_dashboard_dialog(selected_name, card["id"])
                if header[2].button(
                    "",
                    key=f"delete_card_{card['id']}",
                    icon=":material/delete:",
                    help=f"Delete {card['name']}",
                    use_container_width=True,
                ):
                    delete_dashboard_card(card["id"])
                    clear_data_cache()
                    st.rerun()
                render_dashboard_card(card, auto_refresh, refresh_seconds)


def render_dashboard_index(cards: list[dict[str, Any]], dashboards: list[dict[str, Any]]) -> None:
    page_title("Dashboards", "dashboard")
    top = st.columns([0.22, 0.78], vertical_alignment="bottom")
    if top[0].button("Add dashboard", type="primary", icon=":material/add:", use_container_width=True):
        render_create_dashboard_dialog()

    if not dashboards:
        render_empty_state("Add a dashboard to start building your market workspace.")
        return

    for dashboard in dashboards:
        dashboard_name = dashboard["name"]
        card_count = sum(1 for card in cards if (card.get("dashboard_name") or "Default") == dashboard_name)
        with st.container(border=True):
            columns = st.columns([0.52, 0.16, 0.16, 0.16], vertical_alignment="center")
            columns[0].markdown(f"#### {dashboard_name}")
            columns[0].caption(f"{card_count} cards")
            columns[1].markdown(
                action_link("Open", "open_in_new", "open", "dashboard", dashboard["id"], "open"),
                unsafe_allow_html=True,
            )
            dashboard_starred = is_favorite("dashboard", dashboard["id"])
            columns[2].markdown(
                action_link(
                    "Starred" if dashboard_starred else "Star",
                    "star" if dashboard_starred else "star_border",
                    "toggle_favorite",
                    "dashboard",
                    dashboard["id"],
                    "starred" if dashboard_starred else "star",
                ),
                unsafe_allow_html=True,
            )
            columns[3].markdown(
                action_link("Delete", "delete", "delete", "dashboard", dashboard["id"], "delete"),
                unsafe_allow_html=True,
            )


def render_dashboard_card(card: dict[str, Any], auto_refresh: bool, dashboard_refresh_seconds: int | None = None) -> None:
    refresh_seconds = max(int(dashboard_refresh_seconds or card.get("refresh_seconds", 60)), 5)

    @st.fragment(run_every=f"{refresh_seconds}s")
    def _render() -> None:
        _render_dashboard_card_body(card, refresh_seconds)

    if auto_refresh:
        _render()
    else:
        _render_dashboard_card_body(card, None)


def _render_dashboard_card_body(card: dict[str, Any], refresh_seconds: int | None) -> None:
    source = get_source(card["source_id"])
    if not source:
        st.error("The data source for this card no longer exists.")
        return
    try:
        with st.spinner("Loading market data..."):
            df, cached_at, from_cache = cached_sql(source, card["sql"], refresh_seconds)
        render_cache_status(cached_at, from_cache)
        render_result(df, card.get("type", "table"), f"card_{card['id']}", card.get("chart_config", {}))
    except Exception as exc:
        st.error(str(exc))
