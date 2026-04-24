from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import streamlit as st

from web.pages.lrs.strategy_shared import close_series, render_step_module
from web.pages.lrs import strategy_cache as _sc

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

_CONDITION_NAMES = ["收益率曲线", "10Y-3M 利差", "实际利率", "美元趋势", "短端利率斜率"]


# ─────────────────────────────────────────────────────────────────────────────
# Dark-theme chart helper
# ─────────────────────────────────────────────────────────────────────────────

_DARK_BG    = "#0f172a"
_AXES_BG    = "#1e293b"
_GRID_COLOR = "#334155"
_TEXT_COLOR = "#cbd5e1"
_TICK_COLOR = "#94a3b8"


def _apply_dark_style(fig: plt.Figure, *axes) -> None:
    fig.patch.set_facecolor(_DARK_BG)
    for ax in axes:
        ax.set_facecolor(_AXES_BG)
        ax.tick_params(colors=_TICK_COLOR)
        ax.xaxis.label.set_color(_TEXT_COLOR)
        ax.yaxis.label.set_color(_TEXT_COLOR)
        ax.title.set_color(_TEXT_COLOR)
        for spine in ax.spines.values():
            spine.set_edgecolor(_GRID_COLOR)
        ax.grid(color=_GRID_COLOR, linestyle="--", linewidth=0.5, alpha=0.7)
        if ax.get_legend() is not None:
            ax.get_legend().get_frame().set_facecolor(_AXES_BG)
            ax.get_legend().get_frame().set_edgecolor(_GRID_COLOR)
            for text in ax.get_legend().get_texts():
                text.set_color(_TEXT_COLOR)


# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# Auto-score card (always visible, reads session_state)
# ─────────────────────────────────────────────────────────────────────────────

