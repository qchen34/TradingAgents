"""Step 2 — Signal Verification: QQQ MA200 Crossover.

UX pattern:
  - Page load: show last cached results from data/dashboard/strategy/base_signal.json
  - "更新判断" button: fetch fresh data, compute, save to cache, display
  - Charts: only available after "更新判断" in the current session (button appears if live data exists)
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
import yfinance as yf

from web.pages.lrs import strategy_cache as sc
from web.pages.lrs.strategy_shared import apply_dark_style, render_score_card

_CACHE_KEY = "base_signal"
_SKEY      = "lrs_step2"


# ─── Cached data fetch ───────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def _fetch_qqq_data() -> pd.DataFrame:
    df = yf.download("QQQ", period="2y", auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError("Failed to download QQQ data.")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


# ─── Conditions ──────────────────────────────────────────────────────────────

def _compute_conditions(df: pd.DataFrame) -> dict:
    close  = df["Close"].dropna()
    volume = df["Volume"].dropna()
    ma200  = close.rolling(200).mean()
    ma50   = close.rolling(50).mean()
    vol20  = volume.rolling(20).mean()

    close_val = float(close.iloc[-1])
    ma200_val = float(ma200.iloc[-1])
    ma50_val  = float(ma50.iloc[-1]) if not pd.isna(ma50.iloc[-1]) else None

    a1_pass    = close_val > ma200_val
    a1_metric  = f"QQQ = {close_val:.2f}  |  MA200 = {ma200_val:.2f}"
    a1_verdict = (
        "日收盘价已站上 200 日均线，信号有效。"
        if a1_pass else
        "QQQ 收盘价尚未突破 MA200，信号无效。"
    )

    ma200_clean = ma200.dropna()
    if len(ma200_clean) >= 21:
        spct = (float(ma200_clean.iloc[-1]) - float(ma200_clean.iloc[-21])) / float(ma200_clean.iloc[-21]) * 100
        if spct > 0:
            a2_score, a2_cls, a2_v = 1, "Rising", f"过去 20 个交易日上升 +{spct:.2f}%，斜率向上 — 通过。"
        elif abs(spct) <= 0.5:
            a2_score, a2_cls, a2_v = 1, "Flat", f"过去 20 个交易日持平 {spct:+.2f}%，斜率稳定 — 通过。"
        elif spct > -1.0:
            a2_score, a2_cls, a2_v = -1, "Mildly declining", f"过去 20 日小幅下跌 {spct:+.2f}% — 注意 / 不通过。"
        else:
            a2_score, a2_cls, a2_v = 0, "Declining", f"过去 20 日下跌 {spct:+.2f}%，回撤风险高 — 不通过。"
        a2_metric = f"MA200 变化：过去 20 个交易日 {spct:+.2f}%（{a2_cls}）"
    else:
        a2_score, a2_metric, a2_v = None, "历史数据不足。", "需要至少 221 天数据。"

    above = (close > ma200).dropna()
    consec = 0
    for v in reversed(above.values):
        if v:
            consec += 1
        else:
            break
    a3_pass    = consec >= 3
    a3_metric  = f"连续 {consec} 日收盘站上 MA200（至少需要 3 日）"
    a3_verdict = (
        "连续 3 日以上收盘站上 MA200，突破有效。"
        if a3_pass else
        f"仅 {consec} 日，需连续 3 日以上才确认有效。"
    )

    cross_idx = None
    for i in range(len(above) - 1, 0, -1):
        if above.iloc[i] and not above.iloc[i - 1]:
            cross_idx = above.index[i]
            break

    if cross_idx is not None and cross_idx in volume.index:
        cvol  = float(volume.loc[cross_idx])
        avg20 = float(vol20.loc[cross_idx]) if not pd.isna(vol20.loc[cross_idx]) else None
        b1_pass    = (cvol > avg20) if avg20 else None
        b1_metric  = (f"Breakout vol: {cvol/1e6:.1f}M  |  20d avg: {avg20/1e6:.1f}M  |  Ratio: {cvol/avg20:.2f}x"
                      if avg20 else "N/A")
        b1_verdict = (("成交量高于均值，突破有说服力。" if b1_pass else
                       "成交量低于均值，突破力度偏弱，建议减仓 25%。")
                      if b1_pass is not None else "无法评估 — 未检测到突破信号。")
    else:
        b1_pass, b1_metric, b1_verdict = None, "未检测到看涨突破。", ""

    b2_pass = (close_val > ma50_val) if ma50_val else None
    if ma50_val:
        if b2_pass and ma50_val > ma200_val:
            structure = "价格 > MA50 > MA200 — 黄金交叉区间（强势）"
        elif b2_pass:
            structure = "价格 > MA200，MA50 仍在 MA200 以下 — 尚可"
        else:
            structure = "价格 > MA200 但低于 MA50 — MA50 构成压力位（弱势）"
        b2_metric  = f"QQQ = {close_val:.2f}  |  MA50 = {ma50_val:.2f}  |  MA200 = {ma200_val:.2f}"
        b2_verdict = structure
    else:
        b2_metric, b2_verdict = "MA50 数据不可用。", ""

    days_since = max(0, len(close.loc[cross_idx:]) - 1) if cross_idx is not None else None
    cutoff     = pd.Timestamp.now(tz=above.index.tz) - pd.Timedelta(days=60)
    above60    = above[above.index >= cutoff]
    crossings  = sum(1 for i in range(1, len(above60)) if above60.iloc[i] != above60.iloc[i - 1])
    cross_count = crossings // 2

    return dict(
        close=close, ma200=ma200, ma50=ma50, volume=volume, vol20=vol20,
        a1_pass=a1_pass, a1_metric=a1_metric, a1_verdict=a1_verdict,
        a2_score=a2_score, a2_metric=a2_metric, a2_verdict=a2_v,
        a3_pass=a3_pass, a3_metric=a3_metric, a3_verdict=a3_verdict,
        b1_pass=b1_pass, b1_metric=b1_metric, b1_verdict=b1_verdict,
        b2_pass=b2_pass, b2_metric=b2_metric, b2_verdict=b2_verdict,
        cross_idx=cross_idx,
        days_since=days_since, cross_count=cross_count,
        close_val=close_val, ma200_val=ma200_val, ma50_val=ma50_val,
    )


def _signal_quality_from_data(data: dict, b3: bool) -> str:
    a1_ok = bool(data.get("a1_pass", False))
    a2_ok = data.get("a2_score") == 1
    a3_ok = bool(data.get("a3_pass", False))
    if not (a1_ok and a2_ok and a3_ok):
        return "No Signal"
    b1_ok = bool(data.get("b1_pass", False)) if data.get("b1_pass") is not None else False
    b2_ok = bool(data.get("b2_pass", False)) if data.get("b2_pass") is not None else False
    bp = sum([b1_ok, b2_ok, bool(b3)])
    if bp >= 3:  return "Strong"
    if bp >= 2:  return "Valid"
    return "Weak"


def _to_cache(data: dict, b3: bool, quality: str) -> dict:
    return {
        "close_val":  float(data["close_val"]),
        "ma200_val":  float(data["ma200_val"]),
        "ma50_val":   float(data["ma50_val"]) if data["ma50_val"] else None,
        "a1_pass":    bool(data["a1_pass"]),
        "a1_metric":  data["a1_metric"],
        "a1_verdict": data["a1_verdict"],
        "a2_score":   data["a2_score"],
        "a2_metric":  data["a2_metric"],
        "a2_verdict": data["a2_verdict"],
        "a3_pass":    bool(data["a3_pass"]),
        "a3_metric":  data["a3_metric"],
        "a3_verdict": data["a3_verdict"],
        "b1_pass":    (bool(data["b1_pass"]) if data["b1_pass"] is not None else None),
        "b1_metric":  data["b1_metric"],
        "b1_verdict": data["b1_verdict"],
        "b2_pass":    (bool(data["b2_pass"]) if data["b2_pass"] is not None else None),
        "b2_metric":  data["b2_metric"],
        "b2_verdict": data["b2_verdict"],
        "b3_pass":    b3,
        "days_since": data["days_since"],
        "cross_count": data["cross_count"],
        "cross_idx":  str(data["cross_idx"].date()) if data["cross_idx"] is not None else None,
        "signal_quality": quality,
    }


# ─── Charts (requires pandas Series — only from live data) ───────────────────

def _render_charts(data: dict, save: bool = False) -> None:
    close  = data["close"].tail(400)
    ma200  = data["ma200"].tail(400)
    ma50   = data["ma50"].tail(400)
    volume = data["volume"].tail(400)
    vol20  = data["vol20"].tail(400)
    cross_idx = data.get("cross_idx")

    with st.container(border=True):
        st.markdown("**Chart 1 — QQQ Price vs MA200 + Volume**")
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6), sharex=True,
                                        gridspec_kw={"height_ratios": [3, 1]})
        cv, mv, di = close.values, ma200.values, close.index
        ax1.plot(di, cv, color="#38bdf8", linewidth=1.8, label="QQQ")
        ax1.plot(di, mv, color="#a78bfa", linewidth=1.6, label="MA200")
        ax1.fill_between(di, cv, mv, where=(cv > mv), alpha=0.15, color="#22c55e", label="Above MA200")
        ax1.fill_between(di, cv, mv, where=(cv <= mv), alpha=0.15, color="#ef4444", label="Below MA200")
        if cross_idx is not None:
            ax1.axvline(x=cross_idx, color="#f59e0b", linestyle="--", linewidth=1.2,
                        label=f"Crossover ({cross_idx.date() if hasattr(cross_idx,'date') else cross_idx})")
        ax1.set_title("QQQ vs MA200 (Signal Verification)"); ax1.set_ylabel("Price (USD)")
        ax1.legend(loc="upper left", fontsize=8)
        ax2.bar(volume.index, volume.values, color="#475569", alpha=0.7, width=1.0)
        ax2.plot(vol20.index, vol20.values, color="#f59e0b", linewidth=1.2, label="Vol MA20")
        ax2.set_ylabel("Volume"); ax2.legend(fontsize=8)
        apply_dark_style(fig, ax1, ax2)
        plt.tight_layout()
        if save:
            sc.save_figure("base_signal_chart1", fig)
        st.pyplot(fig, clear_figure=True)

    with st.container(border=True):
        st.markdown("**Chart 2 — Trend Structure: QQQ vs MA50 vs MA200**")
        fig2, ax3 = plt.subplots(figsize=(12, 4))
        ax3.plot(close.index, close.values, color="#38bdf8", linewidth=1.6, label="QQQ")
        ax3.plot(ma50.index, ma50.reindex(close.index).values,
                 color="#34d399", linewidth=1.4, label="MA50")
        ax3.plot(ma200.index, ma200.reindex(close.index).values,
                 color="#a78bfa", linewidth=1.4, label="MA200")
        ax3.set_title("QQQ vs MA50 vs MA200 — Trend Structure")
        ax3.set_ylabel("Price (USD)"); ax3.legend(loc="upper left", fontsize=9)
        apply_dark_style(fig2, ax3)
        plt.tight_layout()
        if save:
            sc.save_figure("base_signal_chart2", fig2)
        st.pyplot(fig2, clear_figure=True)


# ─── Render all sections from data dict ──────────────────────────────────────

def _render_all(data: dict, is_fresh: bool = False) -> None:
    st.markdown("""
