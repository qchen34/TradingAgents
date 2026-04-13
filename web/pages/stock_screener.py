from __future__ import annotations

import streamlit as st
import yfinance as yf

from web.navigation import PAGE_STOCK_DETAIL

DEFAULT_TICKERS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "GOOGL",
    "TSLA",
    "AMD",
    "AVGO",
    "NFLX",
]


def _row(ticker: str) -> dict:
    try:
        f = yf.Ticker(ticker).fast_info
        price = float(f.get("lastPrice")) if f.get("lastPrice") is not None else None
        prev = float(f.get("previousClose")) if f.get("previousClose") is not None else None
        volume = float(f.get("lastVolume")) if f.get("lastVolume") is not None else None
        chg = ((price - prev) / prev * 100) if price is not None and prev else None
        return {"ticker": ticker, "price": price, "change_pct": chg, "volume": volume}
    except Exception:
        return {"ticker": ticker, "price": None, "change_pct": None, "volume": None}


def render_stock_screener() -> None:
    st.header("股票筛选")
    q = st.text_input("搜索 ticker", value=st.session_state.get("screener_query", ""))
    st.session_state.screener_query = q

    tickers = [t for t in DEFAULT_TICKERS if q.strip().upper() in t]
    rows = [_row(t) for t in tickers]
    sort_by = st.selectbox("排序", ["change_pct", "volume", "ticker"], index=0)
    rows.sort(key=lambda r: (r.get(sort_by) is None, r.get(sort_by)), reverse=sort_by != "ticker")

    for r in rows:
        c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
        with c1:
            st.write(f"**{r['ticker']}**")
        with c2:
            st.write("N/A" if r["price"] is None else f"{r['price']:.2f}")
        with c3:
            st.write("N/A" if r["change_pct"] is None else f"{r['change_pct']:.2f}%")
        with c4:
            if st.button("查看", key=f"open_{r['ticker']}"):
                st.session_state.selected_ticker = r["ticker"]
                st.session_state.current_page = PAGE_STOCK_DETAIL
                st.rerun()
        st.markdown("---")
