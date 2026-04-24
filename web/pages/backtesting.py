"""LRS TQQQ Strategy — Historical Backtest Engine.

Compares LRS strategy vs QQQ buy-and-hold across six time windows:
  近 2 年 / 近 3 年 / 近 5 年 / 近 10 年 / 2015—2020 / 2010—2015

Key design choices
──────────────────
• Each window downloads 1 extra year for MA200 warmup before trading starts.
• "Initial entry": if signal is already True on day 1 of the trading window,
  enter immediately (no need to wait for a fresh MA200 crossover).
• Transaction cost: $1.99 / side (Futu US stock rates).
• Initial capital: $10,000 USD.
• Idle cash earns 4% annualized, compounded each trading day (≈ (1.04)^(1/252) per day).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

from web.pages.lrs.strategy_shared import apply_dark_style

_INITIAL_CAPITAL = 10_000.0
_COST_PER_SIDE   = 1.99      # $0.99 commission + $1.00 platform fee (Futu)
_DISTANCE_THRESH = 6.0       # macro_score=3 → 6% (Step 3)
_WHIPSAW_DAYS    = 10        # Holding ≤ N days AND loss
_CASH_YIELD_ANNUAL = 0.04    # idle cash MMF / T-bill style; compounded on trading days
_CASH_YIELD_DAILY = (1.0 + _CASH_YIELD_ANNUAL) ** (1.0 / 252.0)


def _accrue_cash_yield(cash: float) -> float:
    """Apply one trading day of compound interest on idle cash (4% annualized)."""
    return cash * _CASH_YIELD_DAILY


# ─────────────────────────────────────────────────────────────────────────────
# Period configuration
# ─────────────────────────────────────────────────────────────────────────────
#
# Each entry:
#   label       – displayed in the sub-tab
#   fetch_type  – "period" (yfinance period string) or "range" (start/end dates)
#   dl_period   – yfinance period to download (includes warmup)  [fetch_type=period]
#   dl_start    – warmup start date string    [fetch_type=range]
#   dl_end      – end date string             [fetch_type=range]
#   target_days – approx trading days to keep after warmup [used when eff_start=None]
#   eff_start   – fixed effective start date (None = compute from target_days / TQQQ)

_PERIOD_SPECS: dict[str, dict] = {
    "2y": {
        "label": "近 2 年", "fetch_type": "period",
        "dl_period": "3y", "target_days": 504,
    },
    "3y": {
        "label": "近 3 年", "fetch_type": "period",
        "dl_period": "4y", "target_days": 756,
    },
    "5y": {
        "label": "近 5 年", "fetch_type": "period",
        "dl_period": "6y", "target_days": 1260,
    },
    "10y": {
        "label": "近 10 年", "fetch_type": "range",
        "dl_start": None, "dl_end": None,    # computed at runtime (today − 11 yr)
        "target_days": 2520,
    },
    "2015_2020": {
        "label": "2015—2020", "fetch_type": "range",
        "dl_start": "2014-01-01", "dl_end": "2020-12-31",
        "eff_start": "2015-01-02",
    },
    "2010_2015": {
        "label": "2010—2015", "fetch_type": "range",
        "dl_start": "2009-01-01", "dl_end": "2015-12-31",
        "eff_start": None,   # will use first available TQQQ date (~2010-02-09)
    },
}

_PERIOD_ORDER = ["2y", "3y", "5y", "10y", "2015_2020", "2010_2015"]


# ─────────────────────────────────────────────────────────────────────────────
# Data fetching
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_by_period(dl_period: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Download by yfinance period string (includes warmup year)."""
    qqq  = yf.download("QQQ",  period=dl_period, auto_adjust=True, progress=False)
    tqqq = yf.download("TQQQ", period=dl_period, auto_adjust=True, progress=False)
    for df in (qqq, tqqq):
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
    return qqq, tqqq


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_by_range(start: str, end: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Download by explicit date range (includes warmup year)."""
    qqq  = yf.download("QQQ",  start=start, end=end, auto_adjust=True, progress=False)
    tqqq = yf.download("TQQQ", start=start, end=end, auto_adjust=True, progress=False)
    for df in (qqq, tqqq):
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
    return qqq, tqqq


def _fetch(period_key: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Dispatch to the right fetch function."""
    spec = _PERIOD_SPECS[period_key]
    if spec["fetch_type"] == "period":
        return _fetch_by_period(spec["dl_period"])
    # date-range based
    start = spec.get("dl_start")
    end   = spec.get("dl_end")
    if start is None:   # "10y": compute dynamically
        end_dt   = datetime.now()
        start_dt = end_dt - timedelta(days=365 * 11)
        start = start_dt.strftime("%Y-%m-%d")
        end   = end_dt.strftime("%Y-%m-%d")
    return _fetch_by_range(start, end)


def _get_effective_start(
    qqq_full:  pd.Series,
    tqqq_full: pd.Series,
    period_key: str,
) -> pd.Timestamp:
    """Return the first tradeable date (after warmup, after TQQQ inception)."""
    spec = _PERIOD_SPECS[period_key]

    # Fixed start defined in config
    if spec.get("eff_start"):
        ts = pd.Timestamp(spec["eff_start"])
        # Clamp to actual data range
        return max(ts, qqq_full.index[0])

    # "2010_2015": TQQQ only starts ~Feb 2010 — use first TQQQ date
    if period_key == "2010_2015":
        return tqqq_full.index[0]

    # Period-based / "10y": keep last target_days trading days
    n      = spec.get("target_days", 504)
    offset = max(0, len(qqq_full) - n)
    return qqq_full.index[offset]


# ─────────────────────────────────────────────────────────────────────────────
# Signals
# ─────────────────────────────────────────────────────────────────────────────

def _streak(s: pd.Series) -> pd.Series:
    """Vectorized consecutive-True count (resets to 0 on False)."""
    groups = (s != s.shift()).cumsum()
    return (s.groupby(groups).cumcount() + 1).where(s, 0)


def _build_signals(qqq_close: pd.Series) -> pd.DataFrame:
    ma200 = qqq_close.rolling(200).mean()
    a1    = qqq_close > ma200
    slope = (ma200 - ma200.shift(20)) / ma200.shift(20) * 100
    a2    = slope > -0.5                           # MA200 flat or rising
    a3    = _streak(a1) >= 3                       # 3+ consecutive closes above

    signal       = a1 & a2 & a3
    entry_signal = signal & ~signal.shift(1).fillna(False)   # False→True transition

    below       = qqq_close < ma200
    exit_signal = below & below.shift(1).fillna(False)       # 2 consecutive days below

    cross = a1 & ~a1.shift(1).fillna(False)

    return pd.DataFrame({
        "qqq": qqq_close, "ma200": ma200,
        "a1": a1, "a2": a2, "a3": a3,
        "signal": signal,
        "entry_signal": entry_signal,
        "exit_signal":  exit_signal,
        "cross": cross,
    })


def _allocation(dist: float) -> tuple[str, float]:
    """(mode_label, cash_fraction) per Step 3 with macro_score=3."""
    if dist <= _DISTANCE_THRESH:
        return "Direct Buy", 2 / 3
    elif dist <= 15.0:
        return "Split", 1 / 3
    else:
        return "Split(>15%)", 1 / 3


# ─────────────────────────────────────────────────────────────────────────────
# Trade
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Trade:
    entry_date:  pd.Timestamp
    entry_price: float
    entry_mode:  str
    shares:      float
    cost_buy:    float
    exit_date:   pd.Timestamp | None = None
    exit_price:  float | None = None
    cost_sell:   float = 0.0
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


# ─────────────────────────────────────────────────────────────────────────────
# Simulation
# ─────────────────────────────────────────────────────────────────────────────

def _simulate(
    sig: pd.DataFrame,
    tqqq_close: pd.Series,
    trade_start: pd.Timestamp | None = None,
) -> tuple[list[Trade], pd.Series]:
    """
    Simulate LRS trades day-by-day. Returns (trades, equity_series).

    trade_start: first tradeable day (warmup period is skipped).
    Initial-entry: if signal is already True on trade_start, enter immediately.
    """
    tqqq        = tqqq_close.reindex(sig.index, method="ffill")
    cross_dates = sig.index[sig["cross"]].tolist()

    cash    = _INITIAL_CAPITAL
    shares  = 0.0
    in_pos  = False
    current : Trade | None = None
    trades  : list[Trade]  = []
    equity  : dict         = {}

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

        # ── Exit ──────────────────────────────────────────────────────────
        if in_pos and current is not None and bool(sig.at[date, "exit_signal"]):
            cash      += shares * price - _COST_PER_SIDE
            current.exit_date  = date
            current.exit_price = price
            current.cost_sell  = _COST_PER_SIDE
            trades.append(current)
            shares  = 0.0
            in_pos  = False
            current = None

        # ── Entry ─────────────────────────────────────────────────────────
        # Fire on normal False→True transition, or on day 1 if already bullish
        is_entry = bool(sig.at[date, "entry_signal"])
        if first_day and not in_pos and bool(sig.at[date, "signal"]):
            is_entry = True
        first_day = False

        if not in_pos and is_entry:
            prior       = [d for d in cross_dates if d <= date]
            cross_date  = prior[-1] if prior else date
            cross_raw   = tqqq.get(cross_date)
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
                    cash   -= n * price + _COST_PER_SIDE
                    shares  = float(n)
                    in_pos  = True
                    current = Trade(
                        entry_date=date, entry_price=price,
                        entry_mode=mode, shares=shares, cost_buy=_COST_PER_SIDE,
                    )

        equity[date] = cash + shares * price

    # ── Force-close at period end ─────────────────────────────────────────
    if in_pos and current is not None and shares > 0:
        last_date = sig.index[-1]
        last_price = float(tqqq.iloc[-1])
        cash += shares * last_price - _COST_PER_SIDE
        current.exit_date   = last_date
        current.exit_price  = last_price
        current.cost_sell   = _COST_PER_SIDE
        current.forced_exit = True
        trades.append(current)
        equity[last_date] = cash

    return trades, pd.Series(equity)


# ─────────────────────────────────────────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────────────────────────────────────────

def _max_dd(equity: pd.Series) -> float:
    peak = equity.cummax()
    return float(((equity - peak) / peak).min() * 100)


def _metrics(trades: list[Trade], equity: pd.Series, qqq_close: pd.Series) -> dict:
    n    = len(trades)
    wins = [t for t in trades if t.net_pnl > 0]
    loss = [t for t in trades if t.net_pnl <= 0]
    wsaw = [t for t in trades if t.is_whipsaw]
    avg  = float(np.mean([t.holding_days for t in trades])) if trades else 0.0
    return {
        "strategy_return": (equity.iloc[-1] / _INITIAL_CAPITAL - 1) * 100,
        "qqq_return":      (qqq_close.iloc[-1] / qqq_close.iloc[0] - 1) * 100,
        "final_value":     float(equity.iloc[-1]),
        "n_trades":  n,
        "n_wins":    len(wins),
        "n_losses":  len(loss),
        "win_rate":  (len(wins) / n * 100) if n > 0 else 0.0,
        "max_dd":    _max_dd(equity),
        "avg_days":  avg,
        "n_whipsaws": len(wsaw),
        "total_cost": sum(t.cost_buy + t.cost_sell for t in trades),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Charts  (all-English labels to avoid mojibake)
# ─────────────────────────────────────────────────────────────────────────────

def _fig_equity(
    equity: pd.Series,
    qqq_close: pd.Series,
    trades: list[Trade],
    period_label: str,
) -> plt.Figure:
    qqq_bh = qqq_close / qqq_close.iloc[0] * _INITIAL_CAPITAL
    idx = qqq_close.index
    eq  = equity.reindex(idx, method="ffill").bfill()
    bh  = qqq_bh.reindex(idx, method="ffill")

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(idx, eq.values, color="#38bdf8", linewidth=1.8, label="LRS Strategy")
    ax.plot(idx, bh.values, color="#a78bfa", linewidth=1.4,
            linestyle="--", label="QQQ Buy & Hold")

    ax.fill_between(idx, eq.values, bh.values,
                    where=(eq.values >= bh.values), alpha=0.10,
                    color="#22c55e", interpolate=True)
    ax.fill_between(idx, eq.values, bh.values,
                    where=(eq.values < bh.values),  alpha=0.10,
                    color="#ef4444", interpolate=True)

    for t in trades:
        ax.axvline(t.entry_date, color="#22c55e", alpha=0.20, linewidth=0.6, linestyle=":")
        if t.exit_date:
            c = "#ef4444" if t.net_pnl < 0 else "#22c55e"
            ax.axvline(t.exit_date, color=c, alpha=0.15, linewidth=0.6, linestyle=":")

    ax.set_title(
        f"Equity Curve — LRS vs QQQ Buy & Hold  |  {period_label}"
        f"  (Initial ${_INITIAL_CAPITAL:,.0f})"
    )
    ax.set_ylabel("Portfolio Value (USD)")
    ax.set_xlabel("Date")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax.legend(fontsize=9)
    apply_dark_style(fig, ax)
    plt.tight_layout()
    return fig


def _fig_per_trade(trades: list[Trade], period_label: str) -> plt.Figure:
    if not trades:
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.text(0.5, 0.5, f"No trades in this period ({period_label})",
                ha="center", va="center", transform=ax.transAxes,
                color="#94a3b8", fontsize=12)
        apply_dark_style(fig, ax)
        return fig

    labels  = [t.entry_date.strftime("%y-%m-%d") for t in trades]
    returns = [t.return_pct for t in trades]
    colors  = ["#f59e0b" if t.is_whipsaw else ("#22c55e" if r >= 0 else "#ef4444")
               for t, r in zip(trades, returns)]

    fig, ax = plt.subplots(figsize=(max(10, len(trades) * 1.3), 4))
    ax.bar(range(len(trades)), returns, color=colors, width=0.7, edgecolor="none")
    ax.axhline(0, color="#64748b", linewidth=0.8)
    ax.set_xticks(range(len(trades)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Return (%)")
    ax.set_title(
        f"Per-Trade Return (%)  |  {period_label}"
        "  (green=win / red=loss / orange=whipsaw)"
    )
    for i, (r, t) in enumerate(zip(returns, trades)):
        va  = "bottom" if r >= 0 else "top"
        off = 0.3 if r >= 0 else -0.3
        ax.text(i, r + off, f"{r:.1f}%", ha="center", va=va,
                fontsize=7, color="#e2e8f0")
    apply_dark_style(fig, ax)
    plt.tight_layout()
    return fig


def _fig_drawdown(equity: pd.Series, period_label: str) -> plt.Figure:
    peak = equity.cummax()
    dd   = (equity - peak) / peak * 100

    fig, ax = plt.subplots(figsize=(12, 3))
    ax.fill_between(dd.index, dd.values, 0, color="#ef4444", alpha=0.4)
    ax.plot(dd.index, dd.values, color="#f87171", linewidth=1.0)
    ax.axhline(0, color="#64748b", linewidth=0.8)
    ax.set_title(f"Strategy Drawdown (%)  |  {period_label}")
    ax.set_ylabel("Drawdown (%)")
    ax.set_xlabel("Date")
    apply_dark_style(fig, ax)
    plt.tight_layout()
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Trade log
# ─────────────────────────────────────────────────────────────────────────────

def _trade_df(trades: list[Trade]) -> pd.DataFrame:
    rows = []
    for t in trades:
        tag = "Whipsaw" if t.is_whipsaw else ("Force-Close" if t.forced_exit else "-")
        rows.append({
            "Entry Date":  t.entry_date.date(),
            "Exit Date":   t.exit_date.date() if t.exit_date else "-",
            "Entry ($)":   round(t.entry_price, 2),
            "Exit ($)":    round(t.exit_price,  2) if t.exit_price else "-",
            "Mode":        t.entry_mode,
            "Hold (days)": t.holding_days,
            "Return (%)":  round(t.return_pct, 2),
            "Cost ($)":    round(t.cost_buy + t.cost_sell, 2),
            "Net P&L ($)": round(t.net_pnl, 2),
            "Flag":        tag,
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Assumptions text
# ─────────────────────────────────────────────────────────────────────────────

_ASSUMPTIONS_MD = """
**信号规则（与策略仪表盘 Step 2 一致）**
- **A1** QQQ 日收盘 > MA200
- **A2** MA200 过去 20 日斜率 > −0.5%（平稳或向上）
- **A3** 连续 ≥ 3 日收盘站上 MA200

**仓位比例（Step 3，宏观评分 = 3）**
- 距突破价 ≤ 6% → Direct Buy → 当前现金 **2/3**
- 距突破价 > 6% → Split → 当前现金 **1/3**

**初始入场** 若回测开始时 QQQ 已在 MA200 之上（signal=True），立即入场

**离场** QQQ 连续 2 日收盘低于 MA200

**成本** 每笔买/卖各 $1.99（富途美股：$0.99 佣金 + $1.00 平台费）

**基准** QQQ 买入持有（同期，等额资金）

**Whipsaw** 持仓 ≤ 10 天且亏损
"""


# ─────────────────────────────────────────────────────────────────────────────
# Per-period sub-tab renderer
# ─────────────────────────────────────────────────────────────────────────────

def _render_period(period_key: str) -> None:
    """Render one backtest period sub-tab (run button + cached results)."""
    spec      = _PERIOD_SPECS[period_key]
    label     = spec["label"]
    cache_key = f"bt_{period_key}"

    run = st.button("▶ 运行回测", type="primary", key=f"bt_run_{period_key}")

    if not run and cache_key not in st.session_state:
        st.info(f"点击「运行回测」开始计算 **{label}** 的回测。")
        with st.expander("回测假设说明"):
            st.markdown(_ASSUMPTIONS_MD)
        return

    # ── Run ───────────────────────────────────────────────────────────────
    if run:
        with st.spinner(f"下载 {label} 数据（含预热期）…"):
            try:
                qqq_df, tqqq_df = _fetch(period_key)
            except Exception as exc:
                st.error(f"数据下载失败：{exc}")
                return

        if qqq_df.empty or tqqq_df.empty:
            st.error("QQQ 或 TQQQ 数据为空，请稍后重试。")
            return

        qqq_full  = qqq_df["Close"].squeeze().dropna()
        tqqq_full = tqqq_df["Close"].squeeze().dropna()

        if len(qqq_full) < 220:
            st.error(f"数据量不足（{len(qqq_full)} 天），无法计算 MA200。")
            return

        t_start = _get_effective_start(qqq_full, tqqq_full, period_key)
        qqq_eff = qqq_full[t_start:]

        with st.spinner("计算信号并模拟交易…"):
            sig          = _build_signals(qqq_full)
            trades, eq   = _simulate(sig, tqqq_full, trade_start=t_start)
            m            = _metrics(trades, eq, qqq_eff)

        st.session_state[cache_key] = {
            "trades": trades, "equity": eq,
            "qqq_eff": qqq_eff, "metrics": m,
        }
        st.success("回测完成！")

    # ── Render ────────────────────────────────────────────────────────────
    res = st.session_state.get(cache_key)
    if res is None:
        return

    trades  = res["trades"]
    equity  = res["equity"]
    qqq_eff = res["qqq_eff"]
    m       = res["metrics"]

    qqq_r    = m["qqq_return"]
    bh_final = _INITIAL_CAPITAL * (1 + qqq_r / 100)
    strat_r  = m["strategy_return"]
    delta    = strat_r - qqq_r

    st.caption(
        f"数据区间：{qqq_eff.index[0].date()} → {qqq_eff.index[-1].date()}"
    )

    # ── Metric block 1: performance ───────────────────────────────────────
    with st.container(border=True):
        # Row 1: Total return
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("LRS 总收益率",  f"{strat_r:+.1f}%",
                  f"vs QQQ {delta:+.1f}%", delta_color="normal")
        c2.metric("QQQ B&H 收益率", f"{qqq_r:+.1f}%")
        c3.metric("LRS 最终资产",   f"${m['final_value']:,.0f}")
        c4.metric("QQQ B&H 最终",  f"${bh_final:,.0f}")

        st.divider()

        # Row 2: Risk stats
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("最大回撤",   f"{m['max_dd']:.1f}%")
        c2.metric("交易次数",
                  str(m["n_trades"]),
                  f"盈 {m['n_wins']} / 亏 {m['n_losses']}")
        c3.metric("胜率",       f"{m['win_rate']:.0f}%")
        c4.metric("Whipsaw",
                  f"{m['n_whipsaws']} 次",
                  f"均持仓 {m['avg_days']:.0f} 天")

    # ── Equity curve ──────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("##### Equity Curve")
        st.pyplot(_fig_equity(equity, qqq_eff, trades, label), clear_figure=True)

    # ── Per-trade returns ─────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("##### Per-Trade Return")
        st.pyplot(_fig_per_trade(trades, label), clear_figure=True)

    # ── Drawdown ──────────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("##### Drawdown")
        st.pyplot(_fig_drawdown(equity, label), clear_figure=True)

    # ── Trade log ─────────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("##### 交易明细")
        if trades:
            st.dataframe(
                _trade_df(trades),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Return (%)":  st.column_config.NumberColumn(format="%.2f %%"),
                    "Net P&L ($)": st.column_config.NumberColumn(format="$ %.2f"),
                },
            )
            st.caption(
                f"Total cost: ${m['total_cost']:.2f}  |  "
                f"Period: {qqq_eff.index[0].date()} → {qqq_eff.index[-1].date()}"
            )
        else:
            st.info("该区间内未产生任何交易信号。")

    with st.expander("回测假设说明"):
        st.markdown(_ASSUMPTIONS_MD)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def render_backtest_tab() -> None:
    st.subheader("LRS TQQQ 策略回测")
    st.caption(
        "LRS 策略 vs QQQ 买入持有 | 六个时间窗口独立缓存，切换 tab 无需重新运行。"
    )

    tabs = st.tabs([_PERIOD_SPECS[k]["label"] for k in _PERIOD_ORDER])
    for tab, period_key in zip(tabs, _PERIOD_ORDER):
        with tab:
            _render_period(period_key)
