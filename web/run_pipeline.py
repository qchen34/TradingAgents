from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

from cli.main import classify_message_type, save_report_to_disk
from cli.stats_handler import StatsCallbackHandler
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph


def _infer_stage(s: dict) -> str:
    """Map accumulated graph state to a coarse I–V stage label for the Web UI."""
    if (s.get("final_trade_decision") or "").strip():
        return "V — Final trade decision"
    if (s.get("investment_plan") or "").strip():
        return "IV — Risk / portfolio plan"
    if (s.get("trader_investment_plan") or "").strip():
        return "III — Trader investment plan"
    inv = s.get("investment_debate_state") or {}
    if isinstance(inv, dict) and (inv.get("judge_decision") or "").strip():
        return "II — Investment debate (judge)"
    names = []
    for key, short in (
        ("market_report", "market"),
        ("sentiment_report", "social"),
        ("news_report", "news"),
        ("fundamentals_report", "fundamentals"),
    ):
        if (s.get(key) or "").strip():
            names.append(short)
    if names:
        return f"I — Analysts ({', '.join(names)})"
    return "I — Pipeline starting"


def _web_event_role(classify_role: str) -> str:
    """Map CLI classify roles to plan buckets: Agent / Tool / System."""
    if classify_role == "Data":
        return "Tool"
    if classify_role == "Agent":
        return "Agent"
    return "System"


STEP_LABELS = [
    "Market analysis",
    "Social sentiment analysis",
    "News analysis",
    "Fundamental analysis",
    "Bull researcher",
    "Bear researcher",
    "Research manager",
    "Trader",
    "Aggressive risk analyst",
    "Conservative risk analyst",
    "Neutral risk analyst",
    "Portfolio manager",
]

# Web UI 步骤列表（与 STEP_LABELS 一一对应）
STEP_LABELS_ZH = [
    "大盘分析",
    "社交媒体情绪",
    "新闻分析",
    "基本面分析",
    "多头研究员",
    "空头研究员",
    "研究经理",
    "交易员",
    "激进风控分析师",
    "保守风控分析师",
    "中性风控分析师",
    "组合经理",
]


def _infer_step_index(s: dict) -> int:
    """Infer current CLI-like step index (0-based, total 12)."""
    if (s.get("final_trade_decision") or "").strip():
        return 11
    risk = s.get("risk_debate_state") or {}
    if isinstance(risk, dict):
        if (risk.get("neutral_history") or "").strip():
            return 10
        if (risk.get("conservative_history") or "").strip():
            return 9
        if (risk.get("aggressive_history") or "").strip():
            return 8
    if (s.get("trader_investment_plan") or "").strip():
        return 7
    inv = s.get("investment_debate_state") or {}
    if isinstance(inv, dict):
        if (inv.get("judge_decision") or "").strip():
            return 6
        if (inv.get("bear_history") or "").strip():
            return 5
        if (inv.get("bull_history") or "").strip():
            return 4
    if (s.get("fundamentals_report") or "").strip():
        return 3
    if (s.get("news_report") or "").strip():
        return 2
    if (s.get("sentiment_report") or "").strip():
        return 1
    return 0


def _preview(text: Optional[str], limit: int = 400) -> str:
    if not text:
        return ""
    one = text.replace("\n", " ").strip()
    if len(one) > limit:
        return one[: limit - 3] + "..."
    return one


