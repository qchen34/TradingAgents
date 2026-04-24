from __future__ import annotations

import math

import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf

_DARK_BG = "#0f172a"
_AXES_BG = "#1e293b"
_GRID_COLOR = "#334155"
_TEXT_COLOR = "#cbd5e1"
_TICK_COLOR = "#94a3b8"


def apply_dark_style(fig: plt.Figure, *axes) -> None:
    fig.patch.set_facecolor(_DARK_BG)
    for ax in axes:
        ax.set_facecolor(_AXES_BG)
        ax.tick_params(colors=_TICK_COLOR)
        ax.xaxis.label.set_color(_TEXT_COLOR)
        ax.yaxis.label.set_color(_TEXT_COLOR)
        ax.title.set_color(_TEXT_COLOR)
        for s in ax.spines.values():
            s.set_color(_GRID_COLOR)
        ax.grid(True, color=_GRID_COLOR, alpha=0.45)
        lg = ax.get_legend()
        if lg is not None:
            lg.get_frame().set_facecolor(_AXES_BG)
            lg.get_frame().set_edgecolor(_GRID_COLOR)
            for t in lg.get_texts():
                t.set_color(_TEXT_COLOR)


def close_series(ticker: str, start: str, end: str) -> pd.Series:
    df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if df.empty:
        raise RuntimeError(f"未获取到 {ticker} 数据")
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    s = close.dropna()
    s.name = ticker
    return s


def annual_to_daily(rate: float, periods: int = 252) -> float:
    return (1.0 + rate) ** (1.0 / periods)


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    d = series.diff()
    up = d.clip(lower=0).ewm(alpha=1.0 / period, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1.0 / period, adjust=False).mean()
    rs = up / dn.replace(0, math.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_price(spot: float, strike: float, t_years: float, rate: float, sigma: float, kind: str) -> float:
    if t_years <= 0:
        if kind == "put":
            return max(strike - spot, 0.0)
        return max(spot - strike, 0.0)
    sigma = max(sigma, 1e-6)
    if spot <= 0 or strike <= 0:
        return 0.0
    d1 = (math.log(spot / strike) + (rate + 0.5 * sigma * sigma) * t_years) / (sigma * math.sqrt(t_years))
    d2 = d1 - sigma * math.sqrt(t_years)
    if kind == "put":
        return strike * math.exp(-rate * t_years) * norm_cdf(-d2) - spot * norm_cdf(-d1)
    return spot * norm_cdf(d1) - strike * math.exp(-rate * t_years) * norm_cdf(d2)