def _render_auto_score_card(
    *,
    condition: str,
    score_key: str,
    metric_key: str,
    verdict_key: str,
) -> None:
    score   = st.session_state.get(score_key)
    metric  = st.session_state.get(metric_key, "")
    verdict = st.session_state.get(verdict_key, "")

    if score is None:
        border, bg, badge_c, badge, txt_c = (
            "rgba(148,163,184,.35)", "rgba(15,23,42,.18)", "#94a3b8", "待测试", "#64748b"
        )
    elif score >= 1.0:
        border, bg, badge_c, badge, txt_c = (
            "rgba(74,222,128,.5)", "rgba(22,101,52,.2)", "#4ade80", "1分 ✅", "#e2e8f0"
        )
    elif score > 0:
        border, bg, badge_c, badge, txt_c = (
            "rgba(251,191,36,.5)", "rgba(120,85,0,.2)", "#fbbf24", "0.5分 ⚠️", "#fbbf24"
        )
    else:
        border, bg, badge_c, badge, txt_c = (
            "rgba(248,113,113,.5)", "rgba(127,29,29,.2)", "#f87171", "0分 ❌", "#e2e8f0"
        )

    m_html = (
        f'<div style="font-size:12px;color:#94a3b8;margin-top:6px;line-height:1.6;">{metric}</div>'
        if metric else ""
    )
    v_html = (
        f'<div style="font-size:12px;color:{txt_c};margin-top:4px;font-style:italic;">{verdict}</div>'
        if verdict else ""
    )
    st.markdown(
        f"""<div style="border:1px solid {border};border-radius:10px;padding:11px 15px;
            background:{bg};margin:10px 0 4px 0;">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <span style="font-size:13px;font-weight:600;color:{txt_c};">自动判断：{condition}</span>
    <span style="font-size:13px;font-weight:700;color:{badge_c};">{badge}</span>
  </div>
  {m_html}{v_html}
</div>""",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Data fetching
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_macro_data() -> dict:
    tickers = ["^IRX", "^FVX", "^TNX", "^TYX", "DX-Y.NYB", "TIP"]
    macro = pd.concat([close_series(t, period="10y") for t in tickers], axis=1).dropna()
    qqq   = close_series("QQQ", period="10y").reindex(macro.index).dropna()
    macro = macro.reindex(qqq.index)

    # T10YIE from FRED (10-year breakeven inflation rate for real rate calculation)
    t10yie: pd.Series | None = None
    try:
        import pandas_datareader as pdr  # type: ignore
        start_str = macro.index.min().strftime("%Y-%m-%d")
        raw = pdr.DataReader("T10YIE", "fred", start=start_str)
        s = raw["T10YIE"].reindex(macro.index, method="ffill")
        if not s.dropna().empty:
            t10yie = s
    except Exception:
        pass  # Fallback to TIP direction proxy in scoring

    spread_10y_3m = macro["^TNX"] - macro["^IRX"]
    spread_30y_5y = macro["^TYX"] - macro["^FVX"]

    return dict(
        macro=macro,
        qqq=qqq,
        t10yie=t10yie,
        spread_10y_3m=spread_10y_3m,
        spread_30y_5y=spread_30y_5y,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Scoring
# ─────────────────────────────────────────────────────────────────────────────

def _score_all_conditions(data: dict) -> None:
    macro         = data["macro"]
    spread_10y_3m = data["spread_10y_3m"]
    t10yie        = data["t10yie"]

    # Condition 1: Yield curve ordered + no inversion past 40 trading days
    last    = macro[["^IRX", "^FVX", "^TNX", "^TYX"]].dropna().iloc[-1]
    ordered = bool(last["^IRX"] < last["^FVX"] < last["^TNX"] < last["^TYX"])
    inv40   = bool((macro["^IRX"] >= macro["^TNX"]).tail(40).any())
    score_1 = 1.0 if (ordered and not inv40) else 0.0
    metric_1 = (
        f"IRX={last['^IRX']:.2f}%   "
        f"FVX={last['^FVX']:.2f}%   "
        f"TNX={last['^TNX']:.2f}%   "
        f"TYX={last['^TYX']:.2f}%"
    )
    if score_1 == 1:
        verdict_1 = "正常排列（IRX<FVX<TNX<TYX），过去40日无倒挂"
    elif ordered:
        verdict_1 = "当前有序，但近40日内曾出现倒挂，保守记0分"
    else:
        verdict_1 = "当前收益率曲线不符合正向斜率排列"

    # Condition 2: 10Y-3M spread positive and widening
    spr      = spread_10y_3m.dropna()
    spr_now  = float(spr.iloc[-1]  * 100)
    spr_63d  = float(spr.iloc[-64] * 100) if len(spr) > 64 else spr_now
    widening = spr_now > spr_63d
    if spr_now > 0 and widening:
        score_2 = 1.0
    elif spr_now > 0:
        score_2 = 0.5
    else:
        score_2 = 0.0
    metric_2 = (
        f"当前利差={spr_now:.1f}bp，"
        f"3个月前={spr_63d:.1f}bp，"
        f"{'走阔 ↑' if widening else '收窄 ↓'}"
    )
    if score_2 == 1:
        verdict_2 = "正利差且持续走阔，衰退风险低"
    elif score_2 == 0.5:
        verdict_2 = "正利差但收窄，保守处理记0分"
    else:
        verdict_2 = "利差为负（倒挂状态），衰退预警"

    # Condition 3: Real rate < 1.5% (TNX - T10YIE, or TIP proxy)
    tnx_now = float(macro["^TNX"].dropna().iloc[-1])
    if t10yie is not None and len(t10yie.dropna()) > 0:
        t10yie_now = float(t10yie.dropna().iloc[-1])
        real_rate  = tnx_now - t10yie_now
        score_3    = 1.0 if real_rate < 1.5 else 0.0
        metric_3   = (
            f"TNX={tnx_now:.2f}%  T10YIE={t10yie_now:.2f}%  "
            f"实际利率≈{real_rate:.2f}%"
        )
        verdict_3 = (
            f"实际利率 {real_rate:.2f}% < 1.5%，估值压力较小" if score_3 == 1
            else f"实际利率 {real_rate:.2f}% >= 1.5%，对纳指估值有压制"
        )
    else:
        tip_3m  = float(macro["TIP"].pct_change(63).dropna().iloc[-1])
        score_3 = 1.0 if tip_3m > 0 else 0.0
        metric_3 = f"TIP 3个月变化={tip_3m*100:.1f}%（FRED不可用，TIP方向代理）"
        verdict_3 = (
            "TIP上涨->实际利率趋降，估值压力缓解" if score_3 == 1
            else "TIP下跌->实际利率趋升，估值受压"
        )

    # Condition 4: DXY < 104, downtrend, no double tightening
    dxy_s    = macro["DX-Y.NYB"].dropna()
    tnx_s    = macro["^TNX"].dropna()
    dxy_now  = float(dxy_s.iloc[-1])
    dxy_63d  = float(dxy_s.iloc[-64]) if len(dxy_s) > 64 else dxy_now
    tnx_63d  = float(tnx_s.iloc[-64]) if len(tnx_s) > 64 else float(tnx_s.iloc[-1])
    dxy_up   = dxy_now > dxy_63d
    tnx_up3m = float(tnx_s.iloc[-1]) > tnx_63d
    double_tight = dxy_up and tnx_up3m
    if double_tight:
        score_4 = 0.0
    elif dxy_now < 104 or not dxy_up:
        score_4 = 1.0
    else:
        score_4 = 0.0
    metric_4 = (
        f"DXY={dxy_now:.2f}（3个月{'上涨' if dxy_up else '下跌'}），"
        f"TNX 3个月{'上涨' if tnx_up3m else '下跌'}"
    )
    if double_tight:
        verdict_4 = "DXY与TNX同步上升——双收紧，最差情形！"
    elif score_4 == 1:
        verdict_4 = "DXY低于104或下行，全球流动性环境较友好"
    else:
        verdict_4 = "DXY高于104且上行，流动性偏紧"

    # Condition 5: IRX 6-month slope <= +0.25%
    irx_s     = macro["^IRX"].dropna()
    irx_now   = float(irx_s.iloc[-1])
    irx_127d  = float(irx_s.iloc[-127]) if len(irx_s) > 127 else irx_now
    irx_delta = irx_now - irx_127d
    score_5   = 1.0 if irx_delta <= 0.25 else 0.0
    if irx_delta < -0.25:
        irx_state = "下行（市场定价降息）"
    elif irx_delta <= 0.25:
        irx_state = "横盘（暂停/数据依赖）"
    else:
        irx_state = "上行（市场定价加息）"
    metric_5  = (
        f"IRX当前={irx_now:.2f}%，"
        f"6个月前={irx_127d:.2f}%，"
        f"变化={irx_delta:+.2f}%"
    )
    verdict_5 = f"利率周期：{irx_state}" + ("" if score_5 == 1 else " -- 不利TQQQ持仓")

    # Store all in session_state
    for i, (s, m, v) in enumerate(
        zip(
            [score_1, score_2, score_3, score_4, score_5],
            [metric_1, metric_2, metric_3, metric_4, metric_5],
            [verdict_1, verdict_2, verdict_3, verdict_4, verdict_5],
        ),
        start=1,
    ):
        st.session_state[f"macro_score_{i}"]   = s
        st.session_state[f"macro_metric_{i}"]  = m
        st.session_state[f"macro_verdict_{i}"] = v
    st.session_state["macro_tested"] = True


# ─────────────────────────────────────────────────────────────────────────────
# Chart containers
# ─────────────────────────────────────────────────────────────────────────────

def _chart_container_12(
    macro: pd.DataFrame | None,
    spread_10y_3m: pd.Series | None,
    spread_30y_5y: pd.Series | None,
    draw: bool,
    save_key: str | None = None,
) -> None:
    with st.container(border=True):
        st.markdown("### 条件 1 & 2 — 收益率曲线形态")

        # ── Chart 1 ──────────────────────────────────────────────────────────
        st.markdown("**图 1：四条收益率的排列顺序（正斜率判断）**")
        st.markdown(
            "**判断标准：**\n"
            "- **通过（1分）**：当前四条利率同时满足 `IRX < FVX < TNX < TYX`（短端最低、长端最高），"
            "且过去 **40个交易日** 内 IRX 从未高于 TNX（无短暂倒挂）。\n"
            "- **不通过（0分）**：任意利率出现倒挂；或当前排列虽正常，但近40日内曾发生过倒挂——"
            "从倒挂恢复后至少需要稳定 **40 天** 才可记1分。\n"
            "- **参考区间（历史均值）**：正常牛市环境下 TYX-IRX 利差约 200~300bp；"
            "平坦化警戒线 < 50bp；倒挂信号 < 0bp。"
        )
        if draw and macro is not None:
            label_map = {
                "^IRX": "IRX (3M)", "^FVX": "FVX (5Y)",
                "^TNX": "TNX (10Y)", "^TYX": "TYX (30Y)",
            }
            rates = (
                macro[["^IRX", "^FVX", "^TNX", "^TYX"]]
                .reset_index()
                .melt("Date", var_name="Tenor", value_name="Yield")
            )
            rates["Tenor"] = rates["Tenor"].map(label_map)
            fig1, ax1 = plt.subplots(figsize=(10, 4))
            sns.lineplot(
                data=rates, x="Date", y="Yield", hue="Tenor",
                ax=ax1, linewidth=1.6,
                palette=["#38bdf8", "#818cf8", "#a78bfa", "#f472b6"],
            )
            ax1.set_title("Yield Curve — 10-Year History", fontsize=12, fontweight="bold")
            ax1.set_xlabel("Date")
            ax1.set_ylabel("Yield (%)")
            ax1.legend(title="Tenor", loc="upper left", ncol=2, fontsize=9)
            _apply_dark_style(fig1, ax1)
            plt.tight_layout()
            if save_key:
                _sc.save_figure(f"{save_key}_1", fig1)
            st.pyplot(fig1, clear_figure=True)
        elif save_key and _sc.figure_path(f"{save_key}_1"):
            st.image(_sc.figure_path(f"{save_key}_1"), use_container_width=True)
        else:
            st.info("点击「更新判断」生成图 1。")

        _render_auto_score_card(
            condition="条件1：收益率曲线正斜率（IRX<FVX<TNX<TYX，40日无倒挂）",
            score_key="macro_score_1",
            metric_key="macro_metric_1",
            verdict_key="macro_verdict_1",
        )

        st.markdown("---")

        # ── Chart 2 ──────────────────────────────────────────────────────────
        st.markdown("**图 2：10Y-3M 利差走势（衰退预警指标）**")
        st.markdown(
            "**判断标准：**\n"
            "- **1分**：TNX - IRX > 0（正利差）且过去 **3个月（约63个交易日）** 利差持续走阔"
            "（当前值 > 3个月前值）。\n"
            "- **0.5分（保守记0）**：TNX - IRX > 0 但利差在收窄，曲线正在平坦化，需谨慎。\n"
            "- **0分**：TNX - IRX <= 0（利差倒挂），历史上每次倒挂结束后平均 **12~18个月** 内出现衰退；"
            "倒挂结束后的恢复初期往往是风险最高的阶段，不能只看「现在是正的」。\n"
            "- **图中红色区域**：历史上所有倒挂时期（利差 < 0bp）。"
        )
        if draw and spread_10y_3m is not None and spread_30y_5y is not None:
            spr10 = spread_10y_3m * 100
            spr30 = spread_30y_5y * 100
            fig2, ax2 = plt.subplots(figsize=(10, 4))
            ax2.plot(spr10.index, spr10.values, color="#38bdf8", linewidth=1.6,
                     label="TNX - IRX  (10Y minus 3M)")
            ax2.plot(spr30.index, spr30.values, color="#a78bfa", linewidth=1.3,
                     linestyle="--", label="TYX - FVX  (30Y minus 5Y)")
            ax2.axhline(0, linestyle="--", color="#64748b", linewidth=1.0, label="Zero line")
            ax2.fill_between(
                spr10.index, spr10.values, 0,
                where=(spr10.values < 0),
                color="#f87171", alpha=0.25, label="Inversion zone",
            )
            ax2.set_title(
                "Yield Curve Spread — Inversion History (bp)",
                fontsize=12, fontweight="bold",
            )
            ax2.set_xlabel("Date")
            ax2.set_ylabel("Spread (bp)")
            ax2.legend(fontsize=9)
            _apply_dark_style(fig2, ax2)
            plt.tight_layout()
            if save_key:
                _sc.save_figure(f"{save_key}_2", fig2)
            st.pyplot(fig2, clear_figure=True)
        elif save_key and _sc.figure_path(f"{save_key}_2"):
            st.image(_sc.figure_path(f"{save_key}_2"), use_container_width=True)
        else:
            st.info("点击「更新判断」生成图 2。")

        _render_auto_score_card(
            condition="条件2：10Y-3M 利差为正且走阔",
            score_key="macro_score_2",
            metric_key="macro_metric_2",
            verdict_key="macro_verdict_2",
        )


def _chart_container_3(
    macro: pd.DataFrame | None,
    t10yie: pd.Series | None,
    draw: bool,
    save_key: str | None = None,
) -> None:
    with st.container(border=True):
        st.markdown("### 条件 3 — 实际利率水平")
        st.markdown("**图 3：实际利率计算（TNX 名义利率 vs TIP 通胀保护债券）**")
        st.markdown(
            "**判断标准：**\n"
            "- **主方法（推荐，FRED T10YIE 可用时）**：实际利率 = TNX - T10YIE（10年期盈亏平衡通胀率）\n"
            "  - 实际利率 **< 1.5%** -> **1分**（科技股估值承压较小）\n"
            "  - 实际利率 **1.5% ~ 2.0%** -> **0分**（边界区，保守处理）\n"
            "  - 实际利率 **> 2.0%** 且持续上升 -> **0分**"
            "（参考：2022年实际利率从 -1% 飙至 +2.5%，QQQ 最大回撤超过35%）\n"
            "- **备选方法（FRED 不可用时）**：TIP 过去3个月价格方向代理\n"
            "  - TIP 3个月价格 **上涨** -> 实际利率趋降 -> **1分**\n"
            "  - TIP 3个月价格 **下跌** -> 实际利率趋升 -> **0分**\n"
            "- **图中紫色虚点线**（FRED可用时）：TNX - T10YIE 实际利率曲线；"
            "**白色虚线**：1.5% 阈值线。"
        )
        if draw and macro is not None:
            tnx_s = macro["^TNX"].dropna()
            tip_s = macro["TIP"].dropna()
            shared_idx = tnx_s.index.intersection(tip_s.index)
            tnx_s = tnx_s.reindex(shared_idx)
            tip_s = tip_s.reindex(shared_idx)

            fig3, ax3 = plt.subplots(figsize=(10, 4))
            color_tnx = "#38bdf8"
            color_tip = "#f59e0b"
            ax3.plot(tnx_s.index, tnx_s.values, color=color_tnx, linewidth=1.6,
                     label="TNX — Nominal Rate (left, %)")
            ax3.set_ylabel("Rate (%)", fontsize=10)
            ax3b = ax3.twinx()
            ax3b.plot(tip_s.index, tip_s.values, color=color_tip, linewidth=1.3,
                      linestyle="--", label="TIP Price (right, $)")
            ax3b.set_ylabel("TIP Price ($)", fontsize=10)
            ax3.axhline(1.5, linestyle=":", color="#e2e8f0", linewidth=1.0,
                        label="1.5% threshold")
            if t10yie is not None and not t10yie.dropna().empty:
                t10yie_aligned = t10yie.reindex(shared_idx, method="ffill")
                real_rate_s = tnx_s - t10yie_aligned
                ax3.plot(real_rate_s.index, real_rate_s.values,
                         color="#a78bfa", linewidth=1.4, linestyle="-.",
                         label="Real Rate = TNX - T10YIE")
            ax3.legend(loc="upper left", fontsize=8)
            ax3b.legend(loc="upper right", fontsize=8)
            ax3.set_title(
                "Real Interest Rate Analysis (TNX vs TIP / T10YIE)",
                fontsize=12, fontweight="bold",
            )
            ax3.set_xlabel("Date")
            _apply_dark_style(fig3, ax3, ax3b)
            plt.tight_layout()
            if save_key:
                _sc.save_figure(save_key, fig3)
            st.pyplot(fig3, clear_figure=True)
        elif save_key and _sc.figure_path(save_key):
            st.image(_sc.figure_path(save_key), use_container_width=True)
        else:
            st.info("点击「更新判断」生成图 3。")

        _render_auto_score_card(
            condition="条件3：实际利率低于1.5%（TNX-T10YIE 或 TIP 方向代理）",
            score_key="macro_score_3",
            metric_key="macro_metric_3",
            verdict_key="macro_verdict_3",
        )


def _chart_container_4(macro: pd.DataFrame | None, draw: bool, save_key: str | None = None) -> None:
    with st.container(border=True):
        st.markdown("### 条件 4 — 美元指数与双收紧风险")
        st.markdown("**图 4：DXY（美元指数）与 TNX（长端利率）双轴对比**")
        st.markdown(
            "**判断标准：**\n"
            "- **1分**：DXY 当前 **< 104**，或过去 **3个月（约63个交易日）** 方向向下/横盘，"
            "且不存在双收紧。\n"
            "- **0分（最差情形）**：DXY 与 TNX **同步上升**（双收紧）——美元走强同时利率上行，"
            "全球流动性双向收紧，对纳指最为不利。\n"
            "- **0分**：DXY > 104 且方向向上（强美元压缩跨国科技股利润）。\n"
            "- **DXY 绝对值参考**：< 100 = 宽松，100~104 = 中性，104~108 = 偏紧，> 108 = 显著收紧。\n"
            "- **图中红色虚线**：DXY = 104 阈值线。"
        )
        if draw and macro is not None:
            dxy_s = macro["DX-Y.NYB"].dropna()
            tnx_s = macro["^TNX"].dropna()
            shared = dxy_s.index.intersection(tnx_s.index)
            dxy_s = dxy_s.reindex(shared)
            tnx_s = tnx_s.reindex(shared)

            fig4, ax4 = plt.subplots(figsize=(10, 4))
            color_tnx = "#38bdf8"
            color_dxy = "#f59e0b"
            ax4.plot(tnx_s.index, tnx_s.values, color=color_tnx, linewidth=1.6,
                     label="TNX — 10Y Rate (left, %)")
            ax4.set_ylabel("TNX (%)", fontsize=10)
            ax4b = ax4.twinx()
            ax4b.plot(dxy_s.index, dxy_s.values, color=color_dxy, linewidth=1.6,
                      label="DXY — Dollar Index (right)")
            ax4b.axhline(104, linestyle="--", color="#f87171", linewidth=1.3,
                         label="DXY = 104 threshold")
            ax4b.set_ylabel("DXY", fontsize=10)
            ax4.legend(loc="upper left", fontsize=8)
            ax4b.legend(loc="upper right", fontsize=8)
            ax4.set_title(
                "Dollar Index (DXY) vs Long-term Rate (TNX) — Dual Tightening Check",
                fontsize=12, fontweight="bold",
            )
            ax4.set_xlabel("Date")
            _apply_dark_style(fig4, ax4, ax4b)
            plt.tight_layout()
            if save_key:
                _sc.save_figure(save_key, fig4)
            st.pyplot(fig4, clear_figure=True)
        elif save_key and _sc.figure_path(save_key):
            st.image(_sc.figure_path(save_key), use_container_width=True)
        else:
            st.info("点击「更新判断」生成图 4。")

        _render_auto_score_card(
            condition="条件4：DXY 走势友好（低于104或下行，无双收紧）",
            score_key="macro_score_4",
            metric_key="macro_metric_4",
            verdict_key="macro_verdict_4",
        )


def _chart_container_5(
    macro: pd.DataFrame | None,
    qqq: pd.Series | None,
    draw: bool,
    save_key: str | None = None,
) -> None:
    with st.container(border=True):
        st.markdown("### 条件 5 — 利率周期方向（IRX 6个月斜率）")
        st.markdown("**图 5a：IRX 近24个月走势与6个月趋势线**")
        st.markdown(
            "**判断标准（基于 IRX 过去6个月变化量）：**\n"
            "- **1分**：IRX 过去 **6个月（约127个交易日）** 变化 **<= +0.25%**"
            "（包含下行/降息 和 横盘/暂停两种情形）。\n"
            "- **0分**：IRX 过去6个月上升 **> +0.25%**，市场在定价加息周期延续。\n"
            "- **细分说明**：\n"
            "  - IRX 变化 **< -0.25%** -> 明确降息周期，对TQQQ最有利。\n"
            "  - IRX 变化 **-0.25% ~ +0.25%** -> 暂停/数据依赖，中性。\n"
            "  - IRX 变化 **> +0.5%** -> 明确加息信号，对TQQQ极度不利。\n"
            "- **辅助参考（须手动确认）**：FOMC 声明中出现"
            '"further tightening" -> 无论 IRX 如何，记0分。'
        )
        st.markdown("**图 5b：宏观坐标定位图（IRX / TNX / DXY / QQQ 近24个月标准化）**")
        st.markdown(
            "用途：将四条线标准化到同一起点（=100），直观比较近两年的相对走势，"
            "帮助定位当前宏观环境与历史上哪个阶段最相似"
            "（例：2019年降息周期 / 2022年快速加息 / 2024年软着陆）。"
        )
        if draw and macro is not None and qqq is not None:
            irx_full = macro["^IRX"].dropna()
            irx_24m  = irx_full.tail(24 * 21)

            fig5, (ax5a, ax5b) = plt.subplots(2, 1, figsize=(10, 9), sharex=False)

            # Upper: IRX 24-month + trend line
            x_num  = np.arange(len(irx_24m))
            coeffs = np.polyfit(x_num, irx_24m.values, 1)
            trend  = np.polyval(coeffs, x_num)
            ax5a.plot(irx_24m.index, irx_24m.values, color="#38bdf8", linewidth=1.6,
                      label="IRX (3-Month T-Bill)")
            ax5a.plot(
                irx_24m.index, trend,
                color="#f87171", linewidth=1.3, linestyle="--",
                label=f"6M Trend  (slope={coeffs[0] * 126:+.3f}%/6M)",
            )
            irx_now  = float(irx_full.iloc[-1])
            irx_127d = float(irx_full.iloc[-127]) if len(irx_full) > 127 else irx_now
            delta    = irx_now - irx_127d
            try:
                ax5a.annotate(
                    f"6M change: {delta:+.2f}%",
                    xy=(irx_24m.index[-1], irx_24m.iloc[-1]),
                    xytext=(-110, 18), textcoords="offset points",
                    fontsize=9, color="#e2e8f0",
                    arrowprops=dict(arrowstyle="->", color="#94a3b8"),
                )
            except Exception:
                pass
            ax5a.set_title("IRX — Last 24 Months with 6M Trend Line", fontsize=11, fontweight="bold")
            ax5a.set_xlabel("Date")
            ax5a.set_ylabel("IRX (%)")
            ax5a.legend(fontsize=8)

            # Lower: 4-line standardized
            tail_df = pd.DataFrame({
                "IRX": macro["^IRX"],
                "TNX": macro["^TNX"],
                "DXY": macro["DX-Y.NYB"],
                "QQQ": qqq,
            }).dropna().tail(24 * 21)
            norm    = (tail_df / tail_df.iloc[0]) * 100
            norm_df = norm.reset_index().melt("Date", var_name="Series", value_name="Value")
            sns.lineplot(
                data=norm_df, x="Date", y="Value",
                hue="Series", ax=ax5b, linewidth=1.4,
                palette=["#38bdf8", "#818cf8", "#f59e0b", "#4ade80"],
            )
            ax5b.axhline(100, linestyle="--", color="#64748b", linewidth=0.8)
            ax5b.set_title(
                "Macro Positioning Map — IRX / TNX / DXY / QQQ  (Last 24M, Base = 100)",
                fontsize=11, fontweight="bold",
            )
            ax5b.set_xlabel("Date")
            ax5b.set_ylabel("Normalized (base = 100)")
            ax5b.legend(title="Series", fontsize=8)

            _apply_dark_style(fig5, ax5a, ax5b)
            plt.tight_layout(h_pad=3)
            if save_key:
                _sc.save_figure(save_key, fig5)
            st.pyplot(fig5, clear_figure=True)
        elif save_key and _sc.figure_path(save_key):
            st.image(_sc.figure_path(save_key), use_container_width=True)
        else:
            st.info("点击「更新判断」生成图 5a 和图 5b。")

        _render_auto_score_card(
            condition="条件5：IRX 斜率（利率周期方向 — 降息或暂停）",
            score_key="macro_score_5",
            metric_key="macro_metric_5",
            verdict_key="macro_verdict_5",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Main orchestrators
# ─────────────────────────────────────────────────────────────────────────────

def _render_macro_5_charts_preview() -> None:
    _chart_container_12(None, None, None, draw=False, save_key="macro_chart12")
    _chart_container_3(None, None, draw=False, save_key="macro_chart3")
    _chart_container_4(None, draw=False, save_key="macro_chart4")
    _chart_container_5(None, None, draw=False, save_key="macro_chart5")


def _render_macro_5_charts_full() -> tuple[bool, str]:
    data = _fetch_macro_data()
    _score_all_conditions(data)

    macro         = data["macro"]
    qqq           = data["qqq"]
    t10yie        = data["t10yie"]
    spread_10y_3m = data["spread_10y_3m"]
    spread_30y_5y = data["spread_30y_5y"]

    _chart_container_12(macro, spread_10y_3m, spread_30y_5y, draw=True, save_key="macro_chart12")
    _chart_container_3(macro, t10yie, draw=True, save_key="macro_chart3")
    _chart_container_4(macro, draw=True, save_key="macro_chart4")
    _chart_container_5(macro, qqq, draw=True, save_key="macro_chart5")

    total  = sum(st.session_state.get(f"macro_score_{i}", 0) or 0 for i in range(1, 6))
    passed = total >= 3
    return passed, f"宏观综合得分：{total:.1f}/5"


# ─────────────────────────────────────────────────────────────────────────────
# Conclusion Scorecard — always visible
# ─────────────────────────────────────────────────────────────────────────────

def _render_macro_conclusion_only() -> None:
    tested = bool(st.session_state.get("macro_tested", False))
    scores = [st.session_state.get(f"macro_score_{i}") for i in range(1, 6)]

    with st.container(border=True):
        st.markdown("#### 宏观评分汇总")

        cols = st.columns(5)
        _pill_styles: dict = {
            None: ("rgba(148,163,184,.3)", "rgba(15,23,42,.2)", "#64748b", "—"),
            1.0:  ("rgba(74,222,128,.5)",  "rgba(22,101,52,.25)", "#4ade80", "1分"),
            0.5:  ("rgba(251,191,36,.5)",  "rgba(120,85,0,.25)",  "#fbbf24", "0.5分"),
            0.0:  ("rgba(248,113,113,.5)", "rgba(127,29,29,.25)", "#f87171", "0分"),
        }
        for col, name, score in zip(cols, _CONDITION_NAMES, scores):
            key_s = score if score in _pill_styles else 0.0
            border_c, bg_c, txt_c, label = _pill_styles[key_s]
            with col:
                st.markdown(
                    f'<div style="text-align:center;border:1px solid {border_c};border-radius:10px;'
                    f'padding:10px 4px;background:{bg_c};margin-bottom:4px;">'
                    f'<div style="font-size:11px;color:#94a3b8;margin-bottom:4px;">{name}</div>'
                    f'<div style="font-size:18px;font-weight:700;color:{txt_c};">{label}</div>'
                    f"</div>",
                    unsafe_allow_html=True,
                )

        st.markdown("<br>", unsafe_allow_html=True)

        if not tested:
            st.info('点击上方"测试"按钮后显示宏观综合评分与 Regime 判断。')
            return

        valid_scores = [s for s in scores if s is not None]
        total   = sum(valid_scores)
        max_pos = len(valid_scores)
        pct     = total / max_pos if max_pos > 0 else 0.0

        col_s, col_b = st.columns([1, 3])
        with col_s:
            st.metric("综合得分", f"{total:.1f} / {max_pos}")
        with col_b:
            st.progress(float(pct))

        if total >= 4:
            regime   = "Risk-On  顺风"
            regime_c = "#4ade80"
            border_c = "rgba(74,222,128,.5)"
            bg_c     = "rgba(22,101,52,.3)"
            pos_text = "建议仓位：80%~100% TQQQ"
        elif total >= 2:
            regime   = "Neutral  中性"
            regime_c = "#fbbf24"
            border_c = "rgba(251,191,36,.5)"
            bg_c     = "rgba(120,85,0,.25)"
            pos_text = "建议仓位：50%~70% TQQQ"
        else:
            regime   = "Risk-Off  逆风"
            regime_c = "#f87171"
            border_c = "rgba(248,113,113,.5)"
            bg_c     = "rgba(127,29,29,.3)"
            pos_text = "建议仓位：清仓或低于20% TQQQ"

        st.markdown(
            f'<div style="margin-top:12px;padding:14px 16px;border-radius:10px;'
            f'background:{bg_c};border:1px solid {border_c};">'
            f'<div style="font-size:16px;font-weight:700;color:{regime_c};">当前宏观状态：{regime}</div>'
            f'<div style="font-size:13px;color:#e2e8f0;margin-top:6px;">{pos_text}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Macro filter (simple, used by risk tab)
# ─────────────────────────────────────────────────────────────────────────────

def render_macro_filter_chart() -> tuple[bool, str]:
    tickers = ["^IRX", "^FVX", "^TNX", "^TYX", "DX-Y.NYB", "TIP"]
    macro = pd.concat([close_series(t, period="1y") for t in tickers], axis=1).dropna()
    chg5  = macro.pct_change(5)
    detail = pd.DataFrame(index=macro.index)
    detail["IRX"]   = np.where(chg5["^IRX"]     <= 0, 1, -1)
    detail["TNX"]   = np.where(chg5["^TNX"]     <= 0, 1, -1)
    detail["TIP"]   = np.where(chg5["TIP"]      >= 0, 1, -1)
    detail["DXY"]   = np.where(chg5["DX-Y.NYB"] <= 0, 1, -1)
    curve = macro["^TYX"] - macro["^FVX"]
    detail["Curve"] = np.where(curve.diff(5)    >= 0, 1, -1)
    detail["macro_score"] = detail.sum(axis=1)

    label_map = {"^IRX": "IRX", "^FVX": "FVX", "^TNX": "TNX", "^TYX": "TYX"}
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    rates = (
        macro[["^IRX", "^FVX", "^TNX", "^TYX"]]
        .reset_index()
        .melt("Date", var_name="Tenor", value_name="Yield")
    )
    rates["Tenor"] = rates["Tenor"].map(label_map)
    sns.lineplot(data=rates, x="Date", y="Yield", hue="Tenor", ax=axes[0], linewidth=1.6)
    axes[0].set_title("Rate Cluster (1Y)", fontsize=11)
    axes[0].set_ylabel("Yield (%)")
    axes[0].legend(loc="upper left", ncol=2)
    sns.lineplot(
        data=detail.reset_index(), x="Date", y="macro_score",
        ax=axes[1], color="#10b981", linewidth=1.8,
    )
    axes[1].axhline(0, color="#64748b", linestyle="--")
    axes[1].set_title("Macro Score (5-day momentum)", fontsize=11)
    axes[1].set_xlabel("Date")
    axes[1].set_ylabel("Score")
    _apply_dark_style(fig, axes[0], axes[1])
    plt.tight_layout()
    st.pyplot(fig, clear_figure=True)

    score  = float(detail.dropna().iloc[-1]["macro_score"])
    passed = score >= -1
    return passed, f"宏观过滤结论：{'通过' if passed else '未通过'}（macro_score={score:.0f}）"


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def render_tab_macro() -> None:
    from web.pages.lrs import strategy_cache as _sc

    # ── Load cache and restore session_state ──────────────────────────────────
    _macro_cache = _sc.load("macro")
    if not st.session_state.get("macro_tested") and _macro_cache:
        if _macro_cache.get("macro_tested"):
            st.session_state["macro_tested"] = True
            for _i in range(1, 6):
                _k = f"macro_score_{_i}"
                if _k in _macro_cache:
                    st.session_state[_k] = _macro_cache[_k]
            if "macro_score_total" in _macro_cache:
                st.session_state["macro_score_total"] = _macro_cache["macro_score_total"]

    # ── Last-update caption ───────────────────────────────────────────────────
    if _macro_cache:
        st.caption(
            f"上次更新：{_macro_cache.get('_updated_at', '—')}  |  "
            "点击「更新判断」获取最新宏观数据"
        )
    else:
        st.caption("暂无历史数据，请点击「更新判断」开始分析")

    render_step_module(
        step_idx=3,
        title="检查清单",
        summary="点击「更新判断」，自动获取最新宏观数据并生成 5 张核心图表，每张图下方会显示自动评分卡。",
        criteria_table_md="",
        chart_titles=[],
        test_button_key="lrs_step3_test",
        status_key="lrs_step3_test_passed",
        on_test=_render_macro_5_charts_full,
        preview_renderer=_render_macro_5_charts_preview,
    )

    _render_macro_conclusion_only()

    # ── Save macro scores to cache after test ────────────────────────────────
    if st.session_state.get("macro_tested"):
        _scores = {f"macro_score_{_i}": st.session_state.get(f"macro_score_{_i}")
                   for _i in range(1, 6)}
        _valid  = [s for s in _scores.values() if s is not None]
        _total  = sum(_valid)
        st.session_state["macro_score_total"] = _total
        _sc.save("macro", {**_scores, "macro_score_total": _total, "macro_tested": True})
