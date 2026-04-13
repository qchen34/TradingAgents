from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage

from web.config_ui import PROVIDER_URL
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.llm_clients.base_client import normalize_content
from tradingagents.llm_clients.factory import create_llm_client
from tradingagents.llm_clients.model_catalog import MODEL_OPTIONS

# 仪表盘 LLM 默认：SiliconFlow + catalog 中首个 quick（与 Web 表单选 SiliconFlow 时第一项一致）
_DASHBOARD_DEFAULT_PROVIDER = "siliconflow"
_DASHBOARD_DEFAULT_QUICK = MODEL_OPTIONS[_DASHBOARD_DEFAULT_PROVIDER]["quick"][0][1]


def build_llm_config(last_params: dict[str, Any] | None) -> dict[str, Any]:
    cfg = DEFAULT_CONFIG.copy()
    cfg["llm_provider"] = _DASHBOARD_DEFAULT_PROVIDER
    cfg["quick_think_llm"] = _DASHBOARD_DEFAULT_QUICK
    cfg["backend_url"] = PROVIDER_URL[_DASHBOARD_DEFAULT_PROVIDER]
    if last_params:
        cfg["llm_provider"] = last_params.get("llm_provider", cfg["llm_provider"])
        cfg["quick_think_llm"] = last_params.get("quick_model", cfg["quick_think_llm"])
        cfg["backend_url"] = last_params.get("backend_url", cfg["backend_url"])
        if last_params.get("google_thinking_level"):
            cfg["google_thinking_level"] = last_params.get("google_thinking_level")
        if last_params.get("openai_reasoning_effort"):
            cfg["openai_reasoning_effort"] = last_params.get("openai_reasoning_effort")
        if last_params.get("anthropic_effort"):
            cfg["anthropic_effort"] = last_params.get("anthropic_effort")
    return cfg


