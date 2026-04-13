from __future__ import annotations

import streamlit as st

from web.services.portfolio_store import load_portfolio, upsert_position


def render_portfolio() -> None:
    st.header("持仓")
    c1, c2, c3 = st.columns(3)
    with c1:
        ticker = st.text_input("股票代码（Ticker）", value="QQQ").strip().upper()
    with c2:
        qty = st.number_input("数量", min_value=0.0, step=1.0, value=10.0)
    with c3:
        buy = st.number_input("买入价", min_value=0.0, step=0.01, value=100.0)
    if st.button("添加 / 合并持仓"):
        if not ticker:
            st.error("股票代码不能为空。")
        else:
            rows = upsert_position(ticker, float(qty), float(buy))
            st.success("已更新持仓。")
            st.session_state.portfolio_rows = rows
    rows = st.session_state.get("portfolio_rows") or load_portfolio()
    st.session_state.portfolio_rows = rows
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("暂无持仓记录。")
