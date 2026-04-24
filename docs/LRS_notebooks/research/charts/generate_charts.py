#!/usr/bin/env python3
"""Generate static PNG charts for LRS TQQQ research HTML (Ch.3–Ch.4).

Reuses core logic from web/pages/backtesting.py (no Streamlit).
LRS simulation: idle cash earns 4% annualized, compounded each trading day.
Outputs to this directory: chart_a_summary.png … chart_j_rolling.png
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import yfinance as yf

# ─── Paths ───────────────────────────────────────────────────────────────────
HERE = Path(__file__).resolve().parent

# ─── Matplotlib / CJK ────────────────────────────────────────────────────────
plt.rcParams["font.sans-serif"] = [
    "PingFang SC",
    "Hiragino Sans GB",
    "Noto Sans CJK SC",
    "Microsoft YaHei",
    "SimHei",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False

# ─── Dark theme (aligned with strategy_shared.apply_dark_style) ─────────────
_DARK_BG = "#0f172a"
_AXES_BG = "#1e293b"
_GRID_COLOR = "#334155"
_TEXT_COLOR = "#cbd5e1"
_TICK_COLOR = "#94a3b8"


def _apply_dark(fig: plt.Figure, *axes) -> None:
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


_INITIAL_CAPITAL = 10_000.0
_COST_PER_SIDE = 1.99
_DISTANCE_THRESH = 6.0
_WHIPSAW_DAYS = 10
_CASH_YIELD_ANNUAL = 0.04
_CASH_YIELD_DAILY = (1.0 + _CASH_YIELD_ANNUAL) ** (1.0 / 252.0)


def _accrue_cash_yield(cash: float) -> float:
    """Idle cash: 4% annual, compounded per trading day."""
    return cash * _CASH_YIELD_DAILY

_PERIOD_SPECS: dict[str, dict] = {
    "2y": {
        "label": "近 2 年",
        "fetch_type": "period",
        "dl_period": "3y",
        "target_days": 504,
    },
    "3y": {
        "label": "近 3 年",
        "fetch_type": "period",
        "dl_period": "4y",
        "target_days": 756,
    },
    "5y": {
        "label": "近 5 年",
        "fetch_type": "period",
        "dl_period": "6y",
        "target_days": 1260,
    },
    "10y": {
        "label": "近 10 年",
        "fetch_type": "range",
        "dl_start": None,
        "dl_end": None,
        "target_days": 2520,
    },
    "15y": {
        "label": "近 15 年",
        "fetch_type": "range",
        "dl_start": "2009-01-01",
        "dl_end": None,
        "target_days": 3780,
    },
}

_PERIOD_ORDER = ["2y", "3y", "5y", "10y", "15y"]


def _norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df


def _fetch_by_period(dl_period: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    qqq = yf.download("QQQ", period=dl_period, auto_adjust=True, progress=False)
    tqqq = yf.download("TQQQ", period=dl_period, auto_adjust=True, progress=False)
    return _norm_cols(qqq), _norm_cols(tqqq)


def _fetch_by_range(start: str, end: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    qqq = yf.download("QQQ", start=start, end=end, auto_adjust=True, progress=False)
    tqqq = yf.download("TQQQ", start=start, end=end, auto_adjust=True, progress=False)
    return _norm_cols(qqq), _norm_cols(tqqq)


def _ensure_ohlcv(qqq_df: pd.DataFrame, tqqq_df: pd.DataFrame) -> None:
    if qqq_df is None or tqqq_df is None or qqq_df.empty or tqqq_df.empty:
        raise RuntimeError("QQQ or TQQQ download returned empty data — retry later.")
    if "Close" not in qqq_df.columns or "Close" not in tqqq_df.columns:
        raise RuntimeError("Missing Close column in downloaded frames.")


def _fetch(period_key: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    spec = _PERIOD_SPECS[period_key]
    if spec["fetch_type"] == "period":
        return _fetch_by_period(spec["dl_period"])
    start = spec.get("dl_start")
    end = spec.get("dl_end")
    end_dt = datetime.now()
    if end is None:
        end = end_dt.strftime("%Y-%m-%d")
    if start is None:
        start_dt = end_dt - timedelta(days=365 * 11)
        start = start_dt.strftime("%Y-%m-%d")
    return _fetch_by_range(start, end)


def _get_effective_start(
    qqq_full: pd.Series,
    tqqq_full: pd.Series,
    period_key: str,
) -> pd.Timestamp:
    if len(tqqq_full.index) == 0:
        raise RuntimeError("TQQQ series is empty — check download.")
    spec = _PERIOD_SPECS[period_key]
    if spec.get("eff_start"):
        ts = pd.Timestamp(spec["eff_start"])
        return max(ts, qqq_full.index[0])
    n = spec.get("target_days", 504)
    offset = max(0, len(qqq_full) - n)
    eff = qqq_full.index[offset]
    return max(eff, tqqq_full.index[0])


def _streak(s: pd.Series) -> pd.Series:
    groups = (s != s.shift()).cumsum()
    return (s.groupby(groups).cumcount() + 1).where(s, 0)


def _build_signals(qqq_close: pd.Series, ma_len: int = 200) -> pd.DataFrame:
    ma = qqq_close.rolling(ma_len).mean()
    a1 = qqq_close > ma
    slope = (ma - ma.shift(20)) / ma.shift(20) * 100
    a2 = slope > -0.5
    a3 = _streak(a1) >= 3
    signal = a1 & a2 & a3
    entry_signal = signal & ~signal.shift(1).fillna(False)
    below = qqq_close < ma
    exit_signal = below & below.shift(1).fillna(False)
    cross = a1 & ~a1.shift(1).fillna(False)
    return pd.DataFrame(
        {
            "qqq": qqq_close,
            f"ma{ma_len}": ma,
            "a1": a1,
            "a2": a2,
            "a3": a3,
            "signal": signal,
            "entry_signal": entry_signal,
            "exit_signal": exit_signal,
            "cross": cross,
        }
    )


def _allocation(dist: float) -> tuple[str, float]:
    if dist <= _DISTANCE_THRESH:
        return "Direct Buy", 2 / 3
    if dist <= 15.0:
        return "Split", 1 / 3
    return "Split(>15%)", 1 / 3


@dataclass
class Trade:
    entry_date: pd.Timestamp
    entry_price: float
    entry_mode: str
    shares: float
    cost_buy: float
    exit_date: pd.Timestamp | None = None
    exit_price: float | None = None
    cost_sell: float = 0.0
    forced_exit: bool = False

    @property
    def holding_days(self) -> int:
        if self.exit_date is None:
            return 0
        return (self.exit_date - self.entry_date).days

    @property
    def gross_pnl(self) -> float:
        if self.exit_price is None:
            return 0.0
        return (self.exit_price - self.entry_price) * self.shares

    @property
    def net_pnl(self) -> float:
        return self.gross_pnl - self.cost_buy - self.cost_sell

    @property
    def return_pct(self) -> float:
        invested = self.entry_price * self.shares + self.cost_buy
        return (self.net_pnl / invested * 100) if invested > 0 else 0.0

    @property
    def is_whipsaw(self) -> bool:
        return self.holding_days <= _WHIPSAW_DAYS and self.net_pnl < 0


def _simulate(
    sig: pd.DataFrame,
    tqqq_close: pd.Series,
    trade_start: pd.Timestamp | None = None,
) -> tuple[list[Trade], pd.Series]:
    tqqq = tqqq_close.reindex(sig.index, method="ffill")
    cross_dates = sig.index[sig["cross"]].tolist()
    cash = _INITIAL_CAPITAL
    shares = 0.0
    in_pos = False
    current: Trade | None = None
    trades: list[Trade] = []
    equity: dict = {}
    first_day = True

    for date in sig.index:
        if trade_start is not None and date < trade_start:
            continue

        cash = _accrue_cash_yield(cash)

        raw = tqqq.get(date)
        if raw is None or (isinstance(raw, float) and math.isnan(raw)):
            equity[date] = cash + shares * (
                float(tqqq.dropna().iloc[-1]) if shares > 0 else 0.0
            )
            first_day = False
            continue
        price = float(raw)

        if in_pos and current is not None and bool(sig.at[date, "exit_signal"]):
            cash += shares * price - _COST_PER_SIDE
            current.exit_date = date
            current.exit_price = price
            current.cost_sell = _COST_PER_SIDE
            trades.append(current)
            shares = 0.0
            in_pos = False
            current = None

        is_entry = bool(sig.at[date, "entry_signal"])
        if first_day and not in_pos and bool(sig.at[date, "signal"]):
            is_entry = True
        first_day = False

        if not in_pos and is_entry:
            prior = [d for d in cross_dates if d <= date]
            cross_date = prior[-1] if prior else date
            cross_raw = tqqq.get(cross_date)
            cross_price = (
                float(cross_raw)
                if cross_raw is not None and not math.isnan(float(cross_raw))
                else price
            )
            dist = (price - cross_price) / cross_price * 100 if cross_price > 0 else 0.0
            mode, frac = _allocation(dist)
            invest = cash * frac - _COST_PER_SIDE
            if invest > 0:
                n = math.floor(invest / price)
                if n >= 1:
                    cash -= n * price + _COST_PER_SIDE
                    shares = float(n)
                    in_pos = True
                    current = Trade(
                        entry_date=date,
                        entry_price=price,
                        entry_mode=mode,
                        shares=shares,
                        cost_buy=_COST_PER_SIDE,
                    )
        equity[date] = cash + shares * price

    if in_pos and current is not None and shares > 0:
        last_date = sig.index[-1]
        last_price = float(tqqq.iloc[-1])
        cash += shares * last_price - _COST_PER_SIDE
        current.exit_date = last_date
        current.exit_price = last_price
        current.cost_sell = _COST_PER_SIDE
        current.forced_exit = True
        trades.append(current)
        equity[last_date] = cash

    return trades, pd.Series(equity)


def _max_dd(equity: pd.Series) -> float:
    peak = equity.cummax()
    return float(((equity - peak) / peak).min() * 100)


def _ts_key(ts: pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(ts).normalize()


def _january_first_trading_days(
    index: pd.DatetimeIndex,
    t_start: pd.Timestamp,
    t_end: pd.Timestamp,
    n: int = 5,
) -> list[pd.Timestamp]:
    """First trading day of January for each year, only if in [t_start, t_end]."""
    out: list[pd.Timestamp] = []
    for y in range(t_start.year, t_end.year + 1):
        iy = index[index.year == y]
        if len(iy) == 0:
            continue
        jan_first = iy[0]
        if jan_first.month != 1:
            continue
        if jan_first < t_start or jan_first > t_end:
            continue
        out.append(jan_first)
        if len(out) >= n:
            break
    return out


def _equity_dca_buyhold(
    close: pd.Series,
    idx: pd.DatetimeIndex,
    contrib_dates: list[pd.Timestamp],
    amount: float,
) -> pd.Series:
    """Buy fractional shares at each contribution; 100% invested after each buy."""
    cset = {_ts_key(d) for d in contrib_dates}
    shares = 0.0
    out: dict = {}
    for date in idx:
        if _ts_key(date) in cset:
            p = float(close.loc[date])
            if p > 0:
                shares += amount / p
        out[date] = shares * float(close.loc[date])
    return pd.Series(out)


def _simulate_dca(
    sig: pd.DataFrame,
    tqqq_close: pd.Series,
    trade_start: pd.Timestamp | None,
    contrib_dates: list[pd.Timestamp],
    contrib_amt: float = 2000.0,
) -> tuple[list[Trade], pd.Series]:
    """Same LRS rules as _simulate, but cash receives `contrib_amt` on each contribution day."""
    tqqq = tqqq_close.reindex(sig.index, method="ffill")
    cross_dates = sig.index[sig["cross"]].tolist()
    cset = {_ts_key(d) for d in contrib_dates}
    cash = 0.0
    shares = 0.0
    in_pos = False
    current: Trade | None = None
    trades: list[Trade] = []
    equity: dict = {}
    first_day = True

    for date in sig.index:
        if trade_start is not None and date < trade_start:
            continue

        cash = _accrue_cash_yield(cash)
        if _ts_key(date) in cset:
            cash += contrib_amt

        raw = tqqq.get(date)
        if raw is None or (isinstance(raw, float) and math.isnan(raw)):
            equity[date] = cash + shares * (
                float(tqqq.dropna().iloc[-1]) if shares > 0 else 0.0
            )
            first_day = False
            continue
        price = float(raw)

        if in_pos and current is not None and bool(sig.at[date, "exit_signal"]):
            cash += shares * price - _COST_PER_SIDE
            current.exit_date = date
            current.exit_price = price
            current.cost_sell = _COST_PER_SIDE
            trades.append(current)
            shares = 0.0
            in_pos = False
            current = None

        is_entry = bool(sig.at[date, "entry_signal"])
        if first_day and not in_pos and bool(sig.at[date, "signal"]):
            is_entry = True
        first_day = False

        if not in_pos and is_entry:
            prior = [d for d in cross_dates if d <= date]
            cross_date = prior[-1] if prior else date
            cross_raw = tqqq.get(cross_date)
            cross_price = (
                float(cross_raw)
                if cross_raw is not None and not math.isnan(float(cross_raw))
                else price
            )
            dist = (price - cross_price) / cross_price * 100 if cross_price > 0 else 0.0
            mode, frac = _allocation(dist)
            invest = cash * frac - _COST_PER_SIDE
            if invest > 0:
                n = math.floor(invest / price)
                if n >= 1:
                    cash -= n * price + _COST_PER_SIDE
                    shares = float(n)
                    in_pos = True
                    current = Trade(
                        entry_date=date,
                        entry_price=price,
                        entry_mode=mode,
                        shares=shares,
                        cost_buy=_COST_PER_SIDE,
                    )
        equity[date] = cash + shares * price

    if in_pos and current is not None and shares > 0:
        last_date = sig.index[-1]
        last_price = float(tqqq.iloc[-1])
        cash += shares * last_price - _COST_PER_SIDE
        current.exit_date = last_date
        current.exit_price = last_price
        current.cost_sell = _COST_PER_SIDE
        current.forced_exit = True
        trades.append(current)
        equity[last_date] = cash

    return trades, pd.Series(equity)


def _total_return_vs_principal(equity: pd.Series, principal: float) -> float:
    return (float(equity.iloc[-1]) / principal - 1.0) * 100.0


def _cagr_on_principal(
    equity: pd.Series, principal: float, eff_start: pd.Timestamp | None = None
) -> float:
    start_dt = eff_start if eff_start is not None else equity.index[0]
    years = max((equity.index[-1] - start_dt).days / 365.25, 0.001)
    fv = float(equity.iloc[-1])
    return ((fv / principal) ** (1.0 / years) - 1.0) * 100.0


def run_dca_5y_analysis(r: dict | None = None) -> dict:
    """DCA: $2,000 on each of 5 January first trading days; total $10,000. Window = 5y."""
    r = r if r is not None else run_period("5y")
    t_start = r["t_start"]
    qqq_eff = r["qqq_eff"]
    t_end = qqq_eff.index[-1]
    idx = qqq_eff.index

    contrib = _january_first_trading_days(idx, t_start, t_end, n=5)
    if len(contrib) < 5:
        raise RuntimeError(
            f"Need 5 January contribution days in window; got {len(contrib)}: {contrib}"
        )
    amt = 2000.0
    principal = 5 * amt

    # Full-history signals (same as run_from_frames / run_period)
    qqq_df, tqqq_df = _fetch("5y")
    _ensure_ohlcv(qqq_df, tqqq_df)
    qqq_full = qqq_df["Close"].squeeze().dropna()
    tqqq_full = tqqq_df["Close"].squeeze().dropna()
    sig = _build_signals(qqq_full, ma_len=200)

    trades_dca, eq_dca = _simulate_dca(sig, tqqq_full, t_start, contrib, contrib_amt=amt)
    eq_dca = eq_dca.reindex(idx, method="ffill").bfill()

    tqqq_eff = r["tqqq_eff"]
    eq_qqq_dca = _equity_dca_buyhold(qqq_eff, idx, contrib, amt)
    eq_tqq_dca = _equity_dca_buyhold(tqqq_eff, idx, contrib, amt)

    # Lump-sum (existing in r)
    eq_lrs = r["equity"].reindex(idx, method="ffill").bfill()
    bh_q = r["bh_qqq"].reindex(idx, method="ffill")
    bh_t = r["bh_tqqq"].reindex(idx, method="ffill")

    dca_start = contrib[0]
    ret = lambda eq, p=principal: _total_return_vs_principal(eq, p)

    def cagr_lump(eq: pd.Series) -> float:
        return _cagr_on_principal(eq, principal, eff_start=t_start)

    def cagr_dca_m(eq: pd.Series) -> float:
        return _cagr_on_principal(eq, principal, eff_start=dca_start)

    def sharpe_lump(eq: pd.Series) -> float:
        sl = eq.loc[eq.index >= t_start]
        daily_ret = sl.pct_change().dropna()
        ann_vol = daily_ret.std() * (252**0.5) if len(daily_ret) > 1 else 1.0
        cg = cagr_lump(eq) / 100.0
        return (cg - 0.04) / ann_vol if ann_vol > 0 else 0.0

    def sharpe_dca_m(eq: pd.Series) -> float:
        sl = eq.loc[eq.index >= dca_start]
        daily_ret = sl.pct_change().dropna()
        ann_vol = daily_ret.std() * (252**0.5) if len(daily_ret) > 1 else 1.0
        cg = cagr_dca_m(eq) / 100.0
        return (cg - 0.04) / ann_vol if ann_vol > 0 else 0.0

    def dd_lump(eq: pd.Series) -> float:
        return _max_dd(eq.loc[eq.index >= t_start])

    def dd_dca(eq: pd.Series) -> float:
        return _max_dd(eq.loc[eq.index >= dca_start])

    return {
        "t_start": t_start,
        "t_end": t_end,
        "dca_start": dca_start,
        "contrib_dates": contrib,
        "principal": principal,
        "idx": idx,
        "eq_lrs_lump": eq_lrs,
        "eq_qqq_lump": bh_q,
        "eq_tqq_lump": bh_t,
        "eq_lrs_dca": eq_dca,
        "eq_qqq_dca": eq_qqq_dca,
        "eq_tqq_dca": eq_tqq_dca,
        "trades_dca": trades_dca,
        "metrics": {
            "lump": {
                "LRS": {
                    "total_pct": ret(eq_lrs),
                    "cagr": cagr_lump(eq_lrs),
                    "sharpe": sharpe_lump(eq_lrs),
                    "max_dd": dd_lump(eq_lrs),
                },
                "QQQ B&H": {
                    "total_pct": ret(bh_q),
                    "cagr": cagr_lump(bh_q),
                    "sharpe": sharpe_lump(bh_q),
                    "max_dd": dd_lump(bh_q),
                },
                "TQQQ B&H": {
                    "total_pct": ret(bh_t),
                    "cagr": cagr_lump(bh_t),
                    "sharpe": sharpe_lump(bh_t),
                    "max_dd": dd_lump(bh_t),
                },
            },
            "dca": {
                "LRS": {
                    "total_pct": ret(eq_dca),
                    "cagr": cagr_dca_m(eq_dca),
                    "sharpe": sharpe_dca_m(eq_dca),
                    "max_dd": dd_dca(eq_dca),
                    "n_trades": len(trades_dca),
                },
                "QQQ B&H": {
                    "total_pct": ret(eq_qqq_dca),
                    "cagr": cagr_dca_m(eq_qqq_dca),
                    "sharpe": sharpe_dca_m(eq_qqq_dca),
                    "max_dd": dd_dca(eq_qqq_dca),
                },
                "TQQQ B&H": {
                    "total_pct": ret(eq_tqq_dca),
                    "cagr": cagr_dca_m(eq_tqq_dca),
                    "sharpe": sharpe_dca_m(eq_tqq_dca),
                    "max_dd": dd_dca(eq_tqq_dca),
                },
            },
        },
    }


def run_dca_for_period(period_key: str) -> dict:
    """DCA: $2,000 on each Jan 1st trading day in window, up to 5 times; principal = 2000 × n."""
    r = run_period(period_key)
    t_start = r["t_start"]
    qqq_eff = r["qqq_eff"]
    t_end = qqq_eff.index[-1]
    idx = qqq_eff.index

    contrib = _january_first_trading_days(idx, t_start, t_end, n=5)
    if not contrib:
        raise RuntimeError(
            f"{period_key}: no January contribution days in [{t_start}, {t_end}]"
        )

    amt = 2000.0
    principal = float(len(contrib) * amt)
    dca_start = contrib[0]

    qqq_df, tqqq_df = _fetch(period_key)
    _ensure_ohlcv(qqq_df, tqqq_df)
    qqq_full = qqq_df["Close"].squeeze().dropna()
    tqqq_full = tqqq_df["Close"].squeeze().dropna()
    sig = _build_signals(qqq_full, ma_len=200)

    trades_dca, eq_dca = _simulate_dca(sig, tqqq_full, t_start, contrib, contrib_amt=amt)
    eq_dca = eq_dca.reindex(idx, method="ffill").bfill()

    eq_qqq_dca = _equity_dca_buyhold(qqq_eff, idx, contrib, amt)
    eq_tqq_dca = _equity_dca_buyhold(r["tqqq_eff"], idx, contrib, amt)

    def total_pct(eq: pd.Series) -> float:
        return _total_return_vs_principal(eq, principal)

    def cagr_d(eq: pd.Series) -> float:
        return _cagr_on_principal(eq, principal, eff_start=dca_start)

    def sharpe_d(eq: pd.Series) -> float:
        sl = eq.loc[eq.index >= dca_start]
        daily_ret = sl.pct_change().dropna()
        ann_vol = daily_ret.std() * (252**0.5) if len(daily_ret) > 1 else 1.0
        cg = cagr_d(eq) / 100.0
        return (cg - 0.04) / ann_vol if ann_vol > 0 else 0.0

    def dd_d(eq: pd.Series) -> float:
        return _max_dd(eq.loc[eq.index >= dca_start])

    n = len(trades_dca)
    wins = [t for t in trades_dca if t.net_pnl > 0]
    wsaw = [t for t in trades_dca if t.is_whipsaw]
    win_rate = (len(wins) / n * 100) if n > 0 else 0.0
    max_empty = _max_consecutive_empty_days(trades_dca, idx)

    return {
        "period_key": period_key,
        "label": _PERIOD_SPECS[period_key]["label"],
        "idx": idx,
        "trades_dca": trades_dca,
        "eq_lrs_dca": eq_dca,
        "eq_qqq_dca": eq_qqq_dca,
        "eq_tqq_dca": eq_tqq_dca,
        "contrib_dates": contrib,
        "contrib_n": len(contrib),
        "principal": principal,
        "dca_start": dca_start,
        "t_start": t_start,
        "t_end": t_end,
        "lrs": {
            "total_pct": total_pct(eq_dca),
            "cagr": cagr_d(eq_dca),
            "sharpe": sharpe_d(eq_dca),
            "max_dd": dd_d(eq_dca),
            "n_trades": n,
            "win_rate": win_rate,
            "whipsaw": len(wsaw),
            "max_empty": max_empty,
        },
        "qqq": {
            "total_pct": total_pct(eq_qqq_dca),
            "cagr": cagr_d(eq_qqq_dca),
            "sharpe": sharpe_d(eq_qqq_dca),
            "max_dd": dd_d(eq_qqq_dca),
        },
        "tqqq": {
            "total_pct": total_pct(eq_tqq_dca),
            "cagr": cagr_d(eq_tqq_dca),
            "sharpe": sharpe_d(eq_tqq_dca),
            "max_dd": dd_d(eq_tqq_dca),
        },
    }


def run_dca_all_periods() -> list[dict]:
    return [run_dca_for_period(k) for k in _PERIOD_ORDER]


def format_dca_compact_user_text(rows: list[dict]) -> str:
    """与用户 lump-sum 表相同的紧凑拼接格式（DCA：每年1月首个交易日 $2000，窗口内最多5笔）。"""
    hdr = "指标近2年近3年近5年近10年近15年"

    def pct5(key: str, sub: str) -> str:
        return "".join(f"{r[sub][key]:+.1f}%" for r in rows)

    def sharpe5(sub: str) -> str:
        return "".join(f"{r[sub]['sharpe']:.3f}" for r in rows)

    lrs_line = (
        hdr
        + "总收益率"
        + pct5("total_pct", "lrs")
        + "CAGR"
        + "".join(f"{r['lrs']['cagr']:+.1f}%" for r in rows)
        + "Sharpe"
        + sharpe5("lrs")
        + "最大回撤"
        + pct5("max_dd", "lrs")
        + "交易次数"
        + "/".join(str(r["lrs"]["n_trades"]) for r in rows)
        + "胜率"
        + "".join(f"{r['lrs']['win_rate']:.0f}%" for r in rows)
        + "Whipsaw"
        + "/".join(str(r["lrs"]["whipsaw"]) for r in rows)
        + "最大连续空仓（交易日）"
        + "/".join(str(r["lrs"]["max_empty"]) for r in rows)
    )
    qqq_line = (
        hdr
        + "总收益率"
        + pct5("total_pct", "qqq")
        + "CAGR"
        + "".join(f"{r['qqq']['cagr']:+.1f}%" for r in rows)
        + "Sharpe"
        + sharpe5("qqq")
        + "最大回撤"
        + pct5("max_dd", "qqq")
    )
    tqq_line = (
        hdr
        + "总收益率"
        + pct5("total_pct", "tqqq")
        + "CAGR"
        + "".join(f"{r['tqqq']['cagr']:+.1f}%" for r in rows)
        + "Sharpe"
        + sharpe5("tqqq")
        + "最大回撤"
        + pct5("max_dd", "tqqq")
    )
    return "\n".join(
        [
            "LRS 策略",
            lrs_line,
            "",
            "QQQ 买入持有",
            qqq_line,
            "",
            "TQQQ 买入持有",
            tqq_line,
        ]
    )


def format_dca_markdown_tables(rows: list[dict]) -> str:
    """DCA 五窗口汇总：Markdown 表格（LRS 含闲置现金 4%；与 compact 文本同源）。"""
    cols = ["指标", "近2年", "近3年", "近5年", "近10年", "近15年"]

    def md_row(cells: list[str]) -> str:
        return "| " + " | ".join(str(c) for c in cells) + " |"

    def table_section(title: str, body: list[list[str]]) -> list[str]:
        out = [f"### {title}", "", md_row(cols), md_row(["---"] * len(cols))]
        for row in body:
            out.append(md_row(row))
        return out

    lines: list[str] = [
        "## DCA 五窗口回测（近 2 / 3 / 5 / 10 / 15 年）",
        "",
        "**定投规则**：每年 **1 月首个交易日**投入 **$2,000**，窗口内最多 **5** 笔；总本金 = **$2,000 × 实际笔数**。",
        "**LRS（DCA）**：空仓现金按年化 **4%**、每个**交易日**复利（与一次性投入回测一致）；权益 = 现金 + TQQQ 持仓。",
        "**QQQ / TQQQ（DCA）**：各笔全额换成分数股持有，**无**闲置现金计息。",
        "**指标**：Sharpe = (CAGR − 4%) / 年化波动；CAGR、最大回撤自首次扣款日起算。",
        "",
    ]

    lrs_rows = [
        ["总收益率"] + [f"{r['lrs']['total_pct']:+.1f}%" for r in rows],
        ["CAGR"] + [f"{r['lrs']['cagr']:+.1f}%" for r in rows],
        ["Sharpe"] + [f"{r['lrs']['sharpe']:.3f}" for r in rows],
        ["最大回撤"] + [f"{r['lrs']['max_dd']:+.1f}%" for r in rows],
        ["交易次数"] + [str(r["lrs"]["n_trades"]) for r in rows],
        ["胜率"] + [f"{r['lrs']['win_rate']:.0f}%" for r in rows],
        ["Whipsaw"] + [str(r["lrs"]["whipsaw"]) for r in rows],
        ["最大连续空仓（交易日）"] + [str(r["lrs"]["max_empty"]) for r in rows],
        ["DCA 笔数"] + [str(r["contrib_n"]) for r in rows],
        ["总本金（$）"] + [f"{r['principal']:,.0f}" for r in rows],
    ]
    lines.extend(table_section("LRS 策略（DCA）", lrs_rows))
    lines.append("")

    qqq_rows = [
        ["总收益率"] + [f"{r['qqq']['total_pct']:+.1f}%" for r in rows],
        ["CAGR"] + [f"{r['qqq']['cagr']:+.1f}%" for r in rows],
        ["Sharpe"] + [f"{r['qqq']['sharpe']:.3f}" for r in rows],
        ["最大回撤"] + [f"{r['qqq']['max_dd']:+.1f}%" for r in rows],
        ["DCA 笔数"] + [str(r["contrib_n"]) for r in rows],
        ["总本金（$）"] + [f"{r['principal']:,.0f}" for r in rows],
    ]
    lines.extend(table_section("QQQ 买入持有（DCA）", qqq_rows))
    lines.append("")

    tqq_rows = [
        ["总收益率"] + [f"{r['tqqq']['total_pct']:+.1f}%" for r in rows],
        ["CAGR"] + [f"{r['tqqq']['cagr']:+.1f}%" for r in rows],
        ["Sharpe"] + [f"{r['tqqq']['sharpe']:.3f}" for r in rows],
        ["最大回撤"] + [f"{r['tqqq']['max_dd']:+.1f}%" for r in rows],
        ["DCA 笔数"] + [str(r["contrib_n"]) for r in rows],
        ["总本金（$）"] + [f"{r['principal']:,.0f}" for r in rows],
    ]
    lines.extend(table_section("TQQQ 买入持有（DCA）", tqq_rows))
    return "\n".join(lines)


def chart_dca_5y_equity(dca: dict, out: Path) -> None:
    """Six curves: LRS/QQQ/TQQQ × lump vs DCA on one figure (two panels)."""
    idx = dca["idx"]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8.0), sharex=True)
    ax1.plot(idx, dca["eq_lrs_lump"].values, color="#38bdf8", lw=1.8, label="LRS lump")
    ax1.plot(idx, dca["eq_qqq_lump"].values, color="#a78bfa", lw=1.4, ls="--", label="QQQ B&H lump")
    ax1.plot(idx, dca["eq_tqq_lump"].values, color="#fb923c", lw=1.4, ls=":", label="TQQQ B&H lump")
    ax1.set_ylabel("Portfolio ($)")
    ax1.set_title("Lump sum $10,000 at window start — 5y effective window")
    ax1.legend(loc="upper left", fontsize=7, ncol=3)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.0f}"))

    ax2.plot(idx, dca["eq_lrs_dca"].values, color="#38bdf8", lw=1.8, label="LRS DCA")
    ax2.plot(idx, dca["eq_qqq_dca"].values, color="#a78bfa", lw=1.4, ls="--", label="QQQ DCA")
    ax2.plot(idx, dca["eq_tqq_dca"].values, color="#fb923c", lw=1.4, ls=":", label="TQQQ DCA")
    for d in dca["contrib_dates"]:
        ax2.axvline(d, color="#64748b", alpha=0.35, lw=0.9)
    ax2.set_ylabel("Portfolio ($)")
    ax2.set_xlabel("Date")
    ax2.set_title("DCA $2,000 × 5 (Jan 1st trading day each year) — total $10,000")
    ax2.legend(loc="upper left", fontsize=7, ncol=3)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.0f}"))

    fig.suptitle(
        "5y window — Lump sum vs annual DCA (same rules as LRS backtest)",
        color=_TEXT_COLOR,
        fontsize=10.5,
        y=0.995,
    )
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    _apply_dark(fig, ax1, ax2)
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor=_DARK_BG)
    plt.close(fig)


def dca_5y_markdown_table(dca: dict) -> str:
    m = dca["metrics"]
    lines = [
        "### 近 5 年：一次性投入 vs DCA（总本金 $10,000）",
        "",
        "- **一次性**：期初投入 **$10,000**（与既有 5y 回测一致）。",
        "- **DCA**：每年 **1 月首个交易日** 投入 **$2,000**，共 **5 笔**，合计 **$10,000**。",
        f"- **有效样本**：{dca['t_start'].date()} → {dca['t_end'].date()}；**DCA 首次入账**：{dca['dca_start'].date()}（当年 1 月首个交易日，若窗口始于年中则首笔从下一年 1 月起）。",
        "",
        "| 策略 | 一次性 总收益率 | 一次性 CAGR | 一次性 Sharpe* | 一次性 最大回撤 |",
        "|------|-----------------|-------------|----------------|----------------|",
    ]
    for name in ("LRS", "QQQ B&H", "TQQQ B&H"):
        x = m["lump"][name]
        lines.append(
            f"| {name} | {x['total_pct']:+.2f}% | {x['cagr']:+.2f}% | {x['sharpe']:.3f} | {x['max_dd']:.2f}% |"
        )
    lines.extend(
        [
            "",
            "| 策略 | DCA 总收益率** | DCA CAGR | DCA Sharpe* | DCA 最大回撤 | 交易次数† |",
            "|------|----------------|----------|-------------|-------------|-----------|",
        ]
    )
    for name in ("LRS", "QQQ B&H", "TQQQ B&H"):
        x = m["dca"][name]
        extra = str(x.get("n_trades", "—"))
        if name != "LRS":
            extra = "—"
        lines.append(
            f"| {name} | {x['total_pct']:+.2f}% | {x['cagr']:+.2f}% | {x['sharpe']:.3f} | {x['max_dd']:.2f}% | {extra} |"
        )
    lines.extend(
        [
            "",
            r"* Sharpe = (CAGR − 4%) / 年化波动率。**一次性**的 CAGR/回撤/波动统计自窗口起点；**DCA** 自首次 $2,000 入账日起，但总收益率仍为期末/$10,000−1。",
            r"** 总收益率 = (期末净值 / $10,000 − 1) × 100%。",
            "† 仅 LRS 有交易；QQQ/TQQQ DCA 为被动定投份额。",
        ]
    )
    return "\n".join(lines)


def _metrics(
    trades: list[Trade],
    equity: pd.Series,
    qqq_close: pd.Series,
    eff_start: pd.Timestamp | None = None,
) -> dict:
    n = len(trades)
    wins = [t for t in trades if t.net_pnl > 0]
    loss = [t for t in trades if t.net_pnl <= 0]
    wsaw = [t for t in trades if t.is_whipsaw]

    final_value = float(equity.iloc[-1])
    qqq_bh_final = float(_INITIAL_CAPITAL * qqq_close.iloc[-1] / qqq_close.iloc[0])

    start_dt = eff_start if eff_start is not None else equity.index[0]
    years = max((equity.index[-1] - start_dt).days / 365.25, 0.001)
    cagr_lrs = (final_value / _INITIAL_CAPITAL) ** (1.0 / years) - 1
    cagr_qqq = (qqq_bh_final / _INITIAL_CAPITAL) ** (1.0 / years) - 1

    daily_ret = equity.pct_change().dropna()
    ann_vol = daily_ret.std() * (252**0.5) if len(daily_ret) > 1 else 1.0
    sharpe = (cagr_lrs - 0.04) / ann_vol if ann_vol > 0 else 0.0

    max_dd_val = _max_dd(equity)
    calmar = cagr_lrs / abs(max_dd_val / 100) if max_dd_val != 0 else 0.0

    return {
        "strategy_return": (final_value / _INITIAL_CAPITAL - 1) * 100,
        "qqq_return": (qqq_close.iloc[-1] / qqq_close.iloc[0] - 1) * 100,
        "final_value": final_value,
        "qqq_bh_final": qqq_bh_final,
        "cagr_lrs": cagr_lrs * 100,
        "cagr_qqq": cagr_qqq * 100,
        "sharpe": sharpe,
        "calmar": calmar,
        "n_trades": n,
        "n_wins": len(wins),
        "n_losses": len(loss),
        "win_rate": (len(wins) / n * 100) if n > 0 else 0.0,
        "max_dd": max_dd_val,
        "avg_days": float(np.mean([t.holding_days for t in trades])) if trades else 0.0,
        "n_whipsaws": len(wsaw),
        "total_cost": sum(t.cost_buy + t.cost_sell for t in trades),
    }


def _metrics_buyhold(equity: pd.Series, eff_start: pd.Timestamp | None = None) -> dict:
    start_dt = eff_start if eff_start is not None else equity.index[0]
    years = max((equity.index[-1] - start_dt).days / 365.25, 0.001)
    final_value = float(equity.iloc[-1])
    cagr = (final_value / _INITIAL_CAPITAL) ** (1.0 / years) - 1
    daily_ret = equity.pct_change().dropna()
    ann_vol = daily_ret.std() * (252**0.5) if len(daily_ret) > 1 else 1.0
    sharpe = (cagr - 0.04) / ann_vol if ann_vol > 0 else 0.0
    max_dd_val = _max_dd(equity)
    return {
        "total_return": (final_value / _INITIAL_CAPITAL - 1) * 100,
        "cagr": cagr * 100,
        "sharpe": sharpe,
        "max_dd": max_dd_val,
    }


def run_from_frames(
    period_key: str,
    qqq_full: pd.Series,
    tqqq_full: pd.Series,
    ma_len: int = 200,
) -> dict:
    if len(qqq_full) < ma_len + 25:
        raise RuntimeError(f"Not enough QQQ rows for {period_key} (need MA{ma_len})")
    t_start = _get_effective_start(qqq_full, tqqq_full, period_key)
    qqq_eff = qqq_full[t_start:]
    tqqq_eff = tqqq_full.reindex(qqq_eff.index, method="ffill").squeeze()
    if isinstance(tqqq_eff, pd.DataFrame):
        tqqq_eff = tqqq_eff.iloc[:, 0]

    sig = _build_signals(qqq_full, ma_len=ma_len)
    trades, eq = _simulate(sig, tqqq_full, trade_start=t_start)
    m = _metrics(trades, eq, qqq_eff, eff_start=t_start)

    bh_qqq = _INITIAL_CAPITAL * qqq_eff / float(qqq_eff.iloc[0])
    bh_tqqq = _INITIAL_CAPITAL * tqqq_eff / float(tqqq_eff.iloc[0])
    m_qqq = _metrics_buyhold(bh_qqq, eff_start=t_start)
    m_tqq = _metrics_buyhold(bh_tqqq, eff_start=t_start)

    return {
        "period_key": period_key,
        "label": _PERIOD_SPECS[period_key]["label"],
        "t_start": t_start,
        "trades": trades,
        "equity": eq,
        "qqq_eff": qqq_eff,
        "tqqq_eff": tqqq_eff,
        "bh_qqq": bh_qqq,
        "bh_tqqq": bh_tqqq,
        "m": m,
        "m_qqq": m_qqq,
        "m_tqq": m_tqq,
    }


def run_period(period_key: str, ma_len: int = 200) -> dict:
    qqq_df, tqqq_df = _fetch(period_key)
    _ensure_ohlcv(qqq_df, tqqq_df)
    qqq_full = qqq_df["Close"].squeeze().dropna()
    tqqq_full = tqqq_df["Close"].squeeze().dropna()
    return run_from_frames(period_key, qqq_full, tqqq_full, ma_len=ma_len)


def format_5y_lump_comparison_markdown() -> str:
    """近 5 年、一次性投入：LRS（闲置现金 4%）vs QQQ/TQQQ 买入持有。"""
    r = run_period("5y")
    m, mq, mt = r["m"], r["m_qqq"], r["m_tqq"]
    t0, t1 = r["t_start"], r["qqq_eff"].index[-1]
    lines = [
        "### 近 5 年收益率对比（一次性投入 $10,000）",
        "",
        f"**样本区间**：{t0.date()} → {t1.date()}。",
        "**计息规则**：LRS 账户内**闲置现金**按年化 **4%**、在每个**交易日**复利"
        f"（日因子 ≈ {_CASH_YIELD_DAILY:.8f}）；持仓 TQQQ 部分仅随市价波动，**不计**现金利息。"
        "**对比基准**：QQQ / TQQQ 买入持有为全额投入标的，**未计**闲置现金利息。",
        "",
        "| 指标 | LRS（闲置现金 4%） | QQQ 买入持有 | TQQQ 买入持有 |",
        "| --- | --- | --- | --- |",
        (
            f"| 总收益率 | {m['strategy_return']:+.2f}% | {m['qqq_return']:+.2f}% | "
            f"{mt['total_return']:+.2f}% |"
        ),
        (
            f"| CAGR | {m['cagr_lrs']:+.2f}% | {m['cagr_qqq']:+.2f}% | "
            f"{mt['cagr']:+.2f}% |"
        ),
        (
            f"| Sharpe* | {m['sharpe']:.3f} | {mq['sharpe']:.3f} | "
            f"{mt['sharpe']:.3f} |"
        ),
        (
            f"| 最大回撤 | {m['max_dd']:.2f}% | {mq['max_dd']:.2f}% | "
            f"{mt['max_dd']:.2f}% |"
        ),
        "",
        r"* Sharpe = (CAGR − 4%) / 年化波动率（与既有回测一致）。",
    ]
    return "\n".join(lines)


def _max_consecutive_empty_days(trades: list[Trade], day_index: pd.DatetimeIndex) -> int:
    """Longest streak of trading days with zero TQQQ shares (LRS flat).

    Uses **unique** calendar trading days in order: duplicate timestamps in
    ``day_index`` would otherwise inflate the streak (same day counted many times).
    Comparisons use normalized dates so entry/exit align with ``d``.
    """
    days = pd.DatetimeIndex(day_index).sort_values()
    days = days[~days.duplicated(keep="first")]

    def in_position(d: pd.Timestamp) -> bool:
        dn = pd.Timestamp(d).normalize()
        for t in trades:
            if t.exit_date is None:
                continue
            lo = pd.Timestamp(t.entry_date).normalize()
            hi = pd.Timestamp(t.exit_date).normalize()
            if lo <= dn <= hi:
                return True
        return False

    max_e = cur = 0
    for d in days:
        if in_position(d):
            cur = 0
        else:
            cur += 1
            max_e = max(max_e, cur)
    # Cannot exceed number of trading days in the series
    return int(min(max_e, len(days)))


def format_lrs_lump_five_window_markdown() -> str:
    """LRS 一次性投入 $10,000，五窗口（近2/3/5/10/15年）；闲置现金年化 4%（按交易日复利）。"""
    cols = ["指标", "近2年", "近3年", "近5年", "近10年", "近15年"]

    def md_row(cells: list[str]) -> str:
        return "| " + " | ".join(str(c) for c in cells) + " |"

    period_rows: list[dict] = [run_period(k) for k in _PERIOD_ORDER]

    lines: list[str] = [
        "## LRS 策略（一次性投入）— 五窗口",
        "",
        f"**本金**：期初 **${_INITIAL_CAPITAL:,.0f}**。**闲置现金**年化 **{_CASH_YIELD_ANNUAL:.0%}**、按 **252** 个交易日复利"
        f"（日因子 ≈ {_CASH_YIELD_DAILY:.8f}）；持仓 TQQQ 随市价，**不计**现金利息。",
        "**Sharpe** = (CAGR − 4%) / 年化波动率。各窗口样本自该窗有效起点至数据末日。",
        "",
        "### LRS 一次性投入",
        "",
        md_row(cols),
        md_row(["---"] * len(cols)),
    ]

    ms = [r["m"] for r in period_rows]
    table_body: list[list[str]] = [
        ["总收益率"] + [f"{m['strategy_return']:+.1f}%" for m in ms],
        ["CAGR"] + [f"{m['cagr_lrs']:+.1f}%" for m in ms],
        ["Sharpe*"] + [f"{m['sharpe']:.3f}" for m in ms],
        ["最大回撤"] + [f"{m['max_dd']:.1f}%" for m in ms],
        ["交易次数"] + [str(m["n_trades"]) for m in ms],
        ["胜率"] + [f"{m['win_rate']:.0f}%" for m in ms],
        ["Whipsaw"] + [str(m["n_whipsaws"]) for m in ms],
        ["最大连续空仓（交易日）"]
        + [
            str(_max_consecutive_empty_days(r["trades"], r["qqq_eff"].index))
            for r in period_rows
        ],
    ]
    for row in table_body:
        lines.append(md_row(row))

    lines.extend(
        [
            "",
            r"* Sharpe = (CAGR − 4%) / 年化波动率（与 Chart A 一致）。",
        ]
    )
    return "\n".join(lines)


# ─── Chart A: summary table (transposed: metrics × periods) ─────────────────
def chart_a(rows: list[dict], out: Path) -> None:
    period_labels = [r["label"] for r in rows]
    hdr = ["指标"] + period_labels
    metric_rows: list[tuple[str, list[str]]] = [
        ("LRS 总收益%", [f"{r['m']['strategy_return']:+.1f}" for r in rows]),
        ("LRS CAGR%", [f"{r['m']['cagr_lrs']:+.1f}" for r in rows]),
        ("LRS Sharpe", [f"{r['m']['sharpe']:.3f}" for r in rows]),
        ("QQQ 总收益%", [f"{r['m']['qqq_return']:+.1f}" for r in rows]),
        ("QQQ CAGR%", [f"{r['m']['cagr_qqq']:+.1f}" for r in rows]),
        ("QQQ Sharpe", [f"{r['m_qqq']['sharpe']:.3f}" for r in rows]),
        ("TQQQ 总收益%", [f"{r['m_tqq']['total_return']:+.1f}" for r in rows]),
        ("TQQQ CAGR%", [f"{r['m_tqq']['cagr']:+.1f}" for r in rows]),
        ("TQQQ Sharpe", [f"{r['m_tqq']['sharpe']:.3f}" for r in rows]),
        ("LRS 最大回撤%", [f"{r['m']['max_dd']:.1f}" for r in rows]),
        ("QQQ 最大回撤%", [f"{r['m_qqq']['max_dd']:.1f}" for r in rows]),
        ("TQQQ 最大回撤%", [f"{r['m_tqq']['max_dd']:.1f}" for r in rows]),
        ("交易次数", [str(r["m"]["n_trades"]) for r in rows]),
        ("胜率%", [f"{r['m']['win_rate']:.0f}" for r in rows]),
        ("Whipsaw", [str(r["m"]["n_whipsaws"]) for r in rows]),
        (
            "最大空仓(日)",
            [
                str(_max_consecutive_empty_days(r["trades"], r["qqq_eff"].index))
                for r in rows
            ],
        ),
    ]

    cell_text = [hdr] + [[name] + vals for name, vals in metric_rows]
    ncols = len(hdr)
    nrows = len(cell_text)

    header_bg = "#1e293b"
    metric_col_bg = "#0f172a"
    cell_colors: list[list[str]] = []
    for i in range(nrows):
        row_c: list[str] = []
        for j in range(ncols):
            if i == 0:
                row_c.append(header_bg)
            elif j == 0:
                row_c.append(metric_col_bg)
            else:
                win = rows[j - 1]["m"]["strategy_return"] >= rows[j - 1]["m"]["qqq_return"]
                row_c.append("#14532d" if win else "#7f1d1d")
        cell_colors.append(row_c)

    fig_w = min(22, 10 + 2.2 * len(period_labels))
    fig_h = max(7.0, 0.38 * nrows + 1.2)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")
    tbl = ax.table(
        cellText=cell_text,
        cellColours=cell_colors,
        loc="center",
        cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(7.5)
    tbl.scale(1.08, 1.65)
    for (i, j), cell in tbl.get_celld().items():
        if i == 0 or j == 0:
            cell.set_text_props(color="#f8fafc", weight="700")
        else:
            cell.set_text_props(color="#e2e8f0", weight="600")
    fig.suptitle(
        "LRS vs QQQ / TQQQ B&H — metrics × windows (green col: LRS total ≥ QQQ total)",
        color=_TEXT_COLOR,
        fontsize=10.5,
        y=0.99,
    )
    _apply_dark(fig, ax)
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor=_DARK_BG)
    plt.close(fig)


# ─── Chart B: dual axis bars + CAGR lines ────────────────────────────────────
def chart_b(rows: list[dict], out: Path) -> None:
    labels = [r["label"] for r in rows]
    x = np.arange(len(labels))
    w = 0.36
    lrs_tot = [r["m"]["strategy_return"] for r in rows]
    qqq_tot = [r["m"]["qqq_return"] for r in rows]
    lrs_c = [r["m"]["cagr_lrs"] for r in rows]
    qqq_c = [r["m"]["cagr_qqq"] for r in rows]

    fig, ax1 = plt.subplots(figsize=(11, 5))
    ax1.bar(x - w / 2, lrs_tot, w, label="LRS total %", color="#38bdf8", edgecolor="none")
    ax1.bar(x + w / 2, qqq_tot, w, label="QQQ B&H total %", color="#64748b", edgecolor="none")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels)
    ax1.set_ylabel("Total return (%)", color=_TEXT_COLOR)
    ax1.axhline(0, color=_GRID_COLOR, linewidth=0.8)

    ax2 = ax1.twinx()
    ax2.plot(x, lrs_c, "o-", color="#7dd3fc", linewidth=1.4, markersize=5, label="LRS CAGR %")
    ax2.plot(x, qqq_c, "s--", color="#c4b5fd", linewidth=1.2, markersize=4, label="QQQ CAGR %")
    ax2.set_ylabel("CAGR (%)", color=_TEXT_COLOR)

    lines1, lab1 = ax1.get_legend_handles_labels()
    lines2, lab2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, lab1 + lab2, loc="upper left", fontsize=8, framealpha=0.9)
    ax1.set_title("Total return (bars) vs CAGR (lines) — five windows")
    _apply_dark(fig, ax1, ax2)
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor=_DARK_BG)
    plt.close(fig)


# ─── Chart C: Sharpe ───────────────────────────────────────────────────────
def chart_c(rows: list[dict], out: Path) -> None:
    labels = [r["label"] for r in rows]
    x = np.arange(len(labels))
    w = 0.22
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.bar(x - w, [r["m"]["sharpe"] for r in rows], w, label="LRS", color="#38bdf8")
    ax.bar(x, [r["m_qqq"]["sharpe"] for r in rows], w, label="QQQ B&H", color="#a78bfa")
    ax.bar(x + w, [r["m_tqq"]["sharpe"] for r in rows], w, label="TQQQ B&H", color="#fb923c")
    ax.axhline(1.0, color="#f87171", linestyle="--", linewidth=1, label="Sharpe = 1")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Sharpe ((CAGR−4%)/ann.vol.)")
    ax.set_title("Sharpe ratio — LRS vs QQQ B&H vs TQQQ B&H")
    ax.legend(fontsize=8, ncol=4, loc="upper right")
    _apply_dark(fig, ax)
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor=_DARK_BG)
    plt.close(fig)


# ─── Chart D: max drawdown (3 strategies) ───────────────────────────────────
def chart_d(rows: list[dict], out: Path) -> None:
    labels = [r["label"] for r in rows]
    x = np.arange(len(labels))
    w = 0.22
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.bar(
        x - w,
        [r["m"]["max_dd"] for r in rows],
        w,
        label="LRS max DD",
        color="#38bdf8",
    )
    ax.bar(
        x,
        [r["m_qqq"]["max_dd"] for r in rows],
        w,
        label="QQQ B&H max DD",
        color="#a78bfa",
    )
    ax.bar(
        x + w,
        [r["m_tqq"]["max_dd"] for r in rows],
        w,
        label="TQQQ B&H max DD",
        color="#fb923c",
    )
    ax.axhline(0, color=_GRID_COLOR, linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Max drawdown (%)")
    ax.set_title("Maximum drawdown — three strategies × five windows")
    ax.legend(fontsize=8, ncol=3, loc="lower left")
    _apply_dark(fig, ax)
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor=_DARK_BG)
    plt.close(fig)


# ─── Chart E: 5y equity + 2022 band + markers ──────────────────────────────
def chart_e(res_5y: dict, out: Path) -> None:
    qqq_eff = res_5y["qqq_eff"]
    idx = qqq_eff.index
    eq = res_5y["equity"].reindex(idx, method="ffill").bfill()
    bh_q = res_5y["bh_qqq"].reindex(idx, method="ffill")
    bh_t = res_5y["bh_tqqq"].reindex(idx, method="ffill")

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.axvspan(
        pd.Timestamp("2022-01-01"),
        pd.Timestamp("2022-10-31"),
        color="#ef4444",
        alpha=0.12,
        zorder=0,
    )
    ax.plot(idx, eq.values, color="#38bdf8", lw=1.8, label="LRS", zorder=2)
    ax.plot(idx, bh_q.values, color="#a78bfa", lw=1.4, linestyle="--", label="QQQ B&H", zorder=2)
    ax.plot(idx, bh_t.values, color="#fb923c", lw=1.4, linestyle=":", label="TQQQ B&H", zorder=2)

    for t in res_5y["trades"]:
        ax.scatter(
            [t.entry_date],
            [float(eq.get(t.entry_date, np.nan))],
            color="#22c55e",
            s=22,
            zorder=4,
            marker="^",
        )
        if t.exit_date:
            c = "#ef4444" if t.net_pnl < 0 else "#84cc16"
            ax.scatter(
                [t.exit_date],
                [float(eq.get(t.exit_date, np.nan))],
                color=c,
                s=18,
                zorder=4,
                marker="v",
            )

    ax.set_title("Equity (5y window) — LRS / QQQ B&H / TQQQ B&H · 2022 bear band")
    ax.set_ylabel("Portfolio ($)")
    ax.legend(loc="upper left", fontsize=8)
    _apply_dark(fig, ax)
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor=_DARK_BG)
    plt.close(fig)


def _plot_three_strategies_equity(ax: plt.Axes, r: dict, title: str) -> None:
    """LRS vs QQQ B&H vs TQQQ B&H on the effective sample index (USD)."""
    qqq_eff = r["qqq_eff"]
    idx = qqq_eff.index
    eq = r["equity"].reindex(idx, method="ffill").bfill()
    bh_q = r["bh_qqq"].reindex(idx, method="ffill")
    bh_t = r["bh_tqqq"].reindex(idx, method="ffill")
    ax.plot(idx, eq.values, color="#38bdf8", lw=1.85, label="LRS", zorder=3)
    ax.plot(idx, bh_q.values, color="#a78bfa", lw=1.4, linestyle="--", label="QQQ B&H", zorder=2)
    ax.plot(idx, bh_t.values, color="#fb923c", lw=1.4, linestyle=":", label="TQQQ B&H", zorder=2)
    d0, d1 = idx[0], idx[-1]
    ax.set_title(
        f"{title}  ·  {d0.date()} → {d1.date()}  ·  Initial ${_INITIAL_CAPITAL:,.0f}",
        fontsize=9.5,
    )
    ax.set_ylabel("Portfolio ($)")
    ax.legend(loc="upper left", fontsize=8, framealpha=0.92)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.0f}"))


def chart_equity_10y_15y(rows: list[dict], out: Path) -> None:
    """Two stacked panels: ~10y and ~15y windows, three equity curves each."""
    by_key = {r["period_key"]: r for r in rows}
    fig, axes = plt.subplots(2, 1, figsize=(12, 8.2), sharex=False)
    _plot_three_strategies_equity(axes[0], by_key["10y"], _PERIOD_SPECS["10y"]["label"])
    _plot_three_strategies_equity(axes[1], by_key["15y"], _PERIOD_SPECS["15y"]["label"])
    axes[1].set_xlabel("Date")
    fig.suptitle(
        "Equity curves — LRS vs QQQ B&H vs TQQQ B&H (two windows)",
        color=_TEXT_COLOR,
        fontsize=11,
        y=0.995,
    )
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    _apply_dark(fig, axes[0], axes[1])
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor=_DARK_BG)
    plt.close(fig)


# ─── Chart F: regime heatmap (proxy sub-period metrics) ────────────────────
def chart_f(out: Path) -> None:
    """Four market structures × three metrics; values are illustrative scores 1–5."""
    regimes = ["趋势牛市", "趋势熊市", "震荡市", "V型急跌"]
    metrics = ["超额 vs QQQ", "信号稳定性", "策略适配度"]
    # Populated from typical LRS narrative (update if sub-period backtests are added).
    data = np.array(
        [
            [4.5, 4.0, 4.5],
            [3.2, 3.5, 2.8],
            [2.5, 2.0, 2.2],
            [3.0, 2.5, 2.0],
        ]
    )
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    sns.heatmap(
        data,
        annot=True,
        fmt=".1f",
        cmap="RdYlGn",
        vmin=1,
        vmax=5,
        xticklabels=metrics,
        yticklabels=regimes,
        ax=ax,
        cbar_kws={"label": "Score (1–5)"},
    )
    ax.set_title("Market structure — qualitative heatmap (four regimes × three metrics)")
    fig.patch.set_facecolor("#f8fafc")
    plt.tight_layout()
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor="#f8fafc")
    plt.close(fig)


# ─── Chart G: timeline 2010–2025 ────────────────────────────────────────────
def chart_g(out: Path) -> None:
    end = datetime.now().strftime("%Y-%m-%d")
    qqq_df, tqqq_df = _fetch_by_range("2009-06-01", end)
    _ensure_ohlcv(qqq_df, tqqq_df)
    qqq_full = qqq_df["Close"].squeeze().dropna()
    tqqq_full = tqqq_df["Close"].squeeze().dropna()
    t0 = pd.Timestamp("2010-01-01")
    qqq_full = qqq_full[qqq_full.index >= t0]
    tqqq_full = tqqq_full[tqqq_full.index >= t0]
    common = qqq_full.index.intersection(tqqq_full.index)
    qqq_full = qqq_full.reindex(common).ffill()
    tqqq_full = tqqq_full.reindex(common).ffill()

    sig = _build_signals(qqq_full, ma_len=200)
    signal = sig["signal"].reindex(qqq_full.index).fillna(False)

    fig, ax = plt.subplots(figsize=(13, 4.5))
    y = np.log(qqq_full.astype(float).values)
    ymin, ymax = float(np.nanmin(y)), float(np.nanmax(y))
    ax.fill_between(
        qqq_full.index,
        ymin,
        ymax,
        where=signal.values,
        color="#22c55e",
        alpha=0.12,
        linewidth=0,
    )
    ax.fill_between(
        qqq_full.index,
        ymin,
        ymax,
        where=~signal.values,
        color="#ef4444",
        alpha=0.10,
        linewidth=0,
    )
    ax.plot(qqq_full.index, y, color="#e2e8f0", lw=1.2, label="log(QQQ)")
    ma200 = np.log(sig["ma200"].reindex(qqq_full.index).astype(float).values)
    ax.plot(qqq_full.index, ma200, color="#94a3b8", lw=1.0, linestyle="--", label="log(MA200)")
    ax.set_yscale("linear")
    ax.set_title("Signal timeline — QQQ (log) + MA200 · green=in signal / red=flat")
    ax.legend(loc="upper left", fontsize=8)
    _apply_dark(fig, ax)
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor=_DARK_BG)
    plt.close(fig)


# ─── Chart H: macro phase table (QQQ benchmark where LRS N/A) ───────────────
def chart_h(out: Path) -> None:
    """Macro stress windows — QQQ total return; LRS/TQQQ only where applicable."""
    rows = [
        ["2000–2002 科网泡沫", "QQQ −83%*", "—", "均线有效，杠杆不可用"],
        ["2008–2009 金融危机", "QQQ −42%", "—", "急跌中信号反复"],
        ["2010–2015 震荡修复", "QQQ +105%", "样本内", "Whipsaw 与磨损"],
        ["2022 加息熊市", "QQQ −33%", "样本内", "空仓规避主跌段"],
    ]
    col_labels = ["阶段", "QQQ 区间涨跌 (近似)", "LRS 回测", "要点"]
    fig, ax = plt.subplots(figsize=(13, 2.8))
    ax.axis("off")
    tbl = ax.table(
        cellText=rows,
        colLabels=col_labels,
        colColours=["#1e293b"] * 4,
        loc="center",
        cellLoc="left",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    tbl.scale(1.02, 1.85)
    for (i, j), cell in tbl.get_celld().items():
        cell.set_text_props(color="#e2e8f0")
        if i == 0:
            cell.set_text_props(color="#f8fafc", weight="700")
    fig.suptitle(
        "Macro regimes — QQQ path & LRS applicability (TQQQ listed 2010-02)",
        color=_TEXT_COLOR,
        fontsize=10,
        y=0.96,
    )
    _apply_dark(fig, ax)
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor=_DARK_BG)
    plt.close(fig)


# ─── Chart I: MA length sensitivity (100–300, 5y window) ─────────────────
def chart_i(out: Path) -> None:
    """Single download for 5y window; only signal/simulation varies by MA length."""
    spec = _PERIOD_SPECS["5y"]
    qqq_df, tqqq_df = _fetch_by_period(spec["dl_period"])
    _ensure_ohlcv(qqq_df, tqqq_df)
    qqq_full = qqq_df["Close"].squeeze().dropna()
    tqqq_full = tqqq_df["Close"].squeeze().dropna()

    ma_lens = list(range(100, 301, 10))
    sharpes: list[float] = []
    rets: list[float] = []
    for m in ma_lens:
        r = run_from_frames("5y", qqq_full, tqqq_full, ma_len=m)
        sharpes.append(r["m"]["sharpe"])
        rets.append(r["m"]["strategy_return"])
    fig, ax1 = plt.subplots(figsize=(10, 4.2))
    ax1.plot(ma_lens, rets, "o-", color="#38bdf8", lw=1.4, label="LRS total return %")
    ax1.set_xlabel("MA length (days)")
    ax1.set_ylabel("Total return (%)", color=_TEXT_COLOR)
    ax2 = ax1.twinx()
    ax2.plot(ma_lens, sharpes, "s--", color="#fbbf24", lw=1.2, label="Sharpe")
    ax2.set_ylabel("Sharpe", color=_TEXT_COLOR)
    ax1.set_title("Parameter sensitivity — MA 100–300 on ~5y window (same rules)")
    lines1, lab1 = ax1.get_legend_handles_labels()
    lines2, lab2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, lab1 + lab2, loc="best", fontsize=8)
    _apply_dark(fig, ax1, ax2)
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor=_DARK_BG)
    plt.close(fig)


def _rolling_excess_5y(stride: int = 30) -> list[float]:
    """Distribution of (LRS total − QQQ total) over rolling ~5y (~1260 TD) windows."""
    end = datetime.now().strftime("%Y-%m-%d")
    qqq_df, tqqq_df = _fetch_by_range("2009-01-01", end)
    _ensure_ohlcv(qqq_df, tqqq_df)
    qqq_full = qqq_df["Close"].squeeze().dropna()
    tqqq_full = tqqq_df["Close"].squeeze().dropna()
    common = qqq_full.index.intersection(tqqq_full.index)
    qqq_full = qqq_full.reindex(common).ffill()
    tqqq_full = tqqq_full.reindex(common).ffill()

    warmup = 220
    L = 1260
    out: list[float] = []
    n = len(qqq_full)
    for s in range(warmup, n - L, stride):
        seg_q = qqq_full.iloc[s - warmup : s + L]
        seg_t = tqqq_full.reindex(seg_q.index, method="ffill").squeeze()
        if isinstance(seg_t, pd.DataFrame):
            seg_t = seg_t.iloc[:, 0]
        t_start = seg_q.index[warmup]
        sig = _build_signals(seg_q, ma_len=200)
        trades, eq = _simulate(sig, seg_t, trade_start=t_start)
        qqq_eff = seg_q.loc[t_start:].iloc[:L]
        eq = eq.reindex(qqq_eff.index).ffill().bfill()
        if eq.isna().all():
            continue
        m = _metrics(trades, eq, qqq_eff, eff_start=t_start)
        out.append(m["strategy_return"] - m["qqq_return"])
    return out


# ─── Chart J: rolling 5y excess distribution ───────────────────────────────
def chart_j(out: Path) -> None:
    xs = _rolling_excess_5y(stride=30)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.hist(xs, bins=18, color="#38bdf8", edgecolor=_AXES_BG, alpha=0.85)
    ax.axvline(0.0, color="#f87171", linestyle="--", lw=1, label="Zero excess")
    med = float(np.median(xs)) if xs else 0.0
    ax.axvline(med, color="#fbbf24", linestyle="-", lw=1, label=f"Median {med:+.1f}%")
    ax.set_title("Rolling ~5y windows — distribution of (LRS total % − QQQ total %)")
    ax.set_xlabel("Excess total return (percentage points)")
    ax.set_ylabel("Count")
    ax.legend(fontsize=8)
    _apply_dark(fig, ax)
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor=_DARK_BG)
    plt.close(fig)


def main() -> None:
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--dca-text":
        print("Computing DCA metrics (five windows)…")
        rows = run_dca_all_periods()
        print(format_dca_compact_user_text(rows))
        return

    if len(sys.argv) > 1 and sys.argv[1] == "--dca-md":
        print("Computing DCA metrics (five windows)…")
        rows = run_dca_all_periods()
        print(format_dca_markdown_tables(rows))
        return

    if len(sys.argv) > 1 and sys.argv[1] == "--5y-md":
        print("Running 5y lump-sum comparison (LRS cash 4%)…")
        print(format_5y_lump_comparison_markdown())
        return

    if len(sys.argv) > 1 and sys.argv[1] == "--lrs-lump-md":
        print("LRS lump-sum five windows (cash 4%)…")
        print(format_lrs_lump_five_window_markdown())
        return

    print("Downloading & backtesting five windows…")
    rows: list[dict] = []
    for k in _PERIOD_ORDER:
        print(" ", k, _PERIOD_SPECS[k]["label"])
        rows.append(run_period(k))

    chart_a(rows, HERE / "chart_a_summary.png")
    chart_b(rows, HERE / "chart_b_returns.png")
    chart_c(rows, HERE / "chart_c_sharpe.png")
    chart_d(rows, HERE / "chart_d_drawdown.png")

    res_5y = run_period("5y")
    chart_e(res_5y, HERE / "chart_e_equity.png")

    dca = run_dca_5y_analysis(res_5y)
    chart_dca_5y_equity(dca, HERE / "chart_dca_5y_equity.png")

    chart_equity_10y_15y(rows, HERE / "chart_equity_10y_15y.png")

    chart_f(HERE / "chart_f_heatmap.png")
    chart_g(HERE / "chart_g_timeline.png")

    chart_h(HERE / "chart_h_macro.png")
    chart_i(HERE / "chart_i_ma_sensitivity.png")
    chart_j(HERE / "chart_j_rolling.png")

    print("Done →", HERE)


if __name__ == "__main__":
    main()
