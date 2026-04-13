import streamlit as st

from web.navigation import PAGE_DASHBOARD
from web.pages import PAGES
from web.sidebar_nav import render_sidebar_navigation
from web.theme import apply_theme


def _init_session_state() -> None:
    defaults = {
        "current_page": PAGE_DASHBOARD,
        "ui_mode": "idle",
        "show_config": False,
        "event_log": [],
        "runtime_stage": "",
        "latest_run_dir": "",
        "last_params": None,
        "selected_params_summary": "",
        "active_output_dir": "",
        "runtime_stats": {},
        "selected_ticker": "QQQ",
        "error": "",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


st.set_page_config(page_title="TradingAgents 控制台", layout="wide")
_init_session_state()
apply_theme()

page_names = list(PAGES.keys())
if st.session_state.current_page not in page_names:
    st.session_state.current_page = page_names[0]

with st.sidebar:
    st.session_state.current_page = render_sidebar_navigation(
        page_names,
        st.session_state.current_page,
    )

PAGES[st.session_state.current_page]()
