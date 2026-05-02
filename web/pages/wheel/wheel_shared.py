from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta, datetime
import io
import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

from web.pages.wheel import strategy_cache as cache
from web.pages.wheel.style_profiles import StyleProfile
from web.pages.wheel.strategy_shared import annual_to_daily, apply_dark_style, bs_price, close_series, rsi

INITIAL_CAPITAL = 10_000.0
COMMISSION = 2.99
CASH_RATE = 0.03
RISK_FREE = 0.03
MAX_CONTRACTS = 1
ENGINE_VERSION = "wheel-v3-split"
RULE_VERSION = "tqqq-wheel-manual-v1.1"


@dataclass
class Position:
    kind: str
    open_date: pd.Timestamp
    expiry: pd.Timestamp
    strike: float
    premium_open: float
    qty: int = 1


def series_to_records(s: pd.Series) -> list[list]:
    return [[str(i.date()), float(v)] for i, v in s.items()]


def records_to_series(rows: list[list]) -> pd.Series:
    if not rows:
        return pd.Series(dtype=float)
    idx = pd.to_datetime([r[0] for r in rows])
    vals = [float(r[1]) for r in rows]
    return pd.Series(vals, index=idx).sort_index()


def serialize_result(res: dict) -> dict:
    return {
        "equity": series_to_records(res["equity"]),
        "benchmark_bh": series_to_records(res["benchmark_bh"]),
        "monthly_pct": series_to_records(res["monthly_pct"]),
        "ivr": series_to_records(res["ivr"]),
        "rsi": series_to_records(res["rsi"]),
        "underlying": series_to_records(res["underlying"]),
        "signal": series_to_records(res["signal"]),
        "metrics": dict(res["metrics"]),
        "trade_log": list(res["trade_log"]),
        "underlying_ticker": str(res.get("underlying_ticker", "TQQQ")),
        "signal_ticker": str(res.get("signal_ticker", "QQQ")),
        "style": str(res.get("style", "aggressive")),
    }


def deserialize_result(payload: dict | None) -> dict | None:
    if not payload:
        return None
    try:
        return {
            "equity": records_to_series(payload.get("equity", [])),
            "benchmark_bh": records_to_series(payload.get("benchmark_bh", [])),
            "monthly_pct": records_to_series(payload.get("monthly_pct", [])),
            "ivr": records_to_series(payload.get("ivr", [])),
            "rsi": records_to_series(payload.get("rsi", [])),
            "underlying": records_to_series(payload.get("underlying", [])),
            "signal": records_to_series(payload.get("signal", [])),
            "metrics": dict(payload.get("metrics", {})),
            "trade_log": list(payload.get("trade_log", [])),
            "underlying_ticker": str(payload.get("underlying_ticker", "TQQQ")),
            "signal_ticker": str(payload.get("signal_ticker", "QQQ")),
            "style": str(payload.get("style", "aggressive")),
        }
    except Exception:
        return None


def _rolling_hv(close: pd.Series, window: int = 20) -> pd.Series:
    return close.pct_change().rolling(window).std() * np.sqrt(252)


def _iv_and_ivr(close: pd.Series) -> tuple[pd.Series, pd.Series]:
    hv = _rolling_hv(close, 20).bfill().fillna(0.45)
    iv = (hv * 1.15).clip(lower=0.10, upper=2.5)
    iv_min = iv.rolling(252, min_periods=20).min()
    iv_max = iv.rolling(252, min_periods=20).max()
    ivr = ((iv - iv_min) / (iv_max - iv_min).replace(0, np.nan) * 100.0).fillna(50.0)
    return iv, ivr.clip(lower=0, upper=100)


def _fetch_option_mid_from_chain(ticker_obj: yf.Ticker, expiry: pd.Timestamp, strike: float, kind: str) -> float | None:
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


def _option_expiry(open_date: pd.Timestamp, dte: int) -> pd.Timestamp:
    return open_date + pd.Timedelta(days=int(dte))


def _max_dd(equity: pd.Series) -> float:
    peak = equity.cummax()
    return float(((equity - peak) / peak).min() * 100.0)


