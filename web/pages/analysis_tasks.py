from __future__ import annotations

import traceback
from pathlib import Path

import streamlit as st

from web.config_ui import format_params_summary, render_config_form
from web.pages.report_history import render_report_history
from web.report_viewer import render_report_focused
from web.run_pipeline import STEP_LABELS_ZH, run_analysis

SUBVIEW_RUN = "运行与进度"
SUBVIEW_HISTORY = "报告历史"


def _normalize_analysis_subview() -> None:
    legacy = {
        "Run / Progress": SUBVIEW_RUN,
        "Report History": SUBVIEW_HISTORY,
    }
    v = st.session_state.get("analysis_subview")
    if v in legacy:
        st.session_state.analysis_subview = legacy[v]


def _render_steps(current_idx: int) -> None:
    lines = []
    for i, name in enumerate(STEP_LABELS_ZH):
        if i < current_idx:
            lines.append(f"✅ {i + 1:02d}. {name}")
        elif i == current_idx:
            lines.append(f"👉 {i + 1:02d}. {name}")
        else:
            lines.append(f"⬜ {i + 1:02d}. {name}")
    st.code("\n".join(lines), language=None)


def _render_stats(stats: dict) -> None:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("LLM 调用次数", int(stats.get("llm_calls", 0)))
    c2.metric("工具调用次数", int(stats.get("tool_calls", 0)))
    c3.metric("输入 Token", int(stats.get("tokens_in", 0)))
    c4.metric("输出 Token", int(stats.get("tokens_out", 0)))


def _render_run_panel() -> None:
    st.subheader("运行与进度")
    running = st.session_state.ui_mode == "running"
    if st.button("新建分析", type="primary"):
        st.session_state.show_config = True
        st.session_state.ui_mode = "configuring"
        st.rerun()
    if st.session_state.last_params and not st.session_state.show_config:
        if st.button("修改参数"):
            st.session_state.show_config = True
            st.session_state.ui_mode = "configuring"
            st.rerun()

    params_live = None
    if st.session_state.show_config:
        params_live = render_config_form(st.container(), disabled=running, key_prefix="task_cfg")
        if st.session_state.get("prefill_ticker"):
            st.caption(f"提示：当前关注的股票代码为 `{st.session_state['prefill_ticker']}`")
    elif st.session_state.last_params:
        st.markdown("<div class='ta-summary'>", unsafe_allow_html=True)
        st.markdown("#### 已选参数")
        st.markdown(
            st.session_state.selected_params_summary or format_params_summary(st.session_state.last_params)
        )
        st.markdown("</div>", unsafe_allow_html=True)

    run_clicked = st.button("开始分析", disabled=running) if st.session_state.show_config else False
    params_for_run = None
    if run_clicked:
        if not params_live or not params_live.get("ticker"):
            st.error("请填写股票代码（Ticker）。")
        elif not params_live.get("selected_analysts"):
            st.error("请至少选择一名分析师维度。")
        else:
            st.session_state.last_params = dict(params_live)
            st.session_state.selected_params_summary = format_params_summary(params_live)
            st.session_state.show_config = False
            params_for_run = dict(params_live)
    if params_for_run:
        st.session_state.ui_mode = "running"
        st.session_state.runtime_stats = {}
        st.session_state.error = ""
        step_box = st.empty()
        stats_box = st.empty()

        def _progress_cb(_msg: str) -> None:
            return

        def _step_cb(info: dict) -> None:
            with step_box.container():
                st.markdown("### 当前步骤")
                _render_steps(int(info.get("index", 0)))

        def _stats_cb(stats: dict) -> None:
            st.session_state.runtime_stats = dict(stats)
            with stats_box.container():
                st.markdown("### Token / 调用统计")
                _render_stats(stats)

        _step_cb({"index": 0})
        _stats_cb({})
        try:
            with st.spinner("分析运行中…"):
                out_state, out_dir = run_analysis(
                    params=params_for_run,
                    progress_cb=_progress_cb,
                    stream_events=True,
                    step_cb=_step_cb,
                    stats_cb=_stats_cb,
                )
                _ = out_state
            st.session_state.latest_run_dir = out_dir
            st.session_state.active_output_dir = out_dir
            st.session_state.ui_mode = "done"
            st.success("分析完成。")
        except Exception:
            st.session_state.ui_mode = "failed"
            st.session_state.error = traceback.format_exc()

    if st.session_state.error:
        st.error(st.session_state.error)
    if st.session_state.active_output_dir and Path(st.session_state.active_output_dir).exists():
        st.subheader("最新报告")
        render_report_focused(st.session_state.active_output_dir)


def render_analysis_tasks() -> None:
    st.header("个股分析")
    _normalize_analysis_subview()
    if "analysis_subview" not in st.session_state:
        st.session_state.analysis_subview = SUBVIEW_RUN
    c1, c2 = st.columns(2)
    with c1:
        if st.button(
            SUBVIEW_RUN,
            key="analysis_sub_run",
            type="primary" if st.session_state.analysis_subview == SUBVIEW_RUN else "secondary",
            use_container_width=True,
        ):
            st.session_state.analysis_subview = SUBVIEW_RUN
            st.rerun()
    with c2:
        if st.button(
            SUBVIEW_HISTORY,
            key="analysis_sub_history",
            type="primary" if st.session_state.analysis_subview == SUBVIEW_HISTORY else "secondary",
            use_container_width=True,
        ):
            st.session_state.analysis_subview = SUBVIEW_HISTORY
            st.rerun()

    if st.session_state.analysis_subview == SUBVIEW_RUN:
        _render_run_panel()
    else:
        render_report_history(default_ticker=st.session_state.get("selected_ticker"))
