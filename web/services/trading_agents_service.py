"""TradingAgents Web 化服务

把 cli/main.py 的多 Agent 分析流水线包装成无交互函数 + in-memory job 管理：
- get_options(): 返回 Provider/Model/Analysts/Depth/Language 等下拉选项
- run_analysis_job(payload): 后台线程跑分析，落盘到 reports/{ticker}_{timestamp}/
- list_reports() / get_report(report_id): 扫描并解析 reports/ 历史报告
"""
from __future__ import annotations

import datetime
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime as dt
from datetime import timezone
from pathlib import Path
from typing import Any

from tradingagents.llm_clients.model_catalog import MODEL_OPTIONS

# ──────────────────────────────────────────────────────────────────────────────
# 常量与目录
# ──────────────────────────────────────────────────────────────────────────────

REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

PROVIDER_URLS: dict[str, dict[str, str]] = {
    "openai": {"label": "OpenAI", "backend_url": "https://api.openai.com/v1", "thinking": "reasoning_effort"},
    "siliconflow": {"label": "SiliconFlow", "backend_url": "https://api.siliconflow.cn/v1", "thinking": "reasoning_effort"},
    "google": {"label": "Google", "backend_url": "https://generativelanguage.googleapis.com/v1", "thinking": "thinking_level"},
    "anthropic": {"label": "Anthropic", "backend_url": "https://api.anthropic.com/", "thinking": "effort"},
    "xai": {"label": "xAI", "backend_url": "https://api.x.ai/v1", "thinking": ""},
    "openrouter": {"label": "Openrouter", "backend_url": "https://openrouter.ai/api/v1", "thinking": ""},
    "ollama": {"label": "Ollama", "backend_url": "http://localhost:11434/v1", "thinking": ""},
}

ANALYST_OPTIONS: list[dict[str, str]] = [
    {"id": "market", "label": "Market Analyst"},
    {"id": "social", "label": "Social Media Analyst"},
    {"id": "news", "label": "News Analyst"},
    {"id": "fundamentals", "label": "Fundamentals Analyst"},
]

DEPTH_OPTIONS: list[dict[str, Any]] = [
    {"label": "Shallow - 快速研究、辩论与讨论轮次少", "value": 1},
    {"label": "Medium - 适中辩论与策略讨论轮次", "value": 3},
    {"label": "Deep - 深度研究、全面辩论", "value": 5},
]

LANGUAGE_OPTIONS: list[dict[str, str]] = [
    {"label": "English (default)", "value": "English"},
    {"label": "Chinese (中文)", "value": "Chinese"},
    {"label": "Japanese (日本語)", "value": "Japanese"},
    {"label": "Korean (한국어)", "value": "Korean"},
    {"label": "Hindi (हिन्दी)", "value": "Hindi"},
    {"label": "Spanish (Español)", "value": "Spanish"},
    {"label": "Portuguese (Português)", "value": "Portuguese"},
    {"label": "French (Français)", "value": "French"},
    {"label": "German (Deutsch)", "value": "German"},
    {"label": "Arabic (العربية)", "value": "Arabic"},
    {"label": "Russian (Русский)", "value": "Russian"},
]

THINKING_CONFIGS: dict[str, list[dict[str, str]]] = {
    "openai": [
        {"label": "Medium (Default)", "value": "medium"},
        {"label": "High (More thorough)", "value": "high"},
        {"label": "Low (Faster)", "value": "low"},
    ],
    "siliconflow": [
        {"label": "Medium (Default)", "value": "medium"},
        {"label": "High (More thorough)", "value": "high"},
        {"label": "Low (Faster)", "value": "low"},
    ],
    "anthropic": [
        {"label": "High (recommended)", "value": "high"},
        {"label": "Medium (balanced)", "value": "medium"},
        {"label": "Low (faster, cheaper)", "value": "low"},
    ],
    "google": [
        {"label": "Enable Thinking (recommended)", "value": "high"},
        {"label": "Minimal/Disable Thinking", "value": "minimal"},
    ],
}