def _quick_llm_kwargs(cfg: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if cfg.get("google_thinking_level"):
        out["google_thinking_level"] = cfg["google_thinking_level"]
    if cfg.get("openai_reasoning_effort"):
        out["openai_reasoning_effort"] = cfg["openai_reasoning_effort"]
    if cfg.get("anthropic_effort"):
        out["anthropic_effort"] = cfg["anthropic_effort"]
    return out


def _get_llm(cfg: dict[str, Any]):
    client = create_llm_client(
        provider=cfg["llm_provider"],
        model=cfg["quick_think_llm"],
        base_url=cfg.get("backend_url"),
        **_quick_llm_kwargs(cfg),
    )
    return client.get_llm()


def _msg_text(resp: Any) -> str:
    if hasattr(resp, "content"):
        normalize_content(resp)
        c = resp.content
        return c if isinstance(c, str) else str(c)
    return str(resp)


def _parse_json_array(text: str) -> list[dict[str, Any]]:
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    m = re.search(r"\[[\s\S]*\]", text)
    if m:
        return json.loads(m.group(0))
    raise ValueError("no JSON array in model output")


def enrich_news_opinions(
    news_items: list[dict[str, Any]],
    cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    """为每条新闻补充 stance + llm_summary（批量一次调用）。"""
    if not news_items:
        return news_items
    llm = _get_llm(cfg)
    lines = []
    for i, n in enumerate(news_items):
        title = (n.get("title") or "")[:500]
        summary = (n.get("summary") or "")[:800]
        lines.append(f'{i}. title: {title}\n   summary: {summary}')
    block = "\n".join(lines)
    prompt = f"""你是财经新闻简评助手。根据下列新闻标题与摘要，对每条给出市场情绪判断与一句中文短评。

新闻列表：
{block}

请只输出一个 JSON 数组，长度与新闻条数相同，不要 markdown 围栏。每个元素格式：
{{"stance":"bullish"|"bearish"|"neutral","summary":"一句中文，不超过80字"}}

stance 含义：bullish=偏多/利好倾向，bearish=偏空/利空倾向，neutral=中性或信息不足。
"""
    resp = llm.invoke([HumanMessage(content=prompt)])
    raw = _msg_text(resp)
    arr = _parse_json_array(raw)
    out = []
    for i, n in enumerate(news_items):
        row = dict(n)
        if i < len(arr) and isinstance(arr[i], dict):
            row["stance"] = arr[i].get("stance", "neutral")
            row["llm_summary"] = (arr[i].get("summary") or "").strip()
        else:
            row["stance"] = "neutral"
            row["llm_summary"] = ""
        out.append(row)
    return out


def generate_market_digest(
    snapshot_context: dict[str, Any],
    news_items: list[dict[str, Any]],
    cfg: dict[str, Any],
) -> str:
    """生成仪表盘顶部大盘总结（Markdown）。"""
    llm = _get_llm(cfg)
    macro = snapshot_context.get("macro_strip") or []
    macro_lines = []
    for m in macro:
        ch = m.get("change_pct")
        ch_s = f"{ch:.2f}" if ch is not None else "N/A"
        macro_lines.append(
            f"- {m.get('label', m.get('ticker'))}: "
            f"价/收益率 {m.get('display_value', 'N/A')} "
            f"日涨跌 {ch_s}%"
        )
    idx_lines = []
    for r in snapshot_context.get("indexes") or []:
        if hasattr(r, "ticker"):
            t, p, ch = r.ticker, r.price, r.change_pct
        else:
            t = r.get("ticker")
            p = r.get("price")
            ch = r.get("change_pct")
        ch_s = f"{ch:.2f}" if ch is not None else "N/A"
        p_s = f"{p:.2f}" if p is not None else "N/A"
        idx_lines.append(f"- {t}: {p_s} ({ch_s}%)")
    news_brief = "\n".join(
        f"- {(n.get('title') or '')[:120]}" for n in (news_items or [])[:10]
    )
    prompt = f"""你是美股市场复盘助手。根据下列**结构化数据**（可能不完整），用中文 Markdown 输出。

【硬性格式 — 必须严格遵守】
1. **禁止**在第一个以 `##### ` 开头的标题行之前输出任何正文、引言或列表（不要先写一段再写标题）。
2. 全文必须且只能按下面 **5 个小节** 依次展开；每一节**单独一行**以 `##### ` 开头（五个 # 加一个空格），紧接着下一行起写该节正文。
3. 小节标题请尽量使用下列措辞（可微调个别用词，但必须保留 `##### ` 前缀）：
   - `##### 经济数据说明了什么`
   - `##### 大盘数据说明了什么`
   - `##### 新闻数据说明了什么`
   - `##### 整体结论`
   - `##### 牛熊判断与数据论据`
4. 「经济数据」节的正文必须写在 `##### 经济数据说明了什么` 标题**下面**，基于美债收益率、美元、TIP 等代理指标推断；勿编造未提供的官方 CPI 数字。
5. 「牛熊判断」节请说明当前美股更偏牛市/熊市/震荡，并列出**可核对的数据论据**（条目列表）。

【输出结构示例】（模仿此结构，把括号说明换成你的实质分析）：

##### 经济数据说明了什么
（本节正文：基于代理指标的分析。）

##### 大盘数据说明了什么
（本节正文：指数与 VIX。）

##### 新闻数据说明了什么
（本节正文：聚合倾向，勿逐条复述。）

##### 整体结论
（本节正文。）

##### 牛熊判断与数据论据
（本节正文：条目列表。）

---
宏观代理指标：
{chr(10).join(macro_lines) if macro_lines else '（无）'}

主要指数：
{chr(10).join(idx_lines) if idx_lines else '（无）'}

新闻标题摘要：
{news_brief if news_brief else '（无）'}
"""
    resp = llm.invoke([HumanMessage(content=prompt)])
    return _msg_text(resp).strip()