def run_analysis(
    params: Dict,
    progress_cb: Callable[[str], None] | None = None,
    event_cb: Callable[[str], None] | None = None,
    stage_cb: Callable[[str], None] | None = None,
    step_cb: Callable[[dict], None] | None = None,
    stats_cb: Callable[[dict], None] | None = None,
    stream_events: bool = True,
) -> Tuple[dict, str]:
    """Run analysis with web params and return final state and output dir.

    When ``stream_events`` is True, uses LangGraph ``stream`` (CLI-style) and pushes
    classified message lines through ``event_cb``. On failure, falls back to
    ``propagate`` (stage-only via ``progress_cb``).
    """
    if progress_cb:
        progress_cb("Preparing configuration...")

    config = DEFAULT_CONFIG.copy()
    config["max_debate_rounds"] = params["research_depth"]
    config["max_risk_discuss_rounds"] = params["research_depth"]
    config["quick_think_llm"] = params["quick_model"]
    config["deep_think_llm"] = params["deep_model"]
    config["backend_url"] = params["backend_url"]
    config["llm_provider"] = params["llm_provider"]
    config["output_language"] = params["output_language"]
    config["google_thinking_level"] = params.get("google_thinking_level")
    config["openai_reasoning_effort"] = params.get("openai_reasoning_effort")
    config["anthropic_effort"] = params.get("anthropic_effort")

    if progress_cb:
        progress_cb("Initializing TradingAgents graph...")
    stats_handler = StatsCallbackHandler()
    graph = TradingAgentsGraph(
        params["selected_analysts"],
        config=config,
        debug=False,
        callbacks=[stats_handler],
    )
    graph.ticker = params["ticker"]

    out_dir = (
        Path("reports") / f"{params['ticker']}_{params['analysis_date'].replace('-', '')}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    init_agent_state = graph.propagator.create_initial_state(
        params["ticker"], params["analysis_date"]
    )
    args = graph.propagator.get_graph_args(callbacks=[stats_handler])
    invoke_config = args.get("config") or {}

    final_state: dict
    used_stream = False

    if stream_events and (event_cb is not None or stage_cb is not None):
        if progress_cb:
            progress_cb("Running I→V pipeline (streaming events)...")
        trace: list = []
        last_msg_id = None
        try:
            for chunk in graph.graph.stream(init_agent_state, **args):
                trace.append(chunk)
                if not isinstance(chunk, dict):
                    continue
                if stage_cb:
                    stage_cb(_infer_stage(chunk))
                if step_cb:
                    step_i = _infer_step_index(chunk)
                    step_cb(
                        {
                            "index": step_i,
                            "total": len(STEP_LABELS),
                            "label": STEP_LABELS[step_i],
                            "steps": STEP_LABELS,
                        }
                    )
                msgs = chunk.get("messages") or []
                if event_cb is not None and len(msgs) > 0:
                    last_message = msgs[-1]
                    msg_id = getattr(last_message, "id", None)
                    if msg_id != last_msg_id:
                        last_msg_id = msg_id
                        role, content = classify_message_type(last_message)
                        web_role = _web_event_role(role)
                        line = f"[{web_role}] {_preview(content)}"
                        event_cb(line)
                if stats_cb:
                    stats_cb(stats_handler.get_stats())
            if trace:
                final_state = trace[-1]
                used_stream = True
                if event_cb is not None:
                    st = stats_handler.get_stats()
                    event_cb(
                        f"[System] final stats: llm_calls={st['llm_calls']} "
                        f"tool_calls={st['tool_calls']} "
                        f"tokens_in={st['tokens_in']} tokens_out={st['tokens_out']}"
                    )
            else:
                raise RuntimeError("empty stream trace")
        except Exception as exc:
            if progress_cb:
                progress_cb(f"Streaming failed ({exc!r}); falling back to invoke...")
            used_stream = False

    if not used_stream:
        if progress_cb:
            progress_cb("Running I→V analysis pipeline...")
        if step_cb:
            step_cb({"index": 0, "total": len(STEP_LABELS), "label": STEP_LABELS[0], "steps": STEP_LABELS})
        final_state = graph.graph.invoke(init_agent_state, config=invoke_config)
        if step_cb:
            step_cb({"index": len(STEP_LABELS) - 1, "total": len(STEP_LABELS), "label": STEP_LABELS[-1], "steps": STEP_LABELS})
        if stats_cb:
            stats_cb(stats_handler.get_stats())

    graph.curr_state = final_state
    graph._log_state(params["analysis_date"], final_state)

    if progress_cb:
        progress_cb("Saving report files...")
    save_report_to_disk(final_state, params["ticker"], out_dir)

    if progress_cb:
        progress_cb("Done.")
    return final_state, str(out_dir)