| 条件组 | 判定规则 | 影响 |
|---|---|---|
| **A 组**（三选三） | A1: 收盘 > MA200 / A2: MA200 斜率 / A3: 连续 ≥3 日 | 任意失败 → No Signal |
| **B 组**（三选二） | B1: 突破量 / B2: 高于 MA50 / B3: 无重大宏观事件 | 0–1 → Weak；2 → Valid；3 → Strong |
| **C 组**（仅记录） | C1: 距突破天数 / C2: 过去 60 日假突破次数 | 输入 Step 3，不影响此步骤评分 |
""")

    with st.container(border=True):
        st.markdown("#### A 组 — 硬性要求（三项须全部通过，任意一项失败则 No Signal）")
        render_score_card(label="A1 — QQQ 日收盘价 > MA200",
                          score=1 if data["a1_pass"] else 0,
                          metric=data["a1_metric"], verdict=data["a1_verdict"])
        render_score_card(label="A2 — MA200 斜率平稳或向上",
                          score=data["a2_score"],
                          metric=data["a2_metric"], verdict=data["a2_verdict"])
        render_score_card(label="A3 — 连续 3 日以上收盘站上 MA200",
                          score=1 if data["a3_pass"] else 0,
                          metric=data["a3_metric"], verdict=data["a3_verdict"])

    with st.container(border=True):
        st.markdown("#### 图表 — QQQ 价格与趋势结构")
        if is_fresh:
            live = st.session_state.get(f"{_SKEY}_live_data")
            if live is not None:
                _render_charts(live, save=True)
        else:
            img1 = sc.figure_path("base_signal_chart1")
            img2 = sc.figure_path("base_signal_chart2")
            if img1:
                st.image(img1, use_container_width=True)
            if img2:
                st.image(img2, use_container_width=True)
            if not img1 and not img2:
                st.info("点击「更新判断」生成图表。")

    with st.container(border=True):
        st.markdown("#### B 组 — 质量过滤（三项中 2/3 通过为 Valid，3/3 为 Strong）")
        render_score_card(label="B1 — 突破日成交量 > 20 日均量",
                          score=(1 if data["b1_pass"] else 0) if data["b1_pass"] is not None else None,
                          metric=data["b1_metric"], verdict=data["b1_verdict"])
        render_score_card(label="B2 — QQQ 收盘价高于 MA50",
                          score=(1 if data["b2_pass"] else 0) if data["b2_pass"] is not None else None,
                          metric=data["b2_metric"], verdict=data["b2_verdict"])

        if "lrs_step2_b3_pass" not in st.session_state:
            st.session_state["lrs_step2_b3_pass"] = bool(data.get("b3_pass", False))
        b3 = st.checkbox(
            "B3 — 未来 5 个交易日无重大宏观事件（FOMC / CPI / NFP / 大型科技股财报）",
            key="lrs_step2_b3_pass",
        )
        st.caption("需手动确认。请查看 Investing.com → Economic Calendar → High Impact。")
        render_score_card(label="B3 — 未来 5 日无高影响宏观事件",
                          score=1 if b3 else 0, metric="手动确认",
                          verdict=("已确认 — 未来 5 天无高影响事件。"
                                   if b3 else "未确认 — 存在重大事件风险。"))

    with st.container(border=True):
        st.markdown("#### C 组 — 背景参考（不影响评分，仅输入 Step 3）")
        c1 = data.get("days_since")
        c2 = data.get("cross_count", 0)
        col1, col2 = st.columns(2)
        with col1:
            st.metric("C1 — 距突破日天数", f"{c1} 天" if c1 is not None else "N/A")
            if c1 is not None:
                if c1 <= 7:    st.caption("最新突破（1–7天）：倾向直接买入。")
                elif c1 <= 20: st.caption("中等距离（8–20天）：Step 3 评估价格距离。")
                else:          st.caption("延伸（20天以上）：可能采用分批买入模式。")
        with col2:
            st.metric("C2 — 过去 60 日 MA200 假突破次数", str(c2))
            if c2 == 0:    st.caption("趋势干净，可信度高。")
            elif c2 <= 2:  st.caption("略有震荡，谨慎推进。")
            else:          st.caption("频繁假突破，建议减仓。")

        st.session_state["lrs_c1_days_since_cross"] = c1
        st.session_state["lrs_c2_false_crosses"]    = c2
        cross_idx = data.get("cross_idx")
        st.session_state["lrs_step2_cross_idx"] = str(cross_idx) if cross_idx else None

    b3 = bool(st.session_state.get("lrs_step2_b3_pass", False))
    quality = _signal_quality_from_data(data, b3)
    st.session_state["lrs_step2_signal_quality"] = quality

    _STYLE = {
        "No Signal": ("#ef4444", "#7f1d1d"),
        "Weak":      ("#f59e0b", "#78350f"),
        "Valid":     ("#38bdf8", "#0c4a6e"),
        "Strong":    ("#22c55e", "#14532d"),
    }
    _DESC = {
        "No Signal": "Group A 未全部通过。停止，返回监控。",
        "Weak":      "Group A 全通，但 Group B 仅 0–1 项通过。可继续但减仓 25%。",
        "Valid":     "Group A 全通，Group B 2 项通过。按正常仓位执行 Step 3。",
        "Strong":    "Group A 全通，Group B 全部通过。信号具有最高可信度。",
    }
    color, bg = _STYLE.get(quality, ("#94a3b8", "#1e293b"))
    st.markdown(
        f'<div style="border:2px solid {color};border-radius:12px;padding:16px 22px;'
        f'background:{bg}33;margin:20px 0 4px 0;text-align:center;">'
        f'<div style="font-size:20px;font-weight:700;color:{color};">Step 2 结果：{quality}</div>'
        f'<div style="font-size:13px;color:#94a3b8;margin-top:6px;">{_DESC.get(quality,"")}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ─── Tab entry point ─────────────────────────────────────────────────────────

def render_tab_base_signal() -> None:
    st.markdown("### Step 2 — 信号验证（QQQ 穿越 MA200）")

    cached = sc.load(_CACHE_KEY)

    col1, col2 = st.columns([4, 1])
    with col1:
        if cached:
            st.caption(f"上次更新：{cached.get('_updated_at', '—')}  |  点击「更新判断」获取最新数据")
        else:
            st.caption("暂无历史数据，请点击「更新判断」开始分析")
    with col2:
        update = st.button("🔄 更新判断", key=f"{_SKEY}_update",
                           type="primary", use_container_width=True)

    if update:
        st.session_state.pop(f"{_SKEY}_chart_ran", None)
        try:
            with st.spinner("正在获取 QQQ 数据…"):
                _fetch_qqq_data.clear()
                df   = _fetch_qqq_data()
                data = _compute_conditions(df)
        except Exception as exc:
            st.error(f"数据获取失败：{exc}")
            return
        b3      = bool(st.session_state.get("lrs_step2_b3_pass", False))
        quality = _signal_quality_from_data(data, b3)
        sc.save(_CACHE_KEY, _to_cache(data, b3, quality))
        st.session_state[f"{_SKEY}_live_data"] = data
        st.success(f"数据已更新 — Step 2 Result: **{quality}**")

    live = st.session_state.get(f"{_SKEY}_live_data")
    if live is not None:
        display_data = live
        is_fresh     = True
    elif cached:
        display_data = cached
        is_fresh     = False
        st.session_state["lrs_step2_signal_quality"] = cached.get("signal_quality", "")
    else:
        st.info("点击「更新判断」开始分析。")
        return

    _render_all(display_data, is_fresh=is_fresh)
