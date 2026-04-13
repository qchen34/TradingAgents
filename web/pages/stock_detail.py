from __future__ import annotations

import datetime as dt

import streamlit as st

from web.navigation import PAGE_ANALYSIS
from web.pages.report_history import render_report_history
from web.services.indicator_service import get_stock_overview_metrics


def render_stock_detail() -> None:
    st.header("股票详情")
    ticker = st.text_input(
        "股票代码（Ticker）",
        value=st.session_state.get("selected_ticker", "QQQ"),
        key="stock_detail_ticker",
    ).strip().upper()
    st.session_state.selected_ticker = ticker

    tab1, tab2, tab3 = st.tabs(["概览", "最新分析", "历史报告"])

    with tab1:
        if st.button("刷新指标", key="refresh_overview"):
            st.session_state.stock_metrics = get_stock_overview_metrics(ticker)
        metrics = st.session_state.get("stock_metrics")
        if not metrics or metrics.get("ticker") != ticker:
            metrics = get_stock_overview_metrics(ticker)
            st.session_state.stock_metrics = metrics
        if metrics.get("error"):
            st.warning(metrics["error"])
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("HV20", "N/A" if metrics.get("hv20") is None else f"{metrics['hv20']:.2f}%")
            st.metric("HV30", "N/A" if metrics.get("hv30") is None else f"{metrics['hv30']:.2f}%")
            st.metric("IV", "N/A" if metrics.get("iv") is None else f"{metrics['iv']:.2f}%")
        with c2:
            vtoday = metrics.get("volume_today")
            vchg = metrics.get("volume_change_pct")
            st.metric(
                "成交量",
                "N/A" if vtoday is None else f"{vtoday:,.0f}",
                delta="N/A" if vchg is None else f"{vchg:.2f}%",
            )
            st.write(f"均线状态: `{metrics.get('ma_status', 'N/A')}`")
        with c3:
            st.metric("MACD", "N/A" if metrics.get("macd_line") is None else f"{metrics['macd_line']:.4f}")
            st.metric("Signal", "N/A" if metrics.get("macd_signal") is None else f"{metrics['macd_signal']:.4f}")
            st.write(
                "KDJ: "
                + (
                    "N/A"
                    if metrics.get("kdj_k") is None
                    else f"K={metrics['kdj_k']:.2f}, D={metrics['kdj_d']:.2f}, J={metrics['kdj_j']:.2f}"
                )
            )

    with tab2:
        st.info("请在「个股分析」页面触发最新分析。")
        if st.button("跳转到个股分析"):
            st.session_state.current_page = PAGE_ANALYSIS
            st.rerun()
        st.session_state.prefill_ticker = ticker
        st.session_state.prefill_date = dt.date.today().strftime("%Y-%m-%d")

    with tab3:
        render_report_history(default_ticker=ticker)
