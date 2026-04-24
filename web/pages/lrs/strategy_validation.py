"""Step 3 — Entry Mode Decision: Price Distance Assessment.

UX pattern:
  - Page load: show last cached results
  - "更新判断" button: fetch fresh data, compute, save, display
  - Chart: only after "更新判断" in current session
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
import yfinance as yf

from web.pages.lrs import strategy_cache as sc
from web.pages.lrs.strategy_shared import apply_dark_style, render_score_card

_CACHE_KEY = "validation"
_SKEY      = "lrs_step3"


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    tqqq = yf.download("TQQQ", period="6mo", auto_adjust=True, progress=False)
    qqq  = yf.download("QQQ",  period="2y",  auto_adjust=True, progress=False)
    for df in (tqqq, qqq):
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
    return tqqq, qqq


def _find_crossover(qqq_df: pd.DataFrame):
    close = qqq_df["Close"].dropna()
    ma200 = close.rolling(200).mean()
    above = (close > ma200).dropna()
    for i in range(len(above) - 1, 0, -1):
        if above.iloc[i] and not above.iloc[i - 1]:
            return above.index[i]
    return None


def _entry_mode(distance_pct: float, macro_score: float) -> tuple[str, str, str]:
    if macro_score >= 5:   threshold = 8.0
    elif macro_score >= 3: threshold = 6.0
    elif macro_score >= 2: threshold = 4.0
    else:
        return ("HOLD", "不入场",
                f"宏观评分 {macro_score:.0f}/5 过低，请返回 Step 1。")
    if distance_pct < 0:
        return ("Reassess", "返回 Step 2",
                "TQQQ 低于突破日价格 — 请重新确认 QQQ 是否仍在 MA200 之上。")
    if distance_pct <= 4.0:
        return ("Direct Buy", "2/3 直接买入 + 1/3 Wheel 保证金",
                f"距离 {distance_pct:.1f}% — 最佳入场，安全边际最大。")
    if distance_pct <= threshold:
        return ("Direct Buy", "2/3 直接买入 + 1/3 Wheel 保证金",
                f"距离 {distance_pct:.1f}% — 突破较新，直接买入合适。")
    if distance_pct <= 15.0:
        return ("Split", "1/3 直接买入 + 1/3 Sell Put + 1/3 预留",
                f"距离 {distance_pct:.1f}% — TQQQ 已有一定涨幅，分批入场降低追高风险。")
    return ("Split（强烈建议）", "1/3 直接买入 + 1/3 Sell Put + 1/3 预留",
            f"距离 {distance_pct:.1f}% — 已大幅上涨，历史上回调频率较高。")


def _to_cache(cross_idx, cross_price, current_price, distance_pct,
              mode, mode_detail, rationale, macro_score) -> dict:
    return {
        "cross_idx":     str(cross_idx.date()) if cross_idx is not None else None,
        "cross_price":   float(cross_price) if cross_price is not None else None,
        "current_price": float(current_price),
        "distance_pct":  float(distance_pct),
        "entry_mode":    mode,
        "mode_detail":   mode_detail,
        "rationale":     rationale,
        "macro_score":   float(macro_score),
    }


def _render_distance_chart(tqqq_close, cross_idx, cross_price, current_price, save: bool = False) -> None:
    with st.container(border=True):
        st.markdown("**图表 — TQQQ 价格与突破基准距离**")
        fig, ax = plt.subplots(figsize=(12, 5))
        t90 = tqqq_close.tail(90)
        ax.plot(t90.index, t90.values, color="#38bdf8", linewidth=1.8, label="TQQQ Close")
        if cross_idx is not None and cross_price is not None:
            ax.axvline(x=cross_idx, color="#f59e0b", linestyle="--", linewidth=1.3,
                       label=f"Crossover ({cross_idx.date()})")
            ax.axhline(y=cross_price, color="#a78bfa", linestyle="--", linewidth=1.2,
                       label=f"Cross price ${cross_price:.2f}")
            ax.axhline(y=current_price, color="#22c55e", linestyle=":", linewidth=1.2,
                       label=f"Current ${current_price:.2f}")
            fc = "#22c55e" if current_price >= cross_price else "#ef4444"
            ax.fill_between(t90.index, cross_price, current_price, alpha=0.12, color=fc)
        ax.set_title("TQQQ — Distance from MA200 Crossover Day"); ax.set_ylabel("Price (USD)")
        ax.legend(loc="upper left", fontsize=9)
        apply_dark_style(fig, ax)
        plt.tight_layout()
        if save:
            sc.save_figure("validation_chart", fig)
        st.pyplot(fig, clear_figure=True)


def _render_all(data: dict, is_fresh: bool = False) -> None:
    cross_price   = data.get("cross_price")
    current_price = data.get("current_price", 0.0)
    distance_pct  = data.get("distance_pct", 0.0)
    cross_idx     = data.get("cross_idx")
    macro_score   = float(data.get("macro_score", 3))
    mode          = data.get("entry_mode", "N/A")
    mode_detail   = data.get("mode_detail", "")
    rationale     = data.get("rationale", "")

    with st.container(border=True):
        st.markdown("#### 3.1 — 价格距离计算")
        st.caption("公式：Distance % = (TQQQ 当前价 - TQQQ 突破当日收盘价) / 突破当日收盘价 x 100")

        if cross_price is not None:
            col1, col2, col3 = st.columns(3)
            col1.metric("TQQQ 突破当日收盘价", f"${cross_price:.2f}",
                        help=f"QQQ 突破日期：{cross_idx}")
            col2.metric("TQQQ 当前价格", f"${current_price:.2f}")
            col3.metric("距突破涨幅", f"{distance_pct:+.1f}%",
                        delta=f"{distance_pct:+.1f}%")
            d_score = 1 if distance_pct <= 8 else (-1 if distance_pct <= 15 else 0)
            render_score_card(
                label="距离评估",
                score=d_score,
                metric=f"涨幅 = {distance_pct:+.1f}%  |  突破日：{cross_idx}  |  突破价：${cross_price:.2f}  |  当前价：${current_price:.2f}",
                verdict=("突破时间较近 — 直接买入条件有利。"
                         if distance_pct <= 8 else
                         "已大幅上涨 — 建议使用分批入场模式。"),
            )
            st.session_state["lrs_step3_distance_pct"]  = distance_pct
            st.session_state["lrs_step3_cross_price"]   = cross_price
            st.session_state["lrs_step3_current_price"] = current_price
        else:
            st.warning("未检测到 MA200 看涨突破，请先完成 Step 2 分析。")
            distance_pct = 0.0

        if is_fresh:
            live = st.session_state.get(f"{_SKEY}_live_data")
            if live is not None:
                _render_distance_chart(live["tqqq_close"], live["cross_idx"],
                                       cross_price, current_price, save=True)
        else:
            img = sc.figure_path("validation_chart")
            if img:
                st.image(img, use_container_width=True)
            else:
                st.info("点击「更新判断」生成图表。")

    with st.container(border=True):
        st.markdown("#### 3.2 — 入场模式判断")
        st.caption(f"宏观评分（来自宏观经济分析 tab）：**{macro_score:.0f} / 5**")
        st.markdown("""
