from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

from web.pages.wheel import strategy_cache as cache
from web.pages.wheel.strategy_shared import (
    annual_to_daily,
    apply_dark_style,
    bs_price,
    close_series,
    rsi,
)

INITIAL_CAPITAL = 10_000.0
COMMISSION = 2.99
CASH_RATE = 0.03
RISK_FREE = 0.03
PUT_OTM = 0.06
CALL_OTM = 0.02
PUT_TP = 0.50
CALL_TP = 0.80
WEEKLY_DTE = 7
MAX_CONTRACTS = 1


def _series_to_records(s: pd.Series) -> list[list]:
    return [[str(i.date()), float(v)] for i, v in s.items()]


def _records_to_series(rows: list[list]) -> pd.Series:
    if not rows:
        return pd.Series(dtype=float)
    idx = pd.to_datetime([r[0] for r in rows])
    vals = [float(r[1]) for r in rows]
    return pd.Series(vals, index=idx).sort_index()


def _serialize_result(res: dict) -> dict:
    return {
        "equity": _series_to_records(res["equity"]),
        "benchmark_bh": _series_to_records(res["benchmark_bh"]),
        "monthly_pct": _series_to_records(res["monthly_pct"]),
        "ivr": _series_to_records(res["ivr"]),
        "rsi": _series_to_records(res["rsi"]),
        "underlying": _series_to_records(res["underlying"]),
        "signal": _series_to_records(res["signal"]),
        "metrics": dict(res["metrics"]),
        "trade_log": list(res["trade_log"]),
        "underlying_ticker": str(res.get("underlying_ticker", "TQQQ")),
        "signal_ticker": str(res.get("signal_ticker", "QQQ")),
    }


def _deserialize_result(payload: dict | None) -> dict | None:
    if not payload:
        return None
    try:
        return {
            "equity": _records_to_series(payload.get("equity", [])),
            "benchmark_bh": _records_to_series(payload.get("benchmark_bh", [])),
            "monthly_pct": _records_to_series(payload.get("monthly_pct", [])),
            "ivr": _records_to_series(payload.get("ivr", [])),
            "rsi": _records_to_series(payload.get("rsi", [])),
            "underlying": _records_to_series(payload.get("underlying", [])),
            "signal": _records_to_series(payload.get("signal", [])),
            "metrics": dict(payload.get("metrics", {})),
            "trade_log": list(payload.get("trade_log", [])),
            "underlying_ticker": str(payload.get("underlying_ticker", "TQQQ")),
            "signal_ticker": str(payload.get("signal_ticker", "QQQ")),
        }
    except Exception:
        return None


@dataclass
class Position:
    kind: str  # put/call
    open_date: pd.Timestamp
    expiry: pd.Timestamp
    strike: float
    premium_open: float
    qty: int = 1


def _next_friday(d: pd.Timestamp) -> pd.Timestamp:
    days = (4 - d.weekday()) % 7
    return d + pd.Timedelta(days=days)


def _option_expiry(open_date: pd.Timestamp) -> pd.Timestamp:
    nf = _next_friday(open_date)
    if nf == open_date:
        nf = nf + pd.Timedelta(days=7)
    return nf


def _rolling_hv(close: pd.Series, window: int = 20) -> pd.Series:
    r = close.pct_change()
    return r.rolling(window).std() * np.sqrt(252)


def _iv_and_ivr(close: pd.Series) -> tuple[pd.Series, pd.Series]:
    hv = _rolling_hv(close, 20).bfill().fillna(0.45)
    iv = (hv * 1.15).clip(lower=0.10, upper=2.5)
    iv_min = iv.rolling(252, min_periods=20).min()
    iv_max = iv.rolling(252, min_periods=20).max()
    ivr = ((iv - iv_min) / (iv_max - iv_min).replace(0, np.nan) * 100.0).fillna(50.0)
    return iv, ivr.clip(lower=0, upper=100)


