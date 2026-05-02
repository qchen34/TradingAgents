"""NavMenu（主导航）：streamlit-option-menu + Bootstrap Icons，色板与 AppCanvas / NavRail 对齐。"""

from __future__ import annotations

import streamlit as st
from streamlit_option_menu import option_menu

from web.navigation import PAGE_STRATEGY
from web.ui_shell import (
    COLOR_NAV_ICON,
    COLOR_NAV_LINK,
    COLOR_NAV_LINK_HOVER,
    COLOR_NAV_MENU_TITLE,
    COLOR_NAV_RAIL_BASE,
    COLOR_NAV_SELECTED_BG,
    COLOR_NAV_SELECTED_TEXT,
)

# 与 web.pages.PAGES 的 key 顺序一致（Bootstrap Icons 名，无 bi- 前缀）
_SIDEBAR_ICONS = [
    "speedometer2",  # 仪表盘
    "graph-up-arrow",  # 个股分析
    "diagram-3",  # 策略
    "funnel",  # 股票筛选
    "building",  # 股票详情
    "wallet2",  # 持仓
]

# 与 NavRail、主画布紫青扫光同系；选中态用 indigo 半透明而非冷灰
_OPTION_MENU_STYLES: dict = {
    "container": {
        "padding": "0.08rem 0 0.45rem 0",
        "margin": "0",
        "background-color": COLOR_NAV_RAIL_BASE,
    },
    "menu-title": {
        "font-size": "0.88rem",
        "font-weight": "600",
        "color": COLOR_NAV_MENU_TITLE,
        "padding": "0.15rem 0.45rem 0.65rem 0.5rem",
        "margin": "0",
        "letter-spacing": "0.02em",
    },
    "icon": {
        "color": COLOR_NAV_ICON,
        "font-size": "1.05rem",
    },
    "nav-link": {
        "font-size": "0.9rem",
        "text-align": "left",
        "margin": "2px 0",
        "padding": "0.5rem 0.68rem",
        "border-radius": "12px",
        "color": COLOR_NAV_LINK,
        "--hover-color": COLOR_NAV_LINK_HOVER,
        "background-color": "transparent",
    },
    "nav-link-selected": {
        "background-color": COLOR_NAV_SELECTED_BG,
        "color": COLOR_NAV_SELECTED_TEXT,
        "font-weight": "600",
        "padding": "0.5rem 0.75rem",
        "border-radius": "12px",
        "box-shadow": "inset 0 0 0 1px rgba(99, 102, 241, 0.22)",
    },
}

_SUB_OPTION_MENU_STYLES: dict = {
    "container": {
        "padding": "0.05rem 0 0.2rem 0",
        "margin": "0",
        "background-color": COLOR_NAV_RAIL_BASE,
    },
    "menu-title": {
        "font-size": "0.78rem",
        "font-weight": "600",
        "color": "#94a3b8",
        "padding": "0.05rem 0.45rem 0.35rem 0.95rem",
        "margin": "0",
        "letter-spacing": "0.015em",
        "text-transform": "uppercase",
    },
    "icon": {
        "color": "#8b9ad1",
        "font-size": "0.95rem",
    },
    "nav-link": {
        "font-size": "0.86rem",
        "text-align": "left",
        "margin": "2px 0",
        "padding": "0.42rem 0.65rem 0.42rem 1.08rem",
        "border-radius": "10px",
        "color": "#a8b3c7",
        "--hover-color": "rgba(99, 102, 241, 0.10)",
        "background-color": "transparent",
    },
    "nav-link-selected": {
        "background-color": "rgba(99, 102, 241, 0.14)",
        "color": "#e2e8f0",
        "font-weight": "600",
        "padding": "0.42rem 0.65rem 0.42rem 1.08rem",
        "border-radius": "10px",
        "box-shadow": "inset 0 0 0 1px rgba(129, 140, 248, 0.28)",
    },
}


def render_sidebar_navigation(page_names: list[str], current_page: str) -> str:
    """在 st.sidebar 内调用。返回当前选中的页面名（与 page_names 中某项一致）。"""
    if len(_SIDEBAR_ICONS) != len(page_names):
        icons: list[str | None] = ["circle"] * len(page_names)
    else:
        icons = list(_SIDEBAR_ICONS)

    try:
        default_index = page_names.index(current_page)
    except ValueError:
        default_index = 0

    selected = option_menu(
        "个性化交易智能体应用",
        page_names,
        icons=icons,
        menu_icon="cpu",
        default_index=default_index,
        orientation="vertical",
        styles=_OPTION_MENU_STYLES,
        key="ta_sidebar_option_menu",
    )

    active_page = str(selected) if selected else (current_page if current_page in page_names else page_names[0])
    if active_page == PAGE_STRATEGY:
        strategy_options = ["LRS TQQQ策略", "Wheel策略"]
        default_sub = str(st.session_state.get("strategy_sub_menu", strategy_options[0]))
        try:
            sub_idx = strategy_options.index(default_sub)
        except ValueError:
            sub_idx = 0
        sub_selected = option_menu(
            "子策略",
            strategy_options,
            icons=["bullseye", "arrow-repeat"],
            menu_icon="chevron-double-right",
            default_index=sub_idx,
            orientation="vertical",
            styles=_SUB_OPTION_MENU_STYLES,
            key="strategy_sub_menu_option_menu",
        )
        st.session_state["strategy_sub_menu"] = sub_selected or strategy_options[0]

    if selected:
        return str(selected)
    return current_page if current_page in page_names else page_names[0]
