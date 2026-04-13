import datetime as dt
from typing import Any, Dict, List, Optional

import streamlit as st

from tradingagents.llm_clients.model_catalog import MODEL_OPTIONS

OUTPUT_LANGS = [
    "English",
    "Chinese",
    "Japanese",
    "Korean",
    "Hindi",
    "Spanish",
    "Portuguese",
    "French",
    "German",
    "Arabic",
    "Russian",
]

PROVIDER_URL = {
    "openai": "https://api.openai.com/v1",
    "siliconflow": "https://api.siliconflow.cn/v1",
    "google": "https://generativelanguage.googleapis.com/v1",
    "anthropic": "https://api.anthropic.com/",
    "xai": "https://api.x.ai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama": "http://localhost:11434/v1",
}


def _models_for(provider: str, mode: str) -> List[str]:
    return [value for _label, value in MODEL_OPTIONS[provider][mode]]


def render_config_form(
    container,
    disabled: bool = False,
    key_prefix: str = "cfg",
) -> Dict[str, Any]:
    """在任意 Streamlit 容器中渲染配置表单（主区或侧栏）。"""
    kp = key_prefix
    container.header("分析任务配置")
    ticker = (
        container.text_input("步骤 1：股票代码（Ticker）", value="SPY", disabled=disabled, key=f"{kp}_ticker")
        .strip()
        .upper()
    )
    analysis_date = container.date_input(
        "步骤 2：分析日期",
        value=dt.date.today(),
        disabled=disabled,
        key=f"{kp}_date",
    )
    output_language = container.selectbox(
        "步骤 3：报告输出语言",
        options=OUTPUT_LANGS,
        index=0,
        disabled=disabled,
        key=f"{kp}_lang",
    )

    container.markdown("步骤 4：分析师团队")
    include_market = container.checkbox("市场", value=True, disabled=disabled, key=f"{kp}_mkt")
    include_social = container.checkbox("舆情", value=True, disabled=disabled, key=f"{kp}_soc")
    include_news = container.checkbox("新闻", value=True, disabled=disabled, key=f"{kp}_news")
    include_fundamentals = container.checkbox(
        "基本面", value=True, disabled=disabled, key=f"{kp}_fund"
    )

    research_depth = container.radio(
        "步骤 5：研究深度（辩论轮数）",
        options=[1, 3, 5],
        horizontal=True,
        disabled=disabled,
        key=f"{kp}_depth",
    )

    provider = container.selectbox(
        "步骤 6：LLM 提供商",
        options=list(PROVIDER_URL.keys()),
        index=0,
        disabled=disabled,
        key=f"{kp}_prov",
    )

    quick_options = _models_for(provider, "quick")
    deep_options = _models_for(provider, "deep")
    quick_model = container.selectbox(
        "步骤 7：快速模型（Quick）", quick_options, disabled=disabled, key=f"{kp}_quick"
    )
    deep_model = container.selectbox(
        "步骤 7：深度模型（Deep）", deep_options, disabled=disabled, key=f"{kp}_deep"
    )

    google_thinking: Optional[str] = None
    openai_reasoning: Optional[str] = None
    anthropic_effort: Optional[str] = None
    if provider == "google":
        google_thinking = container.selectbox(
            "步骤 8：Google Thinking",
            options=["high", "minimal"],
            index=0,
            disabled=disabled,
            key=f"{kp}_gthink",
        )
    elif provider in ("openai", "siliconflow"):
        openai_reasoning = container.selectbox(
            "步骤 8：推理强度（Reasoning）",
            options=["medium", "high", "low"],
            index=0,
            disabled=disabled,
            key=f"{kp}_reason",
        )
    elif provider == "anthropic":
        anthropic_effort = container.selectbox(
            "步骤 8：Anthropic Effort",
            options=["high", "medium", "low"],
            index=0,
            disabled=disabled,
            key=f"{kp}_anth",
        )

    selected_analysts = []
    if include_market:
        selected_analysts.append("market")
    if include_social:
        selected_analysts.append("social")
    if include_news:
        selected_analysts.append("news")
    if include_fundamentals:
        selected_analysts.append("fundamentals")

    return {
        "ticker": ticker,
        "analysis_date": analysis_date.strftime("%Y-%m-%d"),
        "output_language": output_language,
        "selected_analysts": selected_analysts,
        "research_depth": research_depth,
        "llm_provider": provider,
        "backend_url": PROVIDER_URL[provider],
        "quick_model": quick_model,
        "deep_model": deep_model,
        "google_thinking_level": google_thinking,
        "openai_reasoning_effort": openai_reasoning,
        "anthropic_effort": anthropic_effort,
    }


def render_sidebar_form(disabled: bool = False) -> Dict[str, Any]:
    """向后兼容：在侧栏渲染完整配置。"""
    return render_config_form(st.sidebar, disabled=disabled, key_prefix="sidebar")


def format_params_summary(p: Dict[str, Any]) -> str:
    """运行结束后折叠摘要卡片用的一段 Markdown。"""
    effort = (
        p.get("google_thinking_level")
        or p.get("openai_reasoning_effort")
        or p.get("anthropic_effort")
        or "—"
    )
    analysts = ", ".join(p.get("selected_analysts") or []) or "—"
    return (
        f"**股票代码：** {p.get('ticker', '—')}  \n"
        f"**分析日期：** {p.get('analysis_date', '—')}  \n"
        f"**提供商：** {p.get('llm_provider', '—')}  \n"
        f"**模型：** quick `{p.get('quick_model', '—')}` · deep `{p.get('deep_model', '—')}`  \n"
        f"**研究深度：** {p.get('research_depth', '—')}  \n"
        f"**分析师：** {analysts}  \n"
        f"**推理 / 思考：** {effort}  \n"
        f"**输出语言：** {p.get('output_language', '—')}"
    )
