from __future__ import annotations

from pathlib import Path

import streamlit as st

from web.history import list_report_runs
from web.report_viewer import render_report_focused


def _ticker_from_dir(name: str) -> str:
    if "_" not in name:
        return name
    return name.rsplit("_", 1)[0].upper()


def render_report_history(default_ticker: str | None = None) -> None:
    st.subheader("历史报告")
    runs = list_report_runs("reports")
    if not runs:
        st.info("暂无历史报告。")
        return
    tickers = sorted({_ticker_from_dir(r.name) for r in runs})
    if default_ticker and default_ticker in tickers:
        t_idx = tickers.index(default_ticker)
    else:
        t_idx = 0
    ticker = st.selectbox("股票代码", tickers, index=t_idx)
    by_ticker = [r for r in runs if _ticker_from_dir(r.name) == ticker]
    labels = [f"{r.name} · {r.status}" for r in by_ticker]
    idx = st.selectbox("日期 / 运行", list(range(len(labels))), format_func=lambda i: labels[i])
    target = by_ticker[idx].path
    if Path(target).exists():
        st.caption(f"路径：`{target}`")
        render_report_focused(str(target))
    else:
        st.warning("目录不存在。")
