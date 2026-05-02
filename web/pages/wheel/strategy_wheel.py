import streamlit as st

from web.pages.wheel.strategy_aggressive import render_tab as render_aggressive_tab
from web.pages.wheel.strategy_conservative import render_tab as render_conservative_tab
from web.pages.wheel.strategy_neutral import render_tab as render_neutral_tab
from web.pages.wheel.wheel_shared import render_history_tab


def render_wheel_page() -> None:
    st.subheader("Wheel策略")
    tabs = st.tabs(["激进", "中性", "保守", "历史报告"])
    with tabs[0]:
        render_aggressive_tab(state_prefix="wheel", default_underlying="TQQQ", default_signal="QQQ")
    with tabs[1]:
        render_neutral_tab(state_prefix="wheel", default_underlying="TQQQ", default_signal="QQQ")
    with tabs[2]:
        render_conservative_tab(state_prefix="wheel", default_underlying="TQQQ", default_signal="QQQ")
    with tabs[3]:
        render_history_tab("wheel")

