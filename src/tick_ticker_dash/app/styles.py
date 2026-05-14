from __future__ import annotations

from html import escape
from urllib.parse import urlencode

import streamlit as st
import streamlit.components.v1 as components


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
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 8px;
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
    return (
        f"<a class='action-link {escape(class_name)}' href='{escape(href)}' target='_self'>"
        f"{material_icon(icon_name)}<span>{escape(label)}</span></a>"
    )


def inject_dynamic_button_styles() -> None:
    components.html(
        """
        <script>
        const doc = window.parent.document;
        const danger = {
          background: "#d32f2f",
          borderColor: "#d32f2f",
          color: "#ffffff"
        };
        const dangerHover = {
          background: "#b71c1c",
          borderColor: "#b71c1c",
          color: "#ffffff"
        };
        const starred = {
          background: "#f9a825",
          borderColor: "#f9a825",
          color: "#1f1f1f"
        };
        const starredHover = {
          background: "#f57f17",
          borderColor: "#f57f17",
          color: "#1f1f1f"
        };
        function paint(button, style) {
          Object.assign(button.style, style);
          button.querySelectorAll("*").forEach((child) => {
            child.style.color = style.color;
          });
        }
        function alignLeft(button) {
          button.style.justifyContent = "flex-start";
          button.style.textAlign = "left";
          button.querySelectorAll("div, p, span, [data-testid='stMarkdownContainer']").forEach((child) => {
            child.style.justifyContent = "flex-start";
            child.style.textAlign = "left";
            if (child.tagName === "P" || child.getAttribute("data-testid") === "stMarkdownContainer") {
              child.style.width = "100%";
            }
          });
        }
        function wireHover(button, normal, hover) {
          button.onmouseenter = () => paint(button, hover);
          button.onmouseleave = () => paint(button, normal);
        }
        function applyStyles() {
          doc.querySelectorAll("button").forEach((button) => {
            const text = (button.innerText || button.getAttribute("aria-label") || "").trim();
            alignLeft(button);
            if (text.includes("Delete")) {
              paint(button, danger);
              wireHover(button, danger, dangerHover);
            }
            if (text === "Open") {
              const normal = { background: "#2e7d32", borderColor: "#2e7d32", color: "#ffffff" };
              const hover = { background: "#1b5e20", borderColor: "#1b5e20", color: "#ffffff" };
              paint(button, normal);
              wireHover(button, normal, hover);
            }
            if (text === "Starred" || text === "Unstar") {
              paint(button, starred);
              wireHover(button, starred, starredHover);
            }
          });
        }
        applyStyles();
        const observer = new MutationObserver(applyStyles);
        observer.observe(doc.body, { childList: true, subtree: true });
        </script>
        """,
        height=0,
        width=0,
    )
