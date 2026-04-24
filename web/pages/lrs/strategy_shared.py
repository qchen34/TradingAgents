from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
import yfinance as yf

# ─── Dark theme constants (shared across all strategy sub-tabs) ──────────────
_DARK_BG    = "#0f172a"
_AXES_BG    = "#1e293b"
_GRID_COLOR = "#334155"
_TEXT_COLOR = "#cbd5e1"
_TICK_COLOR = "#94a3b8"


def apply_dark_style(fig: plt.Figure, *axes) -> None:
    """Apply consistent dark background theme to a matplotlib figure."""
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
        legend = ax.get_legend()
        if legend is not None:
            legend.get_frame().set_facecolor(_AXES_BG)
            legend.get_frame().set_edgecolor(_GRID_COLOR)
            for t in legend.get_texts():
                t.set_color(_TEXT_COLOR)


def render_score_card(
    *,
    label: str,
    score,          # 1 = pass, 0 = fail, -1 = caution, None = pending
    metric: str = "",
    verdict: str = "",
) -> None:
    """Render an auto-scoring card with pass / fail / caution / pending styling."""
    if score is None:
        border, bg, txt_c, badge_c, badge = "#475569", "#1e293b", "#94a3b8", "#94a3b8", "待测试"
    elif score == 1:
        border, bg, txt_c, badge_c, badge = "#22c55e", "#14532d", "#86efac", "#22c55e", "PASS ✓"
    elif score == -1:
        border, bg, txt_c, badge_c, badge = "#f59e0b", "#78350f", "#fcd34d", "#f59e0b", "CAUTION ⚠"
    else:
        border, bg, txt_c, badge_c, badge = "#ef4444", "#7f1d1d", "#fca5a5", "#ef4444", "FAIL ✗"

    m_html = (
        f'<div style="font-size:12px;color:#94a3b8;margin-top:6px;">{metric}</div>'
        if metric else ""
    )
    v_html = (
        f'<div style="font-size:12px;color:{txt_c};margin-top:4px;font-style:italic;">{verdict}</div>'
        if verdict else ""
    )
    st.markdown(
        f'<div style="border:1px solid {border};border-radius:10px;padding:11px 15px;'
        f'background:{bg}33;margin:8px 0;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<span style="font-size:13px;font-weight:600;color:{txt_c};">{label}</span>'
        f'<span style="font-size:13px;font-weight:700;color:{badge_c};">{badge}</span>'
        f'</div>{m_html}{v_html}</div>',
        unsafe_allow_html=True,
    )


# ─── Data helpers ────────────────────────────────────────────────────────────

def close_series(ticker: str, period: str = "2y") -> pd.Series:
    """Download closing prices for a ticker and return as a named Series."""
    df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f"未获取到 {ticker} 数据")
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    s = close.dropna()
    s.name = ticker
    return s


# ─── Step module wrapper ─────────────────────────────────────────────────────

def render_step_module(
    step_idx: int,
    title: str,
    summary: str,
    criteria_table_md: str,
    chart_titles: list[str],
    test_button_key: str,
    status_key: str,
    on_test=None,
    preview_renderer=None,
) -> None:
    passed = bool(st.session_state.get(status_key, False))
    title_suffix = " ✅" if passed else ""
    ran_key = f"{test_button_key}_ran"
    conclusion_key = f"{test_button_key}_conclusion"

    with st.container(border=True):
        left, right = st.columns([6, 1])
        with left:
            st.markdown(f"### {title}{title_suffix}")
        with right:
            run_test = st.button("🔄 更新判断", key=test_button_key, use_container_width=True)

        st.caption(summary)
        st.markdown(criteria_table_md)

        if run_test:
            st.session_state[ran_key] = True

        should_render = bool(st.session_state.get(ran_key, False))

        if preview_renderer is not None and not should_render:
            preview_renderer()

        if should_render and on_test is not None:
            with st.spinner("正在获取数据并绘图..."):
                try:
                    passed_now, conclusion = on_test()
                    st.session_state[status_key] = bool(passed_now)
                    st.session_state[conclusion_key] = str(conclusion)
                    if passed_now:
                        st.success(f"分析完成 ✅：{conclusion}")
                    else:
                        st.warning(f"分析完成（未通过）：{conclusion}")
                except Exception as exc:
                    st.session_state[status_key] = False
                    st.error(f"测试失败：{exc}")
        else:
            if not (preview_renderer is not None and not should_render):
                st.info('点击右上角「更新判断」按钮，开始拉取数据并生成本步骤图表。')