# ──────────────────────────────────────────────────────────────────────────────
# Job 管理
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class TaJob:
    job_id: str
    status: str  # queued / running / completed / failed
    ticker: str
    analysis_date: str
    created_at: str
    updated_at: str = field(default_factory=lambda: _now_iso())
    started_at: str | None = None
    completed_at: str | None = None
    elapsed_seconds: float = 0.0
    progress: str = ""
    report_id: str | None = None
    error: str | None = None
    # ── 实时进度字段（镜像 cli/main.py MessageBuffer）───────────────────────────
    agent_statuses: dict[str, str] = field(default_factory=dict)
    current_agent: str | None = None
    messages: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=lambda: {
        "llm_calls": 0,
        "tool_calls": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "agents_completed": 0,
        "agents_total": 0,
        "reports_completed": 0,
        "reports_total": 0,
    })
    report_sections: dict[str, str | None] = field(default_factory=dict)
    current_section: str | None = None


_JOBS: dict[str, TaJob] = {}
_JOB_LOCK = threading.Lock()


def _now_iso() -> str:
    return dt.now(timezone.utc).isoformat()


def _has_running_job() -> bool:
    with _JOB_LOCK:
        return any(j.status in ("queued", "running") for j in _JOBS.values())


# ──────────────────────────────────────────────────────────────────────────────
# 选项 API
# ──────────────────────────────────────────────────────────────────────────────

