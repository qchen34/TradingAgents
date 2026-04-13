"""
WebUI 外壳常量（主区与侧栏色板对齐、宽度一致）。

区域命名（沟通用语）详见 docs/ui_shell.md：
  AppCanvas 主画布 | NavRail 导航轨 | NavMenu 主导航 | WorkPane 工作区
"""

from __future__ import annotations

# --- 布局 ---
# 侧栏宽度（px）；与 theme.apply_theme 中 [data-testid="stSidebar"] 同步
SIDEBAR_WIDTH_PX: int = 280

# --- 色板（与主区 #0b1220 + 紫/青扫光同系）---
# NavRail 侧栏壳底色：略深于主画布，形成「轨」而不跳色
COLOR_NAV_RAIL_BASE: str = "#080d16"
COLOR_NAV_RAIL_EDGE: str = "rgba(99, 102, 241, 0.12)"

# 主导航（streamlit-option-menu 内联样式，无法用 CSS 变量）
COLOR_NAV_MENU_TITLE: str = "#cbd5e1"
COLOR_NAV_LINK: str = "#94a3b8"
# option_menu 将 --hover-color 用作 hover 背景色，保持与选中态同色系低透明
COLOR_NAV_LINK_HOVER: str = "rgba(99, 102, 241, 0.12)"
# 选中态：紫调半透明，与 .stApp 径向高光呼应
COLOR_NAV_SELECTED_BG: str = "rgba(99, 102, 241, 0.18)"
COLOR_NAV_SELECTED_TEXT: str = "#f8fafc"
COLOR_NAV_ICON: str = "#94a3b8"