def simulate_wheel(
    *,
    style: StyleProfile,
    start: date,
    end: date,
    underlying_ticker: str,
    signal_ticker: str,
    put_tp: float,
    call_tp: float,
    put_sl: float | None,
    call_sl: float | None,
    put_otm: float,
    call_otm: float,
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
    stock_cost_basis = 0.0
    pos: Position | None = None
    trade_log: list[dict] = []
    equity: dict = {}
    daily = annual_to_daily(CASH_RATE)
    chain_hits = 0
    bs_hits = 0
    last_put_open: pd.Timestamp | None = None
    cooldown_until: pd.Timestamp | None = None
    confirm_counter = 0

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
            loss_mult = (mark - pos.premium_open) / max(pos.premium_open, 1e-9)
            tp_ratio = (pos.premium_open - mark) / max(pos.premium_open, 1e-9)

            if pos.kind == "put" and tp_ratio >= put_tp:
                cash -= mark * 100 * pos.qty + COMMISSION
                pnl = (pos.premium_open - mark) * 100 * pos.qty - 2 * COMMISSION
                trade_log.append({"date": d, "type": "PUT", "action": "TP_Close", "strike": pos.strike, "spot": spot, "premium": pos.premium_open, "close_cost": mark, "pnl": pnl, "hold_days": (d - pos.open_date).days, "result": "Win" if pnl > 0 else "Loss"})
                pos = None
                liab = 0.0
            elif pos.kind == "call" and tp_ratio >= call_tp:
                cash -= mark * 100 * pos.qty + COMMISSION
                pnl = (pos.premium_open - mark) * 100 * pos.qty - 2 * COMMISSION
                trade_log.append({"date": d, "type": "CALL", "action": "TP_Close", "strike": pos.strike, "spot": spot, "premium": pos.premium_open, "close_cost": mark, "pnl": pnl, "hold_days": (d - pos.open_date).days, "result": "Win" if pnl > 0 else "Loss"})
                pos = None
                liab = 0.0
            elif pos.kind == "put" and style.roll_preferred and style.roll_stop_threshold is not None and loss_mult >= style.roll_stop_threshold and (pos.expiry - d).days > 14:
                new_expiry = d + pd.Timedelta(days=35)
                new_strike = round(min(pos.strike * 0.95, spot * 0.90), 2)
                new_prem, src2 = _option_price(ticker_obj, spot, new_strike, d, new_expiry, sigma, "put")
                chain_hits += int(src2 == "chain")
                bs_hits += int(src2 == "bs")
                net_credit = new_prem - mark
                if net_credit >= 0:
                    cash += (new_prem - mark) * 100 - 2 * COMMISSION
                    trade_log.append({"date": d, "type": "PUT", "action": "ROLL_PUT", "strike": pos.strike, "spot": spot, "premium": pos.premium_open, "close_cost": mark, "pnl": (pos.premium_open - mark) * 100 - 2 * COMMISSION, "hold_days": (d - pos.open_date).days, "result": "Roll"})
                    pos = Position("put", d, new_expiry, new_strike, new_prem, MAX_CONTRACTS)
                    liab = 0.0
            elif pos.kind == "put" and put_sl is not None and loss_mult >= put_sl:
                cash -= mark * 100 * pos.qty + COMMISSION
                pnl = (pos.premium_open - mark) * 100 * pos.qty - 2 * COMMISSION
                trade_log.append({"date": d, "type": "PUT", "action": "SL_Close", "strike": pos.strike, "spot": spot, "premium": pos.premium_open, "close_cost": mark, "pnl": pnl, "hold_days": (d - pos.open_date).days, "result": "Win" if pnl > 0 else "Loss"})
                pos = None
                liab = 0.0
                if style.cooldown_days > 0:
                    cooldown_until = d + pd.Timedelta(days=style.cooldown_days)
            elif pos.kind == "call" and call_sl is not None and loss_mult >= call_sl:
                cash -= mark * 100 * pos.qty + COMMISSION
                pnl = (pos.premium_open - mark) * 100 * pos.qty - 2 * COMMISSION
                trade_log.append({"date": d, "type": "CALL", "action": "SL_Close", "strike": pos.strike, "spot": spot, "premium": pos.premium_open, "close_cost": mark, "pnl": pnl, "hold_days": (d - pos.open_date).days, "result": "Win" if pnl > 0 else "Loss"})
                pos = None
                liab = 0.0

        if pos is not None and d >= pos.expiry:
            if pos.kind == "put":
                intrinsic = max(pos.strike - spot, 0.0)
                assigned = spot < pos.strike
                if assigned:
                    qty = 100 * pos.qty
                    cash -= pos.strike * qty
                    prev_cost = stock_cost_basis * shares
                    shares += qty
                    stock_cost_basis = ((prev_cost + pos.strike * qty) / shares) if shares > 0 else 0.0
                pnl = (pos.premium_open - intrinsic) * 100 * pos.qty - COMMISSION
                trade_log.append({"date": d, "type": "PUT", "action": "Assigned" if assigned else "Expire_OTM", "strike": pos.strike, "spot": spot, "premium": pos.premium_open, "close_cost": intrinsic, "pnl": pnl, "hold_days": (d - pos.open_date).days, "result": "Win" if pnl > 0 else "Loss"})
            else:
                intrinsic = max(spot - pos.strike, 0.0)
                called = spot > pos.strike and shares >= 100
                if called:
                    qty = 100 * pos.qty
                    cash += pos.strike * qty
                    shares -= qty
                    if shares == 0:
                        stock_cost_basis = 0.0
                pnl = (pos.premium_open - intrinsic) * 100 * pos.qty - COMMISSION
                trade_log.append({"date": d, "type": "CALL", "action": "Call_Away" if called else "Expire_OTM", "strike": pos.strike, "spot": spot, "premium": pos.premium_open, "close_cost": intrinsic, "pnl": pnl, "hold_days": (d - pos.open_date).days, "result": "Win" if pnl > 0 else "Loss"})
            pos = None
            liab = 0.0

        allow_cycle = last_put_open is None or (d - last_put_open).days >= style.entry_cycle_days
        in_cooldown = cooldown_until is not None and d <= cooldown_until
        if pos is None:
            if shares < 100:
                strike = round(spot * (1.0 - put_otm), 2)
                base_cond = float(ivr.loc[d]) > style.ivr_min and float(rs.loc[d]) < style.rsi_max and cash >= strike * 100 and not in_cooldown
                confirm_counter = (confirm_counter + 1) if base_cond else 0
                confirmed = confirm_counter >= max(1, style.confirm_days + 1)
                if allow_cycle and base_cond and confirmed:
                    expiry = _option_expiry(d, style.dte)
                    premium, src = _option_price(ticker_obj, spot, strike, d, expiry, sigma, "put")
                    chain_hits += int(src == "chain")
                    bs_hits += int(src == "bs")
                    cash += premium * 100 - COMMISSION
                    pos = Position("put", d, expiry, strike, premium, MAX_CONTRACTS)
                    last_put_open = d
            else:
                strike = spot * (1.0 + call_otm)
                if style.cc_min_cost_basis:
                    strike = max(strike, stock_cost_basis)
                if style.cc_pause_below_cost_ratio is not None and stock_cost_basis > 0 and spot < stock_cost_basis * style.cc_pause_below_cost_ratio:
                    strike = -1.0
                if strike > 0 and shares >= 100:
                    strike = round(strike, 2)
                    expiry = _option_expiry(d, style.dte)
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
        "style": style.key,
    }