def get_options() -> dict[str, Any]:
    """返回 Provider/Model/Analysts/Depth/Language/Thinking 选项给前端。"""
    providers: list[dict[str, Any]] = []
    models: dict[str, dict[str, list[dict[str, str]]]] = {}

    for pid, info in PROVIDER_URLS.items():
        providers.append(
            {
                "id": pid,
                "label": info["label"],
                "backend_url": info["backend_url"],
                "thinking": info["thinking"],
            }
        )
        if pid in MODEL_OPTIONS:
            models[pid] = {
                "quick": [
                    {"label": display, "value": value}
                    for display, value in MODEL_OPTIONS[pid]["quick"]
                ],
                "deep": [
                    {"label": display, "value": value}
                    for display, value in MODEL_OPTIONS[pid]["deep"]
                ],
            }

    return {
        "providers": providers,
        "models": models,
        "analysts": ANALYST_OPTIONS,
        "depths": DEPTH_OPTIONS,
        "languages": LANGUAGE_OPTIONS,
        "thinking_configs": THINKING_CONFIGS,
        "defaults": {
            "provider": "siliconflow",
            "language": "Chinese",
            "depth": 3,
            "analysts": ["market", "social", "news", "fundamentals"],
            "openai_reasoning_effort": "medium",
            "anthropic_effort": "high",
            "google_thinking_level": "high",
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# 运行分析（后台线程）
# ──────────────────────────────────────────────────────────────────────────────

def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """校验并归一化前端表单输入。"""
    ticker = str(payload.get("ticker", "")).strip().upper()
    if not ticker:
        raise ValueError("ticker 不能为空")

    date_str = str(payload.get("analysis_date", "")).strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise ValueError("analysis_date 格式应为 YYYY-MM-DD")
    try:
        ad = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError as e:
        raise ValueError(f"analysis_date 解析失败：{e}") from e
    if ad > datetime.datetime.now().date():
        raise ValueError("analysis_date 不能为未来日期")

    analysts = payload.get("analysts") or []
    if not isinstance(analysts, list) or not analysts:
        raise ValueError("至少选择一名分析师")
    valid_analyst_ids = {a["id"] for a in ANALYST_OPTIONS}
    for a in analysts:
        if a not in valid_analyst_ids:
            raise ValueError(f"未知分析师类型：{a}")

    depth = int(payload.get("research_depth", 3))
    if depth not in (1, 3, 5):
        raise ValueError("research_depth 仅允许 1 / 3 / 5")

    provider = str(payload.get("llm_provider", "siliconflow")).lower()
    if provider not in PROVIDER_URLS:
        raise ValueError(f"未知 LLM Provider：{provider}")

    backend_url = str(payload.get("backend_url") or PROVIDER_URLS[provider]["backend_url"])
    shallow = str(payload.get("shallow_thinker") or "").strip()
    deep = str(payload.get("deep_thinker") or "").strip()
    if not shallow or not deep:
        raise ValueError("quick / deep thinking model 不能为空")

    return {
        "ticker": ticker,
        "analysis_date": date_str,
        "analysts": analysts,
        "research_depth": depth,
        "llm_provider": provider,
        "backend_url": backend_url,
        "shallow_thinker": shallow,
        "deep_thinker": deep,
        "openai_reasoning_effort": payload.get("openai_reasoning_effort"),
        "anthropic_effort": payload.get("anthropic_effort"),
        "google_thinking_level": payload.get("google_thinking_level"),
        "output_language": payload.get("output_language") or "English",
    }


# ──────────────────────────────────────────────────────────────────────────────
# CLI MessageBuffer 复刻：agent 团队结构 / 章节映射 / 状态推进
# ──────────────────────────────────────────────────────────────────────────────

_FIXED_AGENTS: dict[str, list[str]] = {
    "Research Team": ["Bull Researcher", "Bear Researcher", "Research Manager"],
    "Trading Team": ["Trader"],
    "Risk Management": ["Aggressive Analyst", "Neutral Analyst", "Conservative Analyst"],
    "Portfolio Management": ["Portfolio Manager"],
}

_ANALYST_MAPPING: dict[str, str] = {
    "market": "Market Analyst",
    "social": "Social Analyst",
    "news": "News Analyst",
    "fundamentals": "Fundamentals Analyst",
}

_ANALYST_ORDER: list[str] = ["market", "social", "news", "fundamentals"]

_ANALYST_REPORT_MAP: dict[str, str] = {
    "market": "market_report",
    "social": "sentiment_report",
    "news": "news_report",
    "fundamentals": "fundamentals_report",
}

# section -> (analyst_key for filtering, finalizing_agent)
_REPORT_SECTIONS: dict[str, tuple[str | None, str]] = {
    "market_report": ("market", "Market Analyst"),
    "sentiment_report": ("social", "Social Analyst"),
    "news_report": ("news", "News Analyst"),
    "fundamentals_report": ("fundamentals", "Fundamentals Analyst"),
    "investment_plan": (None, "Research Manager"),
    "trader_investment_plan": (None, "Trader"),
    "final_trade_decision": (None, "Portfolio Manager"),
}

_MAX_MESSAGES = 60
_MAX_TOOL_CALLS = 60


def _format_tool_args(args: Any, max_length: int = 120) -> str:
    s = str(args)
    if len(s) > max_length:
        return s[: max_length - 3] + "..."
    return s


def _classify_message(message: Any) -> tuple[str, str | None]:
    """与 cli/main.py.classify_message_type 同构，但容忍缺失依赖时回退。"""
    try:
        from cli.main import classify_message_type

        return classify_message_type(message)
    except Exception:
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return "Agent", content.strip() or None
        return "Agent", None


def _init_progress_state(job: TaJob, selected_analysts: list[str]) -> None:
    """初始化 agent_statuses / report_sections / stats，按 CLI 行为对齐。"""
    statuses: dict[str, str] = {}
    for key in selected_analysts:
        if key in _ANALYST_MAPPING:
            statuses[_ANALYST_MAPPING[key]] = "pending"
    for team_agents in _FIXED_AGENTS.values():
        for a in team_agents:
            statuses[a] = "pending"

    sections: dict[str, str | None] = {}
    for section, (analyst_key, _) in _REPORT_SECTIONS.items():
        if analyst_key is None or analyst_key in selected_analysts:
            sections[section] = None

    job.agent_statuses = statuses
    job.report_sections = sections
    job.current_agent = None
    job.current_section = None
    job.messages = []
    job.tool_calls = []
    job.stats = {
        "llm_calls": 0,
        "tool_calls": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "agents_completed": 0,
        "agents_total": len(statuses),
        "reports_completed": 0,
        "reports_total": len(sections),
    }


def _set_agent_status(job: TaJob, agent: str, status: str) -> None:
    if agent not in job.agent_statuses:
        return
    job.agent_statuses[agent] = status
    if status == "in_progress":
        job.current_agent = agent


def _set_research_team_status(job: TaJob, status: str) -> None:
    for a in _FIXED_AGENTS["Research Team"]:
        _set_agent_status(job, a, status)


def _set_section(job: TaJob, section_name: str, content: str | None) -> None:
    if section_name in job.report_sections:
        job.report_sections[section_name] = content
        if content:
            job.current_section = section_name


def _recompute_stats(job: TaJob) -> None:
    job.stats["agents_completed"] = sum(
        1 for s in job.agent_statuses.values() if s == "completed"
    )
    completed = 0
    for section, (_, finalizing_agent) in _REPORT_SECTIONS.items():
        if section not in job.report_sections:
            continue
        has_content = bool(job.report_sections.get(section))
        agent_done = job.agent_statuses.get(finalizing_agent) == "completed"
        if has_content and agent_done:
            completed += 1
    job.stats["reports_completed"] = completed


def _update_analyst_statuses_from_chunk(
    job: TaJob, chunk: dict[str, Any], selected: list[str]
) -> None:
    found_active = False
    for analyst_key in _ANALYST_ORDER:
        if analyst_key not in selected:
            continue
        agent_name = _ANALYST_MAPPING[analyst_key]
        report_key = _ANALYST_REPORT_MAP[analyst_key]

        if chunk.get(report_key):
            _set_section(job, report_key, chunk[report_key])

        has_report = bool(job.report_sections.get(report_key))
        if has_report:
            _set_agent_status(job, agent_name, "completed")
        elif not found_active:
            _set_agent_status(job, agent_name, "in_progress")
            found_active = True
        else:
            _set_agent_status(job, agent_name, "pending")

    if not found_active and selected:
        if job.agent_statuses.get("Bull Researcher") == "pending":
            _set_agent_status(job, "Bull Researcher", "in_progress")


def _process_chunk(job: TaJob, chunk: dict[str, Any], selected: list[str]) -> None:
    """复刻 cli/main.py 中 chunk 处理逻辑，仅修改 job 状态字段。"""
    ts = datetime.datetime.now().strftime("%H:%M:%S")

    messages_list = chunk.get("messages") or []
    if messages_list:
        last_message = messages_list[-1]
        msg_id = getattr(last_message, "id", None)
        last_recorded = job.messages[-1].get("msg_id") if job.messages else None
        if msg_id is not None and msg_id != last_recorded:
            msg_type, content = _classify_message(last_message)
            if content and content.strip():
                content_str = content if len(content) <= 600 else content[:597] + "..."
                job.messages.append(
                    {
                        "timestamp": ts,
                        "type": msg_type,
                        "content": content_str,
                        "msg_id": msg_id,
                    }
                )
                if len(job.messages) > _MAX_MESSAGES:
                    job.messages = job.messages[-_MAX_MESSAGES:]

            tool_calls_attr = getattr(last_message, "tool_calls", None)
            if tool_calls_attr:
                for tc in tool_calls_attr:
                    if isinstance(tc, dict):
                        name = tc.get("name", "")
                        args = tc.get("args", {})
                    else:
                        name = getattr(tc, "name", "")
                        args = getattr(tc, "args", {})
                    job.tool_calls.append(
                        {
                            "timestamp": ts,
                            "tool_name": str(name),
                            "args_preview": _format_tool_args(args),
                        }
                    )
                    if len(job.tool_calls) > _MAX_TOOL_CALLS:
                        job.tool_calls = job.tool_calls[-_MAX_TOOL_CALLS:]

    _update_analyst_statuses_from_chunk(job, chunk, selected)

    debate = chunk.get("investment_debate_state") or {}
    bull_hist = (debate.get("bull_history") or "").strip()
    bear_hist = (debate.get("bear_history") or "").strip()
    judge = (debate.get("judge_decision") or "").strip()
    if bull_hist or bear_hist:
        for a in _FIXED_AGENTS["Research Team"]:
            if job.agent_statuses.get(a) == "pending":
                _set_agent_status(job, a, "in_progress")
    if bull_hist:
        _set_section(job, "investment_plan", f"### Bull Researcher Analysis\n{bull_hist}")
    if bear_hist:
        _set_section(job, "investment_plan", f"### Bear Researcher Analysis\n{bear_hist}")
    if judge:
        _set_section(job, "investment_plan", f"### Research Manager Decision\n{judge}")
        _set_research_team_status(job, "completed")
        if job.agent_statuses.get("Trader") == "pending":
            _set_agent_status(job, "Trader", "in_progress")

    if chunk.get("trader_investment_plan"):
        _set_section(job, "trader_investment_plan", chunk["trader_investment_plan"])
        if job.agent_statuses.get("Trader") != "completed":
            _set_agent_status(job, "Trader", "completed")
            if job.agent_statuses.get("Aggressive Analyst") == "pending":
                _set_agent_status(job, "Aggressive Analyst", "in_progress")

    risk = chunk.get("risk_debate_state") or {}
    agg = (risk.get("aggressive_history") or "").strip()
    con = (risk.get("conservative_history") or "").strip()
    neu = (risk.get("neutral_history") or "").strip()
    rjudge = (risk.get("judge_decision") or "").strip()
    if agg:
        if job.agent_statuses.get("Aggressive Analyst") != "completed":
            _set_agent_status(job, "Aggressive Analyst", "in_progress")
        _set_section(job, "final_trade_decision", f"### Aggressive Analyst Analysis\n{agg}")
    if con:
        if job.agent_statuses.get("Conservative Analyst") != "completed":
            _set_agent_status(job, "Conservative Analyst", "in_progress")
        _set_section(job, "final_trade_decision", f"### Conservative Analyst Analysis\n{con}")
    if neu:
        if job.agent_statuses.get("Neutral Analyst") != "completed":
            _set_agent_status(job, "Neutral Analyst", "in_progress")
        _set_section(job, "final_trade_decision", f"### Neutral Analyst Analysis\n{neu}")
    if rjudge:
        _set_section(job, "final_trade_decision", f"### Portfolio Manager Decision\n{rjudge}")
        for a in ["Aggressive Analyst", "Conservative Analyst", "Neutral Analyst", "Portfolio Manager"]:
            _set_agent_status(job, a, "completed")


def _run_analysis_thread(job_id: str, cfg: dict[str, Any]) -> None:
    """后台线程：跑 TradingAgents graph、落盘 reports/、更新 job 状态。"""
    # Lazy import：避免模块导入时拉起整个 LangGraph 依赖链
    from cli.main import save_report_to_disk
    from cli.stats_handler import StatsCallbackHandler
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    started = time.time()
    stats_handler = StatsCallbackHandler()
    with _JOB_LOCK:
        job = _JOBS[job_id]
        job.status = "running"
        job.started_at = _now_iso()
        job.progress = "Initializing"
        job.updated_at = _now_iso()
        _init_progress_state(job, cfg["analysts"])

    try:
        ta_config = DEFAULT_CONFIG.copy()
        ta_config["max_debate_rounds"] = cfg["research_depth"]
        ta_config["max_risk_discuss_rounds"] = cfg["research_depth"]
        ta_config["quick_think_llm"] = cfg["shallow_thinker"]
        ta_config["deep_think_llm"] = cfg["deep_thinker"]
        ta_config["backend_url"] = cfg["backend_url"]
        ta_config["llm_provider"] = cfg["llm_provider"]
        ta_config["openai_reasoning_effort"] = cfg.get("openai_reasoning_effort")
        ta_config["anthropic_effort"] = cfg.get("anthropic_effort")
        ta_config["google_thinking_level"] = cfg.get("google_thinking_level")
        ta_config["output_language"] = cfg.get("output_language", "English")

        graph = TradingAgentsGraph(
            cfg["analysts"], config=ta_config, debug=False, callbacks=[stats_handler]
        )

        with _JOB_LOCK:
            _JOBS[job_id].progress = "Running multi-agent graph"
            _JOBS[job_id].updated_at = _now_iso()
            # 启动第一个分析师为 in_progress（与 CLI 行为一致）
            first = cfg["analysts"][0] if cfg["analysts"] else None
            if first and first in _ANALYST_MAPPING:
                _set_agent_status(_JOBS[job_id], _ANALYST_MAPPING[first], "in_progress")

        init_state = graph.propagator.create_initial_state(
            cfg["ticker"], cfg["analysis_date"]
        )
        args = graph.propagator.get_graph_args(callbacks=[stats_handler])

        final_state: dict[str, Any] | None = None
        for chunk in graph.graph.stream(init_state, **args):
            final_state = chunk
            with _JOB_LOCK:
                j = _JOBS[job_id]
                _process_chunk(j, chunk, cfg["analysts"])
                stats = stats_handler.get_stats()
                j.stats["llm_calls"] = stats["llm_calls"]
                j.stats["tool_calls"] = stats["tool_calls"]
                j.stats["tokens_in"] = stats["tokens_in"]
                j.stats["tokens_out"] = stats["tokens_out"]
                _recompute_stats(j)
                j.elapsed_seconds = round(time.time() - started, 1)
                j.updated_at = _now_iso()

        if final_state is None:
            raise RuntimeError("TradingAgents 未产出任何状态")

        # 全部 agent 标记完成 + 同步最终 section 内容
        with _JOB_LOCK:
            j = _JOBS[job_id]
            for a in list(j.agent_statuses.keys()):
                j.agent_statuses[a] = "completed"
            for section in list(j.report_sections.keys()):
                if section in final_state and final_state[section]:
                    j.report_sections[section] = final_state[section]
            _recompute_stats(j)
            j.updated_at = _now_iso()

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_id = f"{cfg['ticker']}_{timestamp}"
        save_path = REPORTS_DIR / report_id
        save_report_to_disk(final_state, cfg["ticker"], save_path)

        with _JOB_LOCK:
            j = _JOBS[job_id]
            j.status = "completed"
            j.completed_at = _now_iso()
            j.updated_at = _now_iso()
            j.elapsed_seconds = round(time.time() - started, 1)
            j.report_id = report_id
            j.progress = "Completed"

    except Exception as exc:  # pragma: no cover - best effort background task
        with _JOB_LOCK:
            j = _JOBS[job_id]
            j.status = "failed"
            j.completed_at = _now_iso()
            j.updated_at = _now_iso()
            j.elapsed_seconds = round(time.time() - started, 1)
            j.error = str(exc)
            j.progress = "Failed"


def create_run_job(payload: dict[str, Any]) -> TaJob:
    """启动后台分析任务；同实例只允许一个 job 运行中。"""
    if _has_running_job():
        raise RuntimeError("已有一个 TradingAgents 分析在运行中，请等待完成或刷新页面")

    cfg = _normalize_payload(payload)
    job_id = uuid.uuid4().hex
    job = TaJob(
        job_id=job_id,
        status="queued",
        ticker=cfg["ticker"],
        analysis_date=cfg["analysis_date"],
        created_at=_now_iso(),
    )
    with _JOB_LOCK:
        _JOBS[job_id] = job

    th = threading.Thread(target=_run_analysis_thread, args=(job_id, cfg), daemon=True)
    th.start()
    return job


def get_job(job_id: str) -> TaJob | None:
    with _JOB_LOCK:
        return _JOBS.get(job_id)


def serialize_job(job: TaJob) -> dict[str, Any]:
    return asdict(job)


# ──────────────────────────────────────────────────────────────────────────────
# 报告读取
# ──────────────────────────────────────────────────────────────────────────────

_REPORT_DIR_RE = re.compile(r"^(?P<ticker>[A-Z0-9._-]+)_(?P<ts>\d{8}(?:_\d{6})?)$")


def _read_text(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return None


def _parse_dir_meta(path: Path) -> dict[str, Any] | None:
    if not path.is_dir():
        return None
    m = _REPORT_DIR_RE.match(path.name)
    if not m:
        return None
    ts = m.group("ts")
    gen: datetime.datetime | None = None
    for fmt in ("%Y%m%d_%H%M%S", "%Y%m%d"):
        try:
            gen = datetime.datetime.strptime(ts, fmt)
            break
        except ValueError:
            continue
    if gen is None:
        return None
    analysts: list[str] = []
    if (path / "1_analysts" / "market.md").exists():
        analysts.append("market")
    if (path / "1_analysts" / "sentiment.md").exists():
        analysts.append("social")
    if (path / "1_analysts" / "news.md").exists():
        analysts.append("news")
    if (path / "1_analysts" / "fundamentals.md").exists():
        analysts.append("fundamentals")
    has_complete = (path / "complete_report.md").exists()
    return {
        "report_id": path.name,
        "ticker": m.group("ticker"),
        "generated_at": gen.isoformat(),
        "analysts": analysts,
        "has_complete_report": has_complete,
    }


def list_reports() -> list[dict[str, Any]]:
    """扫描 reports/ 目录，按 generated_at 倒序返回元数据列表。"""
    if not REPORTS_DIR.exists():
        return []
    metas: list[dict[str, Any]] = []
    for child in REPORTS_DIR.iterdir():
        meta = _parse_dir_meta(child)
        if meta is not None:
            metas.append(meta)
    metas.sort(key=lambda x: x["generated_at"], reverse=True)
    return metas


_DECISION_RE = re.compile(r"\b(BUY|HOLD|SELL)\b", re.IGNORECASE)


def _classify_decision(text: str) -> tuple[str, str]:
    """从 portfolio decision 文本里抽取最终决策与简短摘要。

    优先扫描显式 FINAL/Final Decision: BUY 等 pattern；否则取首个匹配。
    """
    if not text:
        return "UNKNOWN", ""

    candidates: list[tuple[int, str]] = []
    for pat in [
        r"FINAL\s+TRANSACTION\s+PROPOSAL[:：]\s*\**\s*(BUY|HOLD|SELL)",
        r"FINAL\s+DECISION[:：]\s*\**\s*(BUY|HOLD|SELL)",
        r"FINAL\s+RECOMMENDATION[:：]\s*\**\s*(BUY|HOLD|SELL)",
        r"DECISION[:：]\s*\**\s*(BUY|HOLD|SELL)",
        r"最终决策[:：]?\s*\**\s*(BUY|HOLD|SELL)",
        r"最终建议[:：]?\s*\**\s*(BUY|HOLD|SELL)",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            candidates.append((m.start(), m.group(1).upper()))

    decision = "UNKNOWN"
    if candidates:
        candidates.sort(key=lambda x: x[0])
        decision = candidates[0][1]
    else:
        m = _DECISION_RE.search(text)
        if m:
            decision = m.group(1).upper()

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    summary = paragraphs[0] if paragraphs else text[:400]
    if len(summary) > 600:
        summary = summary[:600] + "..."
    return decision, summary


def get_report(report_id: str) -> dict[str, Any] | None:
    if not _REPORT_DIR_RE.match(report_id):
        return None
    path = REPORTS_DIR / report_id
    meta = _parse_dir_meta(path)
    if meta is None:
        return None

    analysts_dir = path / "1_analysts"
    research_dir = path / "2_research"
    trading_dir = path / "3_trading"
    risk_dir = path / "4_risk"
    portfolio_dir = path / "5_portfolio"

    sections = {
        "analysts": {
            "market": _read_text(analysts_dir / "market.md"),
            "social": _read_text(analysts_dir / "sentiment.md"),
            "news": _read_text(analysts_dir / "news.md"),
            "fundamentals": _read_text(analysts_dir / "fundamentals.md"),
        },
        "research": {
            "bull": _read_text(research_dir / "bull.md"),
            "bear": _read_text(research_dir / "bear.md"),
            "manager": _read_text(research_dir / "manager.md"),
        },
        "trading": {
            "trader": _read_text(trading_dir / "trader.md"),
        },
        "risk": {
            "aggressive": _read_text(risk_dir / "aggressive.md"),
            "conservative": _read_text(risk_dir / "conservative.md"),
            "neutral": _read_text(risk_dir / "neutral.md"),
        },
        "portfolio": {
            "decision": _read_text(portfolio_dir / "decision.md"),
        },
    }

    portfolio_text = sections["portfolio"]["decision"] or ""
    decision, decision_summary = _classify_decision(portfolio_text)
    if decision == "UNKNOWN":
        trader_text = sections["trading"]["trader"] or ""
        decision, _ = _classify_decision(trader_text)

    raw_md = _read_text(path / "complete_report.md") or ""

    return {
        "report_id": meta["report_id"],
        "ticker": meta["ticker"],
        "generated_at": meta["generated_at"],
        "analysts": meta["analysts"],
        "has_complete_report": meta["has_complete_report"],
        "decision": decision,
        "decision_summary": decision_summary,
        "sections": sections,
        "raw_markdown": raw_md,
    }
