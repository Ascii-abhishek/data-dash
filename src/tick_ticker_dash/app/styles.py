from __future__ import annotations

from html import escape
from urllib.parse import urlencode

import streamlit as st


def inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,500,0,0');
        :root {
            --ttd-blue: #1976d2;
            --ttd-blue-strong: #1565c0;
            --ttd-blue-soft: rgba(25, 118, 210, 0.12);
            --ttd-border: rgba(25, 118, 210, 0.24);
        }
        .block-container {
            padding-top: 3.75rem;
        }
        iframe[height="1"] {
            display: none;
        }
        [data-testid="stSidebar"] {
            min-width: 300px;
            max-width: 360px;
            background: linear-gradient(180deg, rgba(25, 118, 210, 0.10), rgba(25, 118, 210, 0.03));
        }
        [data-testid="stSidebar"] .block-container {
            padding-top: 1.35rem;
        }
        [data-testid="stSidebar"] h3 {
            color: var(--ttd-blue);
            font-weight: 800;
        }
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            gap: 0.5rem;
        }
        [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
            gap: 0.5rem;
        }
        .sidebar-brand {
            border-bottom: 1px solid var(--ttd-border);
            color: var(--ttd-blue);
            font-size: 1.55rem;
            font-weight: 850;
            line-height: 1.2;
            margin: 0 0 1.05rem;
            padding: 0 0 0.75rem;
        }
        .sidebar-section {
            margin-top: 1rem;
        }
        .source-list {
            margin-top: -0.5rem;
        }
        .source-list + div[data-testid="stHorizontalBlock"],
        .source-list + div[data-testid="stHorizontalBlock"] ~ div[data-testid="stHorizontalBlock"] {
            margin-top: -0.5rem;
        }
        .material-symbols-rounded {
            direction: ltr;
            display: inline-block;
            font-family: 'Material Symbols Rounded';
            font-feature-settings: 'liga';
            font-size: 1.15rem;
            line-height: 1;
            text-transform: none;
            vertical-align: -0.2rem;
            white-space: nowrap;
        }
        .page-title {
            align-items: center;
            color: var(--ttd-blue);
            display: flex;
            font-size: 1.7rem;
            font-weight: 800;
            gap: 0.45rem;
            margin: 0 0 1rem;
        }
        .section-label {
            color: rgba(128, 128, 128, 0.9);
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.04em;
            margin: 0 0 0.3rem;
            text-transform: uppercase;
        }
        .metric-strip {
            background: var(--ttd-blue-soft);
            border: 1px solid var(--ttd-border);
            border-radius: 8px;
            padding: 0.85rem 1rem;
        }
        .dashboard-card-grid + div[data-testid="stHorizontalBlock"],
        .dashboard-card-grid + div[data-testid="stHorizontalBlock"] ~ div[data-testid="stHorizontalBlock"] {
            align-items: stretch;
            gap: 1rem;
            margin-bottom: 1rem;
        }
        .dashboard-card-grid + div[data-testid="stHorizontalBlock"] div[data-testid="stVerticalBlockBorderWrapper"],
        .dashboard-card-grid + div[data-testid="stHorizontalBlock"] ~ div[data-testid="stHorizontalBlock"] div[data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(255, 255, 255, 0.015);
            border-radius: 8px;
            min-height: 31rem;
            overflow: hidden;
        }
        .dashboard-card-grid + div[data-testid="stHorizontalBlock"] iframe,
        .dashboard-card-grid + div[data-testid="stHorizontalBlock"] ~ div[data-testid="stHorizontalBlock"] iframe {
            max-width: 100%;
        }
        @media (max-width: 1100px) {
            .dashboard-card-grid + div[data-testid="stHorizontalBlock"],
            .dashboard-card-grid + div[data-testid="stHorizontalBlock"] ~ div[data-testid="stHorizontalBlock"] {
                flex-direction: column;
            }
            .dashboard-card-grid + div[data-testid="stHorizontalBlock"] > div,
            .dashboard-card-grid + div[data-testid="stHorizontalBlock"] ~ div[data-testid="stHorizontalBlock"] > div {
                width: 100% !important;
            }
        }
        .muted {
            color: rgba(128, 128, 128, 0.95);
            font-size: 0.9rem;
        }
        .empty-state {
            align-items: center;
            color: rgba(128, 128, 128, 0.95);
            display: flex;
            font-size: 1.05rem;
            justify-content: center;
            min-height: 56vh;
            text-align: center;
        }
        div.stButton > button {
            display: flex;
            border-radius: 8px;
            font-weight: 650;
            justify-content: flex-start;
            text-align: left;
        }
        div.stButton > button > div,
        div.stButton > button [data-testid="stMarkdownContainer"] {
            justify-content: flex-start;
            text-align: left;
            width: 100%;
        }
        div.stButton > button p {
            text-align: left;
            width: 100%;
        }
        [data-testid="stSidebar"] div.stButton > button {
            justify-content: flex-start;
            text-align: left;
        }
        [data-testid="stSidebar"] div.stButton > button > div {
            justify-content: flex-start;
            width: 100%;
        }
        .icon-only-button div.stButton > button {
            justify-content: center;
            padding-left: 0;
            padding-right: 0;
        }
        .d1-table-list div.stButton > button,
        .d1-table-list div.stButton > button > div,
        .d1-table-list div.stButton > button [data-testid="stMarkdownContainer"],
        .d1-table-list div.stButton > button p {
            justify-content: flex-start;
            text-align: left;
            width: 100%;
        }
        .source-browser-grid + div[data-testid="stHorizontalBlock"] div.stButton > button,
        .source-browser-grid + div[data-testid="stHorizontalBlock"] ~ div[data-testid="stHorizontalBlock"] div.stButton > button {
            align-items: center;
            min-height: 5.4rem;
            padding: 1rem 1.15rem;
        }
        .source-browser-grid + div[data-testid="stHorizontalBlock"] div.stButton > button p,
        .source-browser-grid + div[data-testid="stHorizontalBlock"] ~ div[data-testid="stHorizontalBlock"] div.stButton > button p {
            line-height: 1.35;
            white-space: pre-line;
        }
        .breadcrumb-separator {
            align-items: center;
            color: rgba(128, 128, 128, 0.95);
            display: flex;
            font-size: 1.15rem;
            font-weight: 750;
            height: 2.4rem;
            justify-content: center;
        }
        .breadcrumb-current {
            align-items: center;
            display: flex;
            font-weight: 750;
            min-height: 2.4rem;
            overflow-wrap: anywhere;
        }
        [data-testid="stSidebar"] .source-list div.stButton > button:has(.material-symbols-rounded) {
            min-height: 2.3rem;
        }
        .chat-panel-title {
            align-items: center;
            color: var(--ttd-blue);
            display: flex;
            font-size: 1.35rem;
            font-weight: 800;
            margin: 0 0 0.8rem;
        }
        .chat-panel-title:before {
            content: '';
            background: var(--ttd-blue);
            border-radius: 999px;
            display: inline-block;
            height: 1.1rem;
            margin-right: 0.45rem;
            width: 0.25rem;
        }
        .chat-panel-title + div[data-testid="stHorizontalBlock"] {
            margin-bottom: 0.35rem;
        }
        .chat-rail-start + div[data-testid="stVerticalBlock"] {
            background: linear-gradient(180deg, rgba(25, 118, 210, 0.10), rgba(25, 118, 210, 0.03));
            border-left: 1px solid var(--ttd-border);
            min-height: 100vh;
            margin-bottom: -6rem;
            margin-top: -3.75rem;
            padding: 3.75rem 1rem 1rem;
        }
        .chat-rail-start + div[data-testid="stVerticalBlock"] > div:has(form) {
            margin-top: auto;
        }
        .chat-rail-start + div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(div[data-testid="stChatMessage"]) {
            background: rgba(0, 0, 0, 0.10);
            border: 1px solid var(--ttd-border);
            border-radius: 8px;
        }
        textarea[aria-label="Ask about your data"] {
            resize: none;
        }
        div[data-testid="stChatMessage"] {
            border-radius: 8px;
        }
        .danger-button button,
        .danger-button div.stButton > button,
        .danger-button [data-testid="stBaseButton-secondary"] {
            background: #d32f2f;
            border-color: #d32f2f;
            color: white;
        }
        .danger-button button *,
        .danger-button div.stButton > button *,
        .danger-button [data-testid="stBaseButton-secondary"] * {
            color: white;
        }
        .danger-button button:hover,
        .danger-button div.stButton > button:hover,
        .danger-button [data-testid="stBaseButton-secondary"]:hover {
            background: #b71c1c;
            border-color: #b71c1c;
            color: white;
        }
        .open-action-button button,
        .open-action-button div.stButton > button,
        .open-action-button [data-testid="stBaseButton-secondary"] {
            background: #2e7d32;
            border-color: #2e7d32;
            color: white;
        }
        .open-action-button button *,
        .open-action-button div.stButton > button *,
        .open-action-button [data-testid="stBaseButton-secondary"] * {
            color: white;
        }
        .open-action-button button:hover,
        .open-action-button div.stButton > button:hover,
        .open-action-button [data-testid="stBaseButton-secondary"]:hover {
            background: #1b5e20;
            border-color: #1b5e20;
            color: white;
        }
        .starred-button button,
        .starred-button div.stButton > button,
        .starred-button [data-testid="stBaseButton-secondary"] {
            background: #f9a825;
            border-color: #f9a825;
            color: #1f1f1f;
        }
        .starred-button button:hover,
        .starred-button div.stButton > button:hover,
        .starred-button [data-testid="stBaseButton-secondary"]:hover {
            background: #f57f17;
            border-color: #f57f17;
            color: #1f1f1f;
        }
        .action-link {
            align-items: center;
            border: 1px solid;
            border-radius: 8px;
            display: inline-flex;
            font-weight: 650;
            gap: 0.35rem;
            justify-content: center;
            min-height: 2.5rem;
            text-decoration: none !important;
            width: 100%;
        }
        .action-link.open {
            background: #2e7d32;
            border-color: #2e7d32;
            color: #ffffff !important;
        }
        .action-link.open:hover {
            background: #1b5e20;
            border-color: #1b5e20;
            color: #ffffff !important;
        }
        .action-link.star {
            background: transparent;
            border-color: rgba(128, 128, 128, 0.35);
            color: inherit !important;
        }
        .action-link.starred {
            background: #f9a825;
            border-color: #f9a825;
            color: #1f1f1f !important;
        }
        .action-link.starred:hover {
            background: #f57f17;
            border-color: #f57f17;
            color: #1f1f1f !important;
        }
        .action-link.delete {
            background: #d32f2f;
            border-color: #d32f2f;
            color: #ffffff !important;
        }
        .action-link.delete:hover {
            background: #b71c1c;
            border-color: #b71c1c;
            color: #ffffff !important;
        }
        div.stButton > button[kind="primary"] {
            background: var(--ttd-blue);
            border-color: var(--ttd-blue);
        }
        div.stButton > button:hover {
            border-color: var(--ttd-blue);
            color: var(--ttd-blue-strong);
        }
        div[data-testid="stExpander"] {
            border-color: rgba(128, 128, 128, 0.35);
            border-radius: 8px;
        }
        div[data-testid="stExpander"] summary p {
            color: rgba(128, 128, 128, 0.95);
            font-size: 0.82rem;
            font-weight: 800;
            letter-spacing: 0.03em;
            text-transform: uppercase;
        }
        .ttd-control-panel + div[data-testid="stHorizontalBlock"],
        div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"] {
            align-items: stretch;
        }
        div[data-testid="stExpander"] div.stButton,
        div[data-testid="stExpander"] div.stButton > button {
            min-height: 2.75rem;
            width: 100%;
        }
        div[data-testid="stCheckbox"] {
            width: 100%;
        }
        div[data-testid="stCheckbox"] label {
            align-items: center;
            border: 1px solid rgba(128, 128, 128, 0.35);
            border-radius: 8px;
            background: rgba(128, 128, 128, 0.08);
            display: grid;
            grid-template-columns: minmax(0, 1fr) minmax(2.5rem, 1fr);
            min-height: 2.75rem;
            padding: 0.45rem 0.7rem;
            width: 100%;
        }
        div[data-testid="stCheckbox"] label:hover {
            border-color: var(--ttd-blue);
        }
        div[data-testid="stCheckbox"] label > div:first-child {
            justify-self: end;
            order: 2;
        }
        div[data-testid="stCheckbox"] label > div:last-child {
            min-width: 0;
            order: 1;
            padding-left: 0;
        }
        div[data-testid="stCheckbox"] p {
            font-weight: 650;
            white-space: nowrap;
        }
        div[data-testid="stNumberInput"] {
            align-items: center;
            background: rgba(128, 128, 128, 0.08);
            border: 1px solid rgba(128, 128, 128, 0.35);
            border-radius: 8px;
            box-sizing: border-box;
            display: flex;
            gap: 0.5rem;
            min-height: 2.75rem;
            padding: 0.35rem 0.7rem;
            width: 100%;
        }
        div[data-testid="stNumberInput"]:hover {
            border-color: var(--ttd-blue);
        }
        div[data-testid="stNumberInput"] label {
            flex: 1 1 50%;
            margin: 0;
            min-width: 0;
        }
        div[data-testid="stNumberInput"] label p {
            font-size: 0.78rem;
            font-weight: 700;
            line-height: 1.1;
        }
        div[data-testid="stNumberInput"] [data-baseweb="input"] {
            background: transparent;
            border: 0;
            flex: 1 1 50%;
            min-height: 1.65rem;
            min-width: 0;
        }
        div[data-testid="stNumberInput"] input {
            background: transparent;
            font-weight: 650;
            padding-left: 0;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 8px;
        }
        @media (max-width: 900px) {
            div[data-testid="stHorizontalBlock"] {
                flex-wrap: wrap;
            }
            div[data-testid="stHorizontalBlock"] > div {
                min-width: min(100%, 16rem);
                flex: 1 1 16rem !important;
            }
            [data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] {
                flex-wrap: nowrap;
            }
            [data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] > div {
                min-width: 0;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def material_icon(name: str) -> str:
    return f"<span class='material-symbols-rounded'>{name}</span>"


def page_title(title: str, icon_name: str) -> None:
    st.markdown(
        f"<div class='page-title'>{material_icon(icon_name)}<span>{title}</span></div>",
        unsafe_allow_html=True,
    )


def action_link(label: str, icon_name: str, action: str, item_type: str, item_id: str, class_name: str) -> str:
    href = "?" + urlencode({"action": action, "item_type": item_type, "item_id": item_id})
    return render_link(label, icon_name, href, class_name)


def route_link(label: str, icon_name: str, route: str, class_name: str) -> str:
    href = "?" + urlencode({"route": route.strip("/")})
    return render_link(label, icon_name, href, class_name)


def render_link(label: str, icon_name: str, href: str, class_name: str) -> str:
    return (
        f"<a class='action-link {escape(class_name)}' href='{escape(href)}' target='_self'>"
        f"{material_icon(icon_name)}<span>{escape(label)}</span></a>"
    )