| Distance | Macro >=5 | Macro 3-4 | Macro 2 | Entry Mode |
|---|---|---|---|---|
| 0% – 4% | Direct Buy | Direct Buy | Direct Buy | Optimal |
| 4% – 8% | Direct Buy | Direct Buy | **Split** | Still good |
| 8% – 15% | **Split** | **Split** | **Split** | Partial buy + Sell Put |
| 15%+ | **Split** | **Split** | **Split** | Strongly recommended |
""")
        _MODE_SCORE = {"Direct Buy": 1, "Split": -1,
                       "Split (strongly recommended)": -1, "Reassess": 0, "HOLD": 0}
        render_score_card(label=f"入场模式：{mode}", score=_MODE_SCORE.get(mode, -1),
                          metric=mode_detail, verdict=rationale)
        st.session_state["lrs_step3_entry_mode"] = mode

    with st.container(border=True):
        st.markdown("#### Step 3 输出记录")
        cp_str = f"${cross_price:.2f}" if cross_price else "N/A"
        st.markdown(f"""
| Field | Value |
|---|---|
| TQQQ 突破当日收盘价 | **{cp_str}** |
| TQQQ 当前价格 | **${current_price:.2f}** |
| 距突破涨幅 | **{distance_pct:+.1f}%** |
| 宏观评分（来自 Step 1） | **{macro_score:.0f} / 5** |
| 入场模式 | **{mode}** |
| 资金分配 | **{mode_detail}** |
""")
        st.caption("以上结果已存入 session_state，Step 4 将自动读取。")


def render_tab_validation() -> None:
    st.markdown("### Step 3 — 入场模式判断（价格距离评估）")

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
            with st.spinner("正在获取 TQQQ / QQQ 数据…"):
                _fetch_data.clear()
                tqqq_df, qqq_df = _fetch_data()
        except Exception as exc:
            st.error(f"数据获取失败：{exc}")
            return

        tqqq_close = tqqq_df["Close"].dropna() if not tqqq_df.empty else pd.Series(dtype=float)
        if tqqq_close.empty:
            st.error("TQQQ 数据下载失败（yfinance 返回空数据），请稍后重试。")
            return
        current_price = float(tqqq_close.iloc[-1])
        qqq_close_chk = qqq_df["Close"].dropna() if not qqq_df.empty else pd.Series(dtype=float)
        if qqq_close_chk.empty:
            st.error("QQQ 数据下载失败（yfinance 返回空数据），请稍后重试。")
            return
        cross_idx     = _find_crossover(qqq_df)
        cross_price   = None
        if cross_idx is not None:
            nearest = tqqq_close.index[tqqq_close.index >= cross_idx]
            if len(nearest) > 0:
                cross_price = float(tqqq_close.loc[nearest[0]])

        distance_pct = ((current_price - cross_price) / cross_price * 100
                        if cross_price is not None else 0.0)
        macro_score  = float(st.session_state.get("macro_score_total", 3))
        mode, mode_detail, rationale = _entry_mode(distance_pct, macro_score)

        sc.save(_CACHE_KEY, _to_cache(cross_idx, cross_price, current_price,
                                       distance_pct, mode, mode_detail, rationale, macro_score))
        st.session_state[f"{_SKEY}_live_data"] = {
            "tqqq_close": tqqq_close, "cross_idx": cross_idx,
        }
        st.success(f"数据已更新 — Entry Mode: **{mode}**")

    live = st.session_state.get(f"{_SKEY}_live_data")
    if live is not None:
        display_data = sc.load(_CACHE_KEY) or {}
        is_fresh     = True
    elif cached:
        display_data = cached
        is_fresh     = False
        st.session_state["lrs_step3_entry_mode"]    = cached.get("entry_mode", "")
        st.session_state["lrs_step3_distance_pct"]  = cached.get("distance_pct")
        st.session_state["lrs_step3_current_price"] = cached.get("current_price")
    else:
        st.info("点击「更新判断」开始分析。")
        return

    _render_all(display_data, is_fresh=is_fresh)