def render_metrics(m: dict) -> None:
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("总收益率", f"{m.get('total_return', 0):+.1f}%")
    c2.metric("CAGR", f"{m.get('cagr', 0):+.1f}%")
    c3.metric("Sharpe", f"{m.get('sharpe', 0):.3f}")
    c4.metric("最大回撤", f"{m.get('max_dd', 0):.1f}%")
    c5.metric("胜率", f"{m.get('win_rate', 0):.0f}%")
    c6.metric("交易笔数", str(m.get("n_trades", 0)))
    st.caption(
        f"初始 ${INITIAL_CAPITAL:,.0f} | 佣金 ${COMMISSION:.2f}/笔 | 空闲现金 {CASH_RATE:.0%} 年化 | "
        f"期权定价：chain={m.get('chain_quotes',0)} 次，BS fallback={m.get('bs_quotes',0)} 次"
    )


def fig_to_png_bytes(fig: plt.Figure) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
    buf.seek(0)
    return buf.read()


def build_chart_figures(res: dict) -> dict[str, plt.Figure]:
    eq = res["equity"]
    bh = res["benchmark_bh"]
    monthly = res["monthly_pct"]
    dd = (eq / eq.cummax() - 1.0) * 100
    fig1, ax1 = plt.subplots(figsize=(10, 3.8))
    ax1.plot(eq.index, eq.values, lw=1.8, color="#34d399", label="Wheel Equity")
    ax1.plot(bh.index, bh.values, lw=1.2, ls="--", color="#60a5fa", label=f"{res.get('signal_ticker', 'Benchmark')} B&H")
    ax1.set_title("Portfolio Equity Curve")
    ax1.set_ylabel("Portfolio ($)")
    ax1.legend(loc="upper left")
    apply_dark_style(fig1, ax1)

    fig2, ax2 = plt.subplots(figsize=(7, 3.0))
    ax2.plot(dd.index, dd.values, lw=1.4, color="#fb7185")
    ax2.fill_between(dd.index, dd.values, 0, color="#fb7185", alpha=0.12)
    ax2.set_title("Drawdown Curve (%)")
    apply_dark_style(fig2, ax2)

    fig3, ax3 = plt.subplots(figsize=(7, 3.0))
    colors = ["#34d399" if x >= 0 else "#fb7185" for x in monthly.values]
    ax3.bar(monthly.index.strftime("%Y-%m"), monthly.values, color=colors, alpha=0.85)
    ax3.set_title("Monthly Return (%)")
    ax3.tick_params(axis="x", rotation=45)
    apply_dark_style(fig3, ax3)

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
    return {"equity": fig1, "drawdown": fig2, "monthly": fig3, "indicators": fig4}


