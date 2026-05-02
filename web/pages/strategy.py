from __future__ import annotations

import streamlit as st

from web.services.dashboard_llm import build_llm_config
from web.services.strategy_api_service import answer_lrs_question, get_lrs_doc_markdown
from web.pages.lrs.strategy_macro import render_tab_macro
from web.pages.lrs.strategy_base_signal import render_tab_base_signal
from web.pages.lrs.strategy_validation import render_tab_validation
from web.pages.lrs.strategy_execution import render_tab_execution
from web.pages.lrs.strategy_risk import render_tab_risk
from web.pages.backtesting import render_backtest_tab
from web.pages.wheel.strategy_wheel import render_wheel_page

def _llm_answer(prompt: str) -> str:
    cfg = build_llm_config(st.session_state.get("last_params"))
    return answer_lrs_question(prompt, cfg)


def _render_lrs_dashboard() -> None:
    st.subheader("LRS TQQQ 策略仪表盘")
    st.caption('基于“当日开仓决策”框架。当前采用子 Tab 架构，优先展示宏观层。')

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("策略模式", "LRS")
    k2.metric("标的", "TQQQ")
    k3.metric("决策状态", "待运行")
    k4.metric("建议仓位", "N/A")

    st.markdown("---")

    tab_macro, tab_base, tab_valid, tab_risk, tab_exec = st.tabs([
        "1) 宏观经济分析（优先）",
        "2) 基础信号",
        "3) 入场模式判断",
        "4) 风控层（资金分配）",
        "5) 执行层（下单）",
    ])

    with tab_macro:
        render_tab_macro()

    with tab_base:
        render_tab_base_signal()

    with tab_valid:
        render_tab_validation()

    with tab_risk:
        render_tab_risk()

    with tab_exec:
        render_tab_execution()


def render_strategy() -> None:
    st.header("策略")
    sub_strategy = str(st.session_state.get("strategy_sub_menu", "LRS TQQQ策略"))
    st.caption(f"当前子策略：{sub_strategy}")

    if sub_strategy == "Wheel策略":
        render_wheel_page()
        return
    if sub_strategy != "LRS TQQQ策略":
        st.info("未找到该子策略。")
        return

    tab_doc, tab_dashboard, tab_backtest = st.tabs(["策略文档", "策略仪表盘", "策略回测"])

    with tab_doc:
        left, right = st.columns([1.45, 1], gap="large")
        with left:
            st.markdown(get_lrs_doc_markdown())
        with right:
            st.markdown("#### LRS 策略问答（LLM）")
            st.caption("可针对 LRS 思路、参数与风控方案进行讨论。")
            chat_key = "lrs_chat_messages"
            if chat_key not in st.session_state:
                st.session_state[chat_key] = [{
                    "role": "assistant",
                    "content": "你好，我是 LRS 策略助手。你可以问我：如何定义入场条件、如何控制回撤、如何设计回测指标。",
                }]
            for msg in st.session_state[chat_key]:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
            user_text = st.chat_input("输入你的策略问题...", key="lrs_chat_input")
            if user_text:
                st.session_state[chat_key].append({"role": "user", "content": user_text})
                with st.chat_message("user"):
                    st.markdown(user_text)
                with st.chat_message("assistant"):
                    with st.spinner("正在生成回答..."):
                        try:
                            answer = _llm_answer(
                                f"你是量化策略研究助手。请围绕 LRS TQQQ 策略回答问题，要求中文、结构化、可执行。\n\n用户问题：{user_text}"
                            ).strip()
                            if not answer:
                                answer = "我暂时没有生成有效内容，请换个问法再试。"
                        except Exception as exc:
                            answer = f"LLM 调用失败：{exc}"
                        st.markdown(answer)
                st.session_state[chat_key].append({"role": "assistant", "content": answer})

    with tab_dashboard:
        _render_lrs_dashboard()

    with tab_backtest:
        render_backtest_tab()