def _fetch_option_mid_from_chain(
    ticker_obj: yf.Ticker,
    expiry: pd.Timestamp,
    strike: float,
    kind: str,
) -> float | None:
    try:
        chain = ticker_obj.option_chain(expiry.strftime("%Y-%m-%d"))
        df = chain.puts if kind == "put" else chain.calls
        if df is None or df.empty:
            return None
        i = (df["strike"] - strike).abs().idxmin()
        row = df.loc[i]
        bid = float(row.get("bid", np.nan))
        ask = float(row.get("ask", np.nan))
        last = float(row.get("lastPrice", np.nan))
        if np.isfinite(bid) and np.isfinite(ask) and bid > 0 and ask > 0:
            return 0.5 * (bid + ask)
        if np.isfinite(last) and last > 0:
            return last
    except Exception:
        return None
    return None


def _option_price(
    ticker_obj: yf.Ticker,
    spot: float,
    strike: float,
    now: pd.Timestamp,
    expiry: pd.Timestamp,
    sigma: float,
    kind: str,
) -> tuple[float, str]:
    prem = _fetch_option_mid_from_chain(ticker_obj, expiry, strike, kind)
    if prem is not None:
        return prem, "chain"
    t = max((expiry - now).days / 365.0, 0.0)
    return bs_price(spot, strike, t, RISK_FREE, sigma, kind), "bs"


def _max_dd(equity: pd.Series) -> float:
    peak = equity.cummax()
    return float(((equity - peak) / peak).min() * 100.0)