def render_charts(res: dict) -> None:
    figs = build_chart_figures(res)
    st.pyplot(figs["equity"], use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        st.pyplot(figs["drawdown"], use_container_width=True)
    with c2:
        st.pyplot(figs["monthly"], use_container_width=True)
    st.pyplot(figs["indicators"], use_container_width=True)
    for fig in figs.values():
        plt.close(fig)


def render_trade_table(rows: list[dict]) -> None:
    if not rows:
        st.info("当前区间没有生成有效交易。")
        return
    df = pd.DataFrame(rows).rename(
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


def run_style_tab(style: StyleProfile, state_prefix: str, default_underlying: str, default_signal: str) -> None:
    st.markdown(f"#### {style.label}风格")
    c0, c1, c2, c3 = st.columns(4)
    with c0:
        underlying = st.text_input("标的Ticker", value=default_underlying, key=f"{state_prefix}_{style.key}_ul").upper().strip()
    with c1:
        signal = st.text_input("信号Ticker", value=default_signal, key=f"{state_prefix}_{style.key}_sig").upper().strip()
    with c2:
        end_d = st.date_input("结束日期", value=date.today(), key=f"{state_prefix}_{style.key}_end")
    with c3:
        start_d = st.date_input("开始日期", value=date.today() - timedelta(days=365), key=f"{state_prefix}_{style.key}_start")

    p1, p2, p3, p4, p5, p6 = st.columns(6)
    with p1:
        put_otm_pct = st.number_input("Put OTM(%)", min_value=0.0, max_value=30.0, value=style.put_otm * 100, step=0.5, key=f"{state_prefix}_{style.key}_put_otm")
    with p2:
        call_otm_pct = st.number_input("Call OTM(%)", min_value=0.0, max_value=30.0, value=style.call_otm * 100, step=0.5, key=f"{state_prefix}_{style.key}_call_otm")
    with p3:
        put_tp_pct = st.number_input("Put止盈(%)", min_value=1.0, max_value=95.0, value=style.put_tp * 100, step=1.0, key=f"{state_prefix}_{style.key}_put_tp")
    with p4:
        call_tp_pct = st.number_input("Call止盈(%)", min_value=1.0, max_value=99.0, value=style.call_tp * 100, step=1.0, key=f"{state_prefix}_{style.key}_call_tp")
    with p5:
        put_sl_pct = st.number_input("Put止损倍数(%)", min_value=0.0, max_value=1000.0, value=(style.put_sl or 0.0) * 100, step=50.0, key=f"{state_prefix}_{style.key}_put_sl")
    with p6:
        call_sl_pct = st.number_input("Call止损倍数(%)", min_value=0.0, max_value=1000.0, value=0.0, step=50.0, key=f"{state_prefix}_{style.key}_call_sl")

    if st.button(f"运行{style.label}回测", key=f"run_{state_prefix}_{style.key}", use_container_width=True):
        with st.spinner("正在获取 yfinance 数据并回测..."):
            try:
                res = simulate_wheel(
                    style=style,
                    start=start_d,
                    end=end_d,
                    underlying_ticker=underlying,
                    signal_ticker=signal,
                    put_tp=put_tp_pct / 100.0,
                    call_tp=call_tp_pct / 100.0,
                    put_sl=(put_sl_pct / 100.0) if put_sl_pct > 0 else None,
                    call_sl=(call_sl_pct / 100.0) if call_sl_pct > 0 else None,
                    put_otm=put_otm_pct / 100.0,
                    call_otm=call_otm_pct / 100.0,
                )
                payload = serialize_result(res)
                latest_key = f"{state_prefix}_{style.key}_latest"
                cache.save(latest_key, {"style": style.key, "result_payload": payload, "start": str(start_d), "end": str(end_d)})
                chart_pngs: dict[str, bytes] = {}
                figs = build_chart_figures(res)
                for name, fig in figs.items():
                    chart_pngs[name] = fig_to_png_bytes(fig)
                    plt.close(fig)
                cache.save_report(
                    {
                        "style": style.key,
                        "ticker": underlying,
                        "run_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "meta": {
                            "start": str(start_d),
                            "end": str(end_d),
                            "style": style.key,
                            "underlying_ticker": underlying,
                            "signal_ticker": signal,
                            "put_otm_pct": put_otm_pct,
                            "call_otm_pct": call_otm_pct,
                            "put_tp_pct": put_tp_pct,
                            "call_tp_pct": call_tp_pct,
                            "put_sl_pct": put_sl_pct if put_sl_pct > 0 else None,
                            "call_sl_pct": call_sl_pct if call_sl_pct > 0 else None,
                            "engine_version": ENGINE_VERSION,
                            "rule_version": RULE_VERSION,
                        },
                        "series": {
                            "equity": payload["equity"],
                            "benchmark_bh": payload["benchmark_bh"],
                            "monthly_pct": payload["monthly_pct"],
                            "ivr": payload["ivr"],
                            "rsi": payload["rsi"],
                            "underlying": payload["underlying"],
                            "signal": payload["signal"],
                        },
                        "trades": payload["trade_log"],
                        "metrics": payload["metrics"],
                    },
                    chart_pngs=chart_pngs,
                )
                st.session_state[f"{state_prefix}_{style.key}_result"] = res
                st.success("回测完成。")
            except Exception as exc:
                st.error(f"回测失败：{exc}")

    res = st.session_state.get(f"{state_prefix}_{style.key}_result")
    if res is None:
        cached = cache.load(f"{state_prefix}_{style.key}_latest")
        if cached:
            res = deserialize_result(cached.get("result_payload"))
            if res is not None:
                st.session_state[f"{state_prefix}_{style.key}_result"] = res
                st.caption(f"已加载上次{style.label}结果：{cached.get('start')} → {cached.get('end')}")
    if res is None:
        st.info("点击上方按钮开始回测。")
        return
    render_metrics(res["metrics"])
    render_charts(res)
    st.markdown("#### 交易记录")
    render_trade_table(res["trade_log"])


def render_history_tab(state_prefix: str) -> None:
    st.markdown("#### 历史报告")
    c1, c2 = st.columns(2)
    with c1:
        style_filter = st.selectbox("风格筛选", ["全部", "aggressive", "neutral", "conservative"], key=f"{state_prefix}_hist_style")
    with c2:
        ticker_filter = st.text_input("Ticker筛选(可空)", value="", key=f"{state_prefix}_hist_ticker").strip().upper()
    reports = cache.list_reports(style=None if style_filter == "全部" else style_filter, ticker=ticker_filter or None)
    if not reports:
        st.info("暂无历史报告。")
        return
    options = [f"{r.get('run_at')} | {r.get('style')} | {r.get('ticker')} | {r.get('start')}~{r.get('end')}" for r in reports]
    choice = st.radio("选择历史报告", options, index=0, key=f"{state_prefix}_hist_radio")
    rid = reports[options.index(choice)]["report_id"]
    data = cache.load_report(rid)
    if not data:
        st.warning("读取历史报告失败。")
        return
    series = data.get("series", {})
    res = deserialize_result(
        {
            "equity": series.get("equity", []),
            "benchmark_bh": series.get("benchmark_bh", []),
            "monthly_pct": series.get("monthly_pct", []),
            "ivr": series.get("ivr", []),
            "rsi": series.get("rsi", []),
            "underlying": series.get("underlying", []),
            "signal": series.get("signal", []),
            "metrics": data.get("metrics", {}),
            "trade_log": data.get("trades", []),
            "underlying_ticker": data.get("meta", {}).get("underlying_ticker", ""),
            "signal_ticker": data.get("meta", {}).get("signal_ticker", ""),
            "style": data.get("meta", {}).get("style", data.get("style", "")),
        }
    )
    if not res:
        st.warning("历史报告序列解析失败。")
        return
    st.caption(f"Report ID: {rid}")
    chart_map = data.get("charts", {}) if isinstance(data, dict) else {}
    if chart_map:
        with st.expander("查看历史快照图（本地PNG）", expanded=False):
            c1, c2 = st.columns(2)
            if chart_map.get("equity"):
                c1.image(chart_map["equity"], caption="equity.png")
            if chart_map.get("drawdown"):
                c2.image(chart_map["drawdown"], caption="drawdown.png")
            c3, c4 = st.columns(2)
            if chart_map.get("monthly"):
                c3.image(chart_map["monthly"], caption="monthly.png")
            if chart_map.get("indicators"):
                c4.image(chart_map["indicators"], caption="indicators.png")
    render_metrics(res["metrics"])
    render_charts(res)
    st.markdown("#### 交易记录")
    render_trade_table(res["trade_log"])

