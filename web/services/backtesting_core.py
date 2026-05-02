from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

_INITIAL_CAPITAL = 10_000.0
_COST_PER_SIDE = 1.99
_DISTANCE_THRESH = 6.0
_WHIPSAW_DAYS = 10
_CASH_YIELD_ANNUAL = 0.04
_CASH_YIELD_DAILY = (1.0 + _CASH_YIELD_ANNUAL) ** (1.0 / 252.0)

_PERIOD_SPECS: dict[str, dict] = {
    "2y": {"label": "近 2 年", "fetch_type": "period", "dl_period": "3y", "target_days": 504},
    "3y": {"label": "近 3 年", "fetch_type": "period", "dl_period": "4y", "target_days": 756},
    "5y": {"label": "近 5 年", "fetch_type": "period", "dl_period": "6y", "target_days": 1260},
    "10y": {"label": "近 10 年", "fetch_type": "range", "dl_start": None, "dl_end": None, "target_days": 2520},
    "2015_2020": {
        "label": "2015—2020",
        "fetch_type": "range",
        "dl_start": "2014-01-01",
        "dl_end": "2020-12-31",
        "eff_start": "2015-01-02",
    },
    "2010_2015": {
        "label": "2010—2015",
        "fetch_type": "range",
        "dl_start": "2009-01-01",
        "dl_end": "2015-12-31",
        "eff_start": None,
    },
}

_PERIOD_ORDER = ["2y", "3y", "5y", "10y", "2015_2020", "2010_2015"]


def _accrue_cash_yield(cash: float) -> float:
    return cash * _CASH_YIELD_DAILY


def _fetch_by_period(dl_period: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    qqq = yf.download("QQQ", period=dl_period, auto_adjust=True, progress=False)
    tqqq = yf.download("TQQQ", period=dl_period, auto_adjust=True, progress=False)
    for df in (qqq, tqqq):
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
    return qqq, tqqq


def _fetch_by_range(start: str, end: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    qqq = yf.download("QQQ", start=start, end=end, auto_adjust=True, progress=False)
    tqqq = yf.download("TQQQ", start=start, end=end, auto_adjust=True, progress=False)
    for df in (qqq, tqqq):
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
    return qqq, tqqq


def _fetch(period_key: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    spec = _PERIOD_SPECS[period_key]
    if spec["fetch_type"] == "period":
        return _fetch_by_period(spec["dl_period"])
    start = spec.get("dl_start")
    end = spec.get("dl_end")
    if start is None:
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=365 * 11)
        start = start_dt.strftime("%Y-%m-%d")
        end = end_dt.strftime("%Y-%m-%d")
    return _fetch_by_range(start, end)


def _get_effective_start(qqq_full: pd.Series, tqqq_full: pd.Series, period_key: str) -> pd.Timestamp:
    spec = _PERIOD_SPECS[period_key]
    if spec.get("eff_start"):
        ts = pd.Timestamp(spec["eff_start"])
        return max(ts, qqq_full.index[0])
    if period_key == "2010_2015":
        return tqqq_full.index[0]
    n = spec.get("target_days", 504)
    offset = max(0, len(qqq_full) - n)
    return qqq_full.index[offset]


def _streak(s: pd.Series) -> pd.Series:
    groups = (s != s.shift()).cumsum()
    return (s.groupby(groups).cumcount() + 1).where(s, 0)


def _build_signals(qqq_close: pd.Series) -> pd.DataFrame:
    ma200 = qqq_close.rolling(200).mean()
    a1 = qqq_close > ma200
    slope = (ma200 - ma200.shift(20)) / ma200.shift(20) * 100
    a2 = slope > -0.5
    a3 = _streak(a1) >= 3
    signal = a1 & a2 & a3
    entry_signal = signal & ~signal.shift(1).fillna(False)
    below = qqq_close < ma200
    exit_signal = below & below.shift(1).fillna(False)
    cross = a1 & ~a1.shift(1).fillna(False)
    return pd.DataFrame(
        {
            "qqq": qqq_close,
            "ma200": ma200,
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


def _simulate(sig: pd.DataFrame, tqqq_close: pd.Series, trade_start: pd.Timestamp | None = None) -> tuple[list[Trade], pd.Series]:
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
            equity[date] = cash + shares * (float(tqqq.dropna().iloc[-1]) if shares > 0 else 0.0)
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
            cross_price = float(cross_raw) if cross_raw is not None and not math.isnan(float(cross_raw)) else price
            dist = (price - cross_price) / cross_price * 100 if cross_price > 0 else 0.0
            mode, frac = _allocation(dist)
            invest = cash * frac - _COST_PER_SIDE
            if invest > 0:
                n = math.floor(invest / price)
                if n >= 1:
                    cash -= n * price + _COST_PER_SIDE
                    shares = float(n)
                    in_pos = True
                    current = Trade(entry_date=date, entry_price=price, entry_mode=mode, shares=shares, cost_buy=_COST_PER_SIDE)
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


def _metrics(trades: list[Trade], equity: pd.Series, qqq_close: pd.Series) -> dict:
    n = len(trades)
    wins = [t for t in trades if t.net_pnl > 0]
    loss = [t for t in trades if t.net_pnl <= 0]
    wsaw = [t for t in trades if t.is_whipsaw]
    avg = float(np.mean([t.holding_days for t in trades])) if trades else 0.0
    return {
        "strategy_return": (equity.iloc[-1] / _INITIAL_CAPITAL - 1) * 100,
        "qqq_return": (qqq_close.iloc[-1] / qqq_close.iloc[0] - 1) * 100,
        "final_value": float(equity.iloc[-1]),
        "n_trades": n,
        "n_wins": len(wins),
        "n_losses": len(loss),
        "win_rate": (len(wins) / n * 100) if n > 0 else 0.0,
        "max_dd": _max_dd(equity),
        "avg_days": avg,
        "n_whipsaws": len(wsaw),
        "total_cost": sum(t.cost_buy + t.cost_sell for t in trades),
    }
