from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage

from tradingagents.llm_clients.base_client import normalize_content
from tradingagents.llm_clients.factory import create_llm_client

_LRS_DOC_MD = """
### LRS TQQQ策略（草案）

LRS（Long Regime Switching）TQQQ 策略的当前目标是提供一个最小可运行框架，用于快速验证：

1. 在趋势行情中保持多头暴露（以 TQQQ 为核心标的）。
2. 在风险放大阶段降低仓位或切换到观望。
3. 将信号、仓位和回测结果放在同一策略页面里，便于迭代。

**当前版本（MVP）策略骨架：**

- **标的**：`TQQQ`
- **信号层**：趋势/波动率/风险三类信号（后续逐步细化）
- **执行层**：先不接券商下单，仅输出建议仓位与操作提示
- **评估层**：回测页展示收益、回撤、胜率、换手（当前先占位）

**后续计划：**

- 增加参数面板（信号窗口、止损阈值、仓位上限）
- 接入历史数据批量回测
- 输出可复盘的策略日志与版本对比
""".strip()


def get_lrs_doc_markdown() -> str:
    return _LRS_DOC_MD


def answer_lrs_question(prompt: str, cfg: dict[str, Any]) -> str:
    client = create_llm_client(
        provider=cfg["llm_provider"],
        model=cfg["quick_think_llm"],
        base_url=cfg.get("backend_url"),
    )
    llm = client.get_llm()
    resp = llm.invoke([HumanMessage(content=prompt)])
    if hasattr(resp, "content"):
        normalize_content(resp)
        content = resp.content
        out = content if isinstance(content, str) else str(content)
        return out.strip() or "我暂时没有生成有效内容，请换个问法再试。"
    return str(resp)

