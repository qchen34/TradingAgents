from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import yfinance as yf


def _history(ticker: str, days: int = 260) -> pd.DataFrame:
    end = datetime.utcnow()
    start = end - timedelta(days=days * 2)
    df = yf.Ticker(ticker).history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
    return df.dropna()


def _annualized_vol(close: pd.Series, window: int = 20) -> float | None:
    if len(close) < window + 1:
        return None
    ret = close.pct_change().dropna()
    v = ret.tail(window).std() * math.sqrt(252)
    return float(v * 100)


def _ma_status(close: pd.Series) -> str:
    if close.empty:
        return "N/A"
    c = close.iloc[-1]
    ma20 = close.tail(20).mean() if len(close) >= 20 else None
    ma50 = close.tail(50).mean() if len(close) >= 50 else None
    ma200 = close.tail(200).mean() if len(close) >= 200 else None
    bits = []
    if ma20:
        bits.append(f"Price {'>' if c > ma20 else '<='} MA20")
    if ma50:
        bits.append(f"Price {'>' if c > ma50 else '<='} MA50")
    if ma200:
        bits.append(f"Price {'>' if c > ma200 else '<='} MA200")
    return ", ".join(bits) if bits else "N/A"


def _macd(close: pd.Series) -> tuple[float | None, float | None]:
    if len(close) < 35:
        return None, None
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    line = ema12 - ema26
    signal = line.ewm(span=9, adjust=False).mean()
    return float(line.iloc[-1]), float(signal.iloc[-1])


def _kdj(df: pd.DataFrame, n: int = 9) -> tuple[float | None, float | None, float | None]:
    if len(df) < n:
        return None, None, None
    low = df["Low"].rolling(n).min()
    high = df["High"].rolling(n).max()
    rsv = (df["Close"] - low) / (high - low) * 100
    k = rsv.ewm(alpha=1 / 3, adjust=False).mean()
    d = k.ewm(alpha=1 / 3, adjust=False).mean()
    j = 3 * k - 2 * d
    return float(k.iloc[-1]), float(d.iloc[-1]), float(j.iloc[-1])


def _iv_proxy(ticker: str) -> float | None:
    # Best-effort: derive from nearest option chain if available.
    try:
        t = yf.Ticker(ticker)
        expirations = t.options
        if not expirations:
            return None
        chain = t.option_chain(expirations[0])
        calls = chain.calls
        if calls.empty or "impliedVolatility" not in calls:
            return None
        iv = calls["impliedVolatility"].dropna()
        if iv.empty:
            return None
        return float(iv.median() * 100)
    except Exception:
        return None


def get_stock_overview_metrics(ticker: str) -> dict[str, Any]:
    try:
        df = _history(ticker)
        if df.empty:
            return {"error": f"{ticker} 暂无价格数据。"}
        close = df["Close"]
        vol = df["Volume"]
        hv20 = _annualized_vol(close, 20)
        hv30 = _annualized_vol(close, 30)
        iv = _iv_proxy(ticker)
        macd_line, macd_sig = _macd(close)
        k, d, j = _kdj(df)
        vol_today = float(vol.iloc[-1]) if not vol.empty else None
        vol_prev = float(vol.iloc[-2]) if len(vol) > 1 else None
        vol_chg = (
            ((vol_today - vol_prev) / vol_prev * 100) if vol_prev and vol_today is not None else None
        )
        return {
            "ticker": ticker,
            "hv20": hv20,
            "hv30": hv30,
            "iv": iv,
            "volume_today": vol_today,
            "volume_prev": vol_prev,
            "volume_change_pct": vol_chg,
            "ma_status": _ma_status(close),
            "macd_line": macd_line,
            "macd_signal": macd_sig,
            "kdj_k": k,
            "kdj_d": d,
            "kdj_j": j,
            "error": "",
        }
    except Exception as exc:
        return {"error": str(exc)}