def _simulate_aggressive(
    start: date,
    end: date,
    underlying_ticker: str = "TQQQ",
    signal_ticker: str = "QQQ",
    put_tp: float = PUT_TP,
    call_tp: float = CALL_TP,
    put_sl: float | None = None,
    call_sl: float | None = None,
) -> dict:
    sig = close_series(signal_ticker, start.isoformat(), (end + timedelta(days=1)).isoformat())
    ul = close_series(underlying_ticker, start.isoformat(), (end + timedelta(days=1)).isoformat())
    idx = sig.index.intersection(ul.index)
    sig = sig.reindex(idx).ffill()
    ul = ul.reindex(idx).ffill()
    rs = rsi(sig, 14).fillna(50.0)
    iv, ivr = _iv_and_ivr(ul)
    iv = iv.reindex(idx).ffill().bfill()
    ivr = ivr.reindex(idx).ffill().bfill()

    ticker_obj = yf.Ticker(underlying_ticker)
    cash = INITIAL_CAPITAL
    shares = 0
    pos: Position | None = None
    trade_log: list[dict] = []
    equity = {}
    daily = annual_to_daily(CASH_RATE)
    chain_hits = 0
    bs_hits = 0

    for d in idx:
        cash *= daily
        spot = float(ul.loc[d])
        sigma = float(iv.loc[d])

        liab = 0.0
        if pos is not None:
            mark, src = _option_price(ticker_obj, spot, pos.strike, d, pos.expiry, sigma, pos.kind)
            liab = mark * 100 * pos.qty
            chain_hits += int(src == "chain")
            bs_hits += int(src == "bs")

            tp_ratio = (pos.premium_open - mark) / max(pos.premium_open, 1e-9)
            if pos.kind == "put" and tp_ratio >= put_tp:
                cash -= mark * 100 * pos.qty + COMMISSION
                pnl = (pos.premium_open - mark) * 100 * pos.qty - 2 * COMMISSION
                trade_log.append(
                    {
                        "date": d,
                        "type": "PUT",
                        "action": "TP_Close",
                        "strike": pos.strike,
                        "spot": spot,
                        "premium": pos.premium_open,
                        "close_cost": mark,
                        "pnl": pnl,
                        "hold_days": (d - pos.open_date).days,
                        "result": "Win" if pnl > 0 else "Loss",
                    }
                )
                pos = None
                liab = 0.0
            elif pos.kind == "call" and tp_ratio >= call_tp:
                cash -= mark * 100 * pos.qty + COMMISSION
                pnl = (pos.premium_open - mark) * 100 * pos.qty - 2 * COMMISSION
                trade_log.append(
                    {
                        "date": d,
                        "type": "CALL",
                        "action": "TP_Close",
                        "strike": pos.strike,
                        "spot": spot,
                        "premium": pos.premium_open,
                        "close_cost": mark,
                        "pnl": pnl,
                        "hold_days": (d - pos.open_date).days,
                        "result": "Win" if pnl > 0 else "Loss",
                    }
                )
                pos = None
                liab = 0.0
            elif pos.kind == "put" and put_sl is not None:
                # put_sl is loss multiple on premium, e.g. 2.0 => option rises 200% from entry premium
                sl_hit = (mark - pos.premium_open) / max(pos.premium_open, 1e-9) >= put_sl
                if sl_hit:
                    cash -= mark * 100 * pos.qty + COMMISSION
                    pnl = (pos.premium_open - mark) * 100 * pos.qty - 2 * COMMISSION
                    trade_log.append(
                        {
                            "date": d,
                            "type": "PUT",
                            "action": "SL_Close",
                            "strike": pos.strike,
                            "spot": spot,
                            "premium": pos.premium_open,
                            "close_cost": mark,
                            "pnl": pnl,
                            "hold_days": (d - pos.open_date).days,
                            "result": "Win" if pnl > 0 else "Loss",
                        }
                    )
                    pos = None
                    liab = 0.0
            elif pos.kind == "call" and call_sl is not None:
                sl_hit = (mark - pos.premium_open) / max(pos.premium_open, 1e-9) >= call_sl
                if sl_hit:
                    cash -= mark * 100 * pos.qty + COMMISSION
                    pnl = (pos.premium_open - mark) * 100 * pos.qty - 2 * COMMISSION
                    trade_log.append(
                        {
                            "date": d,
                            "type": "CALL",
                            "action": "SL_Close",
                            "strike": pos.strike,
                            "spot": spot,
                            "premium": pos.premium_open,
                            "close_cost": mark,
                            "pnl": pnl,
                            "hold_days": (d - pos.open_date).days,
                            "result": "Win" if pnl > 0 else "Loss",
                        }
                    )
                    pos = None
                    liab = 0.0

        if pos is not None and d >= pos.expiry:
            if pos.kind == "put":
                intrinsic = max(pos.strike - spot, 0.0)
                assigned = spot < pos.strike
                if assigned:
                    cash -= pos.strike * 100 * pos.qty
                    shares += 100 * pos.qty
                pnl = (pos.premium_open - intrinsic) * 100 * pos.qty - COMMISSION
                trade_log.append(
                    {
                        "date": d,
                        "type": "PUT",
                        "action": "Assigned" if assigned else "Expire_OTM",
                        "strike": pos.strike,
                        "spot": spot,
                        "premium": pos.premium_open,
                        "close_cost": intrinsic,
                        "pnl": pnl,
                        "hold_days": (d - pos.open_date).days,
                        "result": "Win" if pnl > 0 else "Loss",
                    }
                )
            else:
                intrinsic = max(spot - pos.strike, 0.0)
                called = spot > pos.strike and shares >= 100
                if called:
                    cash += pos.strike * 100 * pos.qty
                    shares -= 100 * pos.qty
                pnl = (pos.premium_open - intrinsic) * 100 * pos.qty - COMMISSION
                trade_log.append(
                    {
                        "date": d,
                        "type": "CALL",
                        "action": "Call_Away" if called else "Expire_OTM",
                        "strike": pos.strike,
                        "spot": spot,
                        "premium": pos.premium_open,
                        "close_cost": intrinsic,
                        "pnl": pnl,
                        "hold_days": (d - pos.open_date).days,
                        "result": "Win" if pnl > 0 else "Loss",
                    }
                )
            pos = None
            liab = 0.0

        if d.weekday() == 4 and pos is None:
            if shares < 100:
                strike = round(spot * (1.0 - PUT_OTM), 2)
                if float(ivr.loc[d]) > 20 and float(rs.loc[d]) < 65 and cash >= strike * 100:
                    expiry = _option_expiry(d)
                    premium, src = _option_price(ticker_obj, spot, strike, d, expiry, sigma, "put")
                    chain_hits += int(src == "chain")
                    bs_hits += int(src == "bs")
                    cash += premium * 100 - COMMISSION
                    pos = Position("put", d, expiry, strike, premium, MAX_CONTRACTS)
            else:
                strike = round(spot * (1.0 + CALL_OTM), 2)
                expiry = _option_expiry(d)
                premium, src = _option_price(ticker_obj, spot, strike, d, expiry, sigma, "call")
                chain_hits += int(src == "chain")
                bs_hits += int(src == "bs")
                cash += premium * 100 - COMMISSION
                pos = Position("call", d, expiry, strike, premium, MAX_CONTRACTS)

        if pos is not None:
            mark, _ = _option_price(ticker_obj, spot, pos.strike, d, pos.expiry, sigma, pos.kind)
            liab = mark * 100 * pos.qty
        equity[d] = cash + shares * spot - liab

    eq = pd.Series(equity).sort_index()
    ret = eq.pct_change().dropna()
    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 0.001)
    cagr = (float(eq.iloc[-1]) / INITIAL_CAPITAL) ** (1.0 / years) - 1.0
    ann_vol = ret.std() * math.sqrt(252) if len(ret) > 1 else 1.0
    sharpe = (cagr - RISK_FREE) / ann_vol if ann_vol > 0 else 0.0
    mdd = _max_dd(eq)
    wins = [x for x in trade_log if x["pnl"] > 0]
    losses = [x for x in trade_log if x["pnl"] <= 0]
    monthly = eq.resample("ME").last().pct_change().dropna() * 100
    benchmark_bh = INITIAL_CAPITAL * sig / float(sig.iloc[0])

    return {
        "equity": eq,
        "benchmark_bh": benchmark_bh.reindex(eq.index).ffill(),
        "trade_log": trade_log,
        "metrics": {
            "total_return": (float(eq.iloc[-1]) / INITIAL_CAPITAL - 1.0) * 100,
            "final_value": float(eq.iloc[-1]),
            "cagr": cagr * 100,
            "sharpe": sharpe,
            "max_dd": mdd,
            "n_trades": len(trade_log),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": (len(wins) / len(trade_log) * 100) if trade_log else 0.0,
            "avg_win": float(np.mean([x["pnl"] for x in wins])) if wins else 0.0,
            "avg_loss": float(np.mean([x["pnl"] for x in losses])) if losses else 0.0,
            "chain_quotes": chain_hits,
            "bs_quotes": bs_hits,
        },
        "monthly_pct": monthly,
        "ivr": ivr,
        "rsi": rs,
        "underlying": ul,
        "signal": sig,
        "underlying_ticker": underlying_ticker,
        "signal_ticker": signal_ticker,
    }


def _render_metrics(m: dict) -> None:
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("总收益率", f"{m['total_return']:+.1f}%")
    c2.metric("CAGR", f"{m['cagr']:+.1f}%")
    c3.metric("Sharpe", f"{m['sharpe']:.3f}")
    c4.metric("最大回撤", f"{m['max_dd']:.1f}%")
    c5.metric("胜率", f"{m['win_rate']:.0f}%")
    c6.metric("交易笔数", str(m["n_trades"]))
    st.caption(
        f"初始 ${INITIAL_CAPITAL:,.0f} | 佣金 ${COMMISSION:.2f}/笔 | 空闲现金 {CASH_RATE:.0%} 年化 | "
        f"期权定价：chain={m['chain_quotes']} 次，BS fallback={m['bs_quotes']} 次"
    )


def _render_charts(res: dict) -> None:
    eq = res["equity"]
    bh = res["benchmark_bh"]
    monthly = res["monthly_pct"]
    dd = (eq / eq.cummax() - 1.0) * 100

    fig1, ax1 = plt.subplots(figsize=(10, 3.8))
    ax1.plot(eq.index, eq.values, lw=1.8, color="#34d399", label="Wheel Equity")
    ax1.plot(
        bh.index,
        bh.values,
        lw=1.2,
        ls="--",
        color="#60a5fa",
        label=f"{res.get('signal_ticker', 'Benchmark')} B&H",
    )
    ax1.set_title("Portfolio Equity Curve")
    ax1.set_ylabel("Portfolio ($)")
    ax1.legend(loc="upper left")
    apply_dark_style(fig1, ax1)
    st.pyplot(fig1, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        fig2, ax2 = plt.subplots(figsize=(7, 3.0))
        ax2.plot(dd.index, dd.values, lw=1.4, color="#fb7185")
        ax2.fill_between(dd.index, dd.values, 0, color="#fb7185", alpha=0.12)
        ax2.set_title("Drawdown Curve (%)")
        apply_dark_style(fig2, ax2)
        st.pyplot(fig2, use_container_width=True)
    with c2:
        fig3, ax3 = plt.subplots(figsize=(7, 3.0))
        colors = ["#34d399" if x >= 0 else "#fb7185" for x in monthly.values]
        ax3.bar(monthly.index.strftime("%Y-%m"), monthly.values, color=colors, alpha=0.85)
        ax3.set_title("Monthly Return (%)")
        ax3.tick_params(axis="x", rotation=45)
        apply_dark_style(fig3, ax3)
        st.pyplot(fig3, use_container_width=True)

    fig4, ax4 = plt.subplots(figsize=(10, 3.2))
    ivr = res["ivr"].reindex(eq.index).ffill()
    rsi_s = res["rsi"].reindex(eq.index).ffill()
    ul = res["underlying"].reindex(eq.index).ffill()
    ax4.plot(ivr.index, ivr.values, color="#22d3ee", lw=1.2, label="IVR%")
    ax4.plot(rsi_s.index, rsi_s.values, color="#fbbf24", lw=1.1, label="RSI")
    ax4_t = ax4.twinx()
    ul_name = res.get("underlying_ticker", "Underlying")
    ax4_t.plot(ul.index, ul.values, color="#a78bfa", lw=1.0, alpha=0.75, label=ul_name)
    ax4.set_title(f"Indicators: IVR / RSI / {ul_name}")
    apply_dark_style(fig4, ax4, ax4_t)
    st.pyplot(fig4, use_container_width=True)


def _render_trade_table(res: dict) -> None:
    rows = res["trade_log"]
    if not rows:
        st.info("当前区间没有生成有效交易。")
        return
    df = pd.DataFrame(rows)
    df = df.rename(
        columns={
            "date": "日期",
            "type": "类型",
            "action": "操作",
            "strike": "行权价",
            "spot": "标的价",
            "premium": "开仓权利金",
            "close_cost": "平仓成本",
            "pnl": "盈亏",
            "hold_days": "持仓天数",
            "result": "结果",
        }
    )
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_wheel_page(
    *,
    strategy_name: str,
    underlying_ticker: str,
    signal_ticker: str,
    state_prefix: str,
) -> None:
    st.subheader(strategy_name)
    tab_aggr = st.tabs(["激进风格"])[0]
    with tab_aggr:
        st.markdown(f"#### 激进风格（{underlying_ticker}: Sell Put + Covered Call）")
        st.caption("规则：7DTE、Put OTM 6%、CC OTM 2%，止盈/止损可前端配置。")
        c1, c2 = st.columns(2)
        with c1:
            end_default = date.today()
            end_d = st.date_input("回测结束日期", value=end_default, key=f"{state_prefix}_end")
        with c2:
            start_default = end_default - timedelta(days=365)
            start_d = st.date_input("回测开始日期", value=start_default, key=f"{state_prefix}_start")

        p1, p2, p3, p4 = st.columns(4)
        with p1:
            put_tp_pct = st.number_input("Put止盈(%)", min_value=1.0, max_value=95.0, value=PUT_TP * 100, step=1.0, key=f"{state_prefix}_put_tp")
        with p2:
            call_tp_pct = st.number_input("Call止盈(%)", min_value=1.0, max_value=99.0, value=CALL_TP * 100, step=1.0, key=f"{state_prefix}_call_tp")
        with p3:
            enable_put_sl = st.toggle("启用Put止损", value=False, key=f"{state_prefix}_put_sl_enabled")
            put_sl_x = st.number_input("Put止损倍数(亏损x%)", min_value=50.0, max_value=1000.0, value=200.0, step=50.0, disabled=not enable_put_sl, key=f"{state_prefix}_put_sl_x")
        with p4:
            enable_call_sl = st.toggle("启用Call止损", value=False, key=f"{state_prefix}_call_sl_enabled")
            call_sl_x = st.number_input("Call止损倍数(亏损x%)", min_value=50.0, max_value=1000.0, value=200.0, step=50.0, disabled=not enable_call_sl, key=f"{state_prefix}_call_sl_x")

        if st.button("运行激进风格回测", key=f"run_{state_prefix}_aggr", use_container_width=True):
            with st.spinner("正在获取 yfinance 数据并回测..."):
                try:
                    res = _simulate_aggressive(
                        start_d,
                        end_d,
                        underlying_ticker=underlying_ticker,
                        signal_ticker=signal_ticker,
                        put_tp=put_tp_pct / 100.0,
                        call_tp=call_tp_pct / 100.0,
                        put_sl=(put_sl_x / 100.0) if enable_put_sl else None,
                        call_sl=(call_sl_x / 100.0) if enable_call_sl else None,
                    )
                    cache.save(
                        f"{state_prefix}_aggressive_latest",
                        {
                            "start": str(start_d),
                            "end": str(end_d),
                            "underlying_ticker": underlying_ticker,
                            "signal_ticker": signal_ticker,
                            "put_tp_pct": put_tp_pct,
                            "call_tp_pct": call_tp_pct,
                            "put_sl_x_pct": put_sl_x if enable_put_sl else None,
                            "call_sl_x_pct": call_sl_x if enable_call_sl else None,
                            "metrics": res["metrics"],
                            "n_trades": len(res["trade_log"]),
                            "result_payload": _serialize_result(res),
                        },
                    )
                    st.session_state[f"{state_prefix}_wheel_aggr_result"] = res
                    st.success("回测完成。")
                except Exception as exc:
                    st.error(f"回测失败：{exc}")

        res = st.session_state.get(f"{state_prefix}_wheel_aggr_result")
        if not res:
            cached = cache.load(f"{state_prefix}_aggressive_latest")
            if cached:
                restored = _deserialize_result(cached.get("result_payload"))
                if restored is not None:
                    res = restored
                    st.session_state[f"{state_prefix}_wheel_aggr_result"] = restored
                    st.caption(
                        f"已加载上次回测结果：{cached.get('start')} → {cached.get('end')}（重新运行可更新）。"
                    )
                else:
                    st.info(
                        f"最近一次回测：{cached.get('start')} → {cached.get('end')}，请点击上方按钮重新生成完整图表。"
                    )
            else:
                st.info("点击上方按钮开始回测。")
            if not res:
                return

        _render_metrics(res["metrics"])
        _render_charts(res)
        st.markdown("#### 交易记录")
        _render_trade_table(res)


def render_tqqq_wheel_page() -> None:
    render_wheel_page(
        strategy_name="TQQQ Wheel策略",
        underlying_ticker="TQQQ",
        signal_ticker="QQQ",
        state_prefix="tqqq_wheel",
    )


def render_soxl_wheel_page() -> None:
    render_wheel_page(
        strategy_name="SOXL Wheel策略",
        underlying_ticker="SOXL",
        signal_ticker="SOXX",
        state_prefix="soxl_wheel",
    )

