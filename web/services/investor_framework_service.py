"""
个股详情页 — 大佬框架分析 v2.1（13 位逐人 Agent）
- quick：compact 框架 + 短 JSON
- deep：Per-Investor Playbook + 预计算 computed_context
"""
from __future__ import annotations

import importlib.util
import json
import math
import re
import statistics
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from langchain_core.messages import HumanMessage, SystemMessage

from web.services.stock_tracker_service import (
    _get_deep_llm,
    _msg_text,
    load_latest,
)

REPO_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = REPO_ROOT / "data" / "stock_tracker"
INVESTOR_JSON = DATA_DIR / "investor_analysis.json"
FRAMEWORKS_DIR = REPO_ROOT / "docs" / "investor-frameworks"
COMPACT_FRAMEWORK_PATH = FRAMEWORKS_DIR / "framework-prompt-compact.md"
MASTER_FRAMEWORK_PATH = FRAMEWORKS_DIR / "master-investors-framework.md"
MANIFEST_PATH = FRAMEWORKS_DIR / "manifest.json"
PLAYBOOKS_DIR = FRAMEWORKS_DIR / "investors"
PRECOMPUTE_SCRIPT = FRAMEWORKS_DIR / "scripts" / "precompute_context.py"

INVESTOR_SLUGS: dict[str, str] = {
    "Buffett": "buffett",
    "Klarman": "klarman",
    "Marks": "marks",
    "Druckenmiller": "druckenmiller",
    "PTJ": "ptj",
    "Dalio": "dalio",
    "Cathie Wood": "cathie_wood",
    "Ackman": "ackman",
    "Burry": "burry",
    "Asness": "asness",
    "Greenblatt": "greenblatt",
    "Loeb": "loeb",
    "Weinstein": "weinstein",
}

ANALYSIS_MODES = ("quick", "deep")

REQUIRED_INVESTORS: list[str] = [
    "Buffett",
    "Klarman",
    "Marks",
    "Druckenmiller",
    "PTJ",
    "Dalio",
    "Cathie Wood",
    "Ackman",
    "Burry",
    "Asness",
    "Greenblatt",
    "Loeb",
    "Weinstein",
]

_INVESTOR_ALIAS: dict[str, str] = {
    "warren buffett": "Buffett",
    "buffett": "Buffett",
    "seth klarman": "Klarman",
    "klarman": "Klarman",
    "howard marks": "Marks",
    "marks": "Marks",
    "stanley druckenmiller": "Druckenmiller",
    "druckenmiller": "Druckenmiller",
    "paul tudor jones": "PTJ",
    "ptj": "PTJ",
    "ray dalio": "Dalio",
    "dalio": "Dalio",
    "cathie wood": "Cathie Wood",
    "wood": "Cathie Wood",
    "bill ackman": "Ackman",
    "ackman": "Ackman",
    "michael burry": "Burry",
    "burry": "Burry",
    "cliff asness": "Asness",
    "asness": "Asness",
    "joel greenblatt": "Greenblatt",
    "greenblatt": "Greenblatt",
    "daniel loeb": "Loeb",
    "loeb": "Loeb",
    "stan weinstein": "Weinstein",
    "weinstein": "Weinstein",
}

_VERDICT_ALIASES: dict[str, str] = {
    "buy": "buy",
    "买入": "buy",
    "积极": "buy",
    "bullish": "buy",
    "watch": "watch",
    "观望": "watch",
    "中性": "watch",
    "neutral": "watch",
    "hold": "watch",
    "avoid": "avoid",
    "回避": "avoid",
    "谨慎": "avoid",
    "sell": "avoid",
    "bearish": "avoid",
}

MAX_LLM_WORKERS = 2
MAX_INVESTOR_RETRIES = 2

_COMPACT_CACHE: str | None = None
_INVESTOR_SECTIONS: dict[str, str] | None = None


@dataclass
class InvestorJob:
    job_id: str
    ticker: str
    mode: str
    status: str
    created_at: str
    updated_at: str = field(default_factory=lambda: _now_iso())
    progress: str = ""
    result: dict[str, Any] | None = None
    error: str | None = None


_INVESTOR_JOBS: dict[str, InvestorJob] = {}
_JOB_LOCK = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class InvestorAnalysisError(Exception):
    pass


class InvestorJobConflictError(Exception):
    pass


class TickerNotFoundError(Exception):
    pass


def _load_store() -> dict[str, Any]:
    if INVESTOR_JSON.exists():
        try:
            return json.loads(INVESTOR_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"schema_version": "2.1", "updated_at": None, "analyses": {}}


def _save_store(store: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    store["schema_version"] = "2.1"
    store["updated_at"] = _now_iso()
    INVESTOR_JSON.write_text(
        json.dumps(store, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _normalize_stored_ticker_record(ticker: str, raw: dict[str, Any]) -> dict[str, Any]:
    """统一 GET 输出：{ ticker, quick?, deep? }；兼容 v2.0 扁平结构。"""
    tk = ticker.upper()
    if "quick" in raw or "deep" in raw:
        return {
            "ticker": tk,
            "quick": raw.get("quick"),
            "deep": raw.get("deep"),
        }
    if "framework_scores" in raw:
        return {"ticker": tk, "quick": raw, "deep": None}
    return {"ticker": tk, "quick": None, "deep": None}


def get_investor_analysis(ticker: str) -> dict[str, Any] | None:
    store = _load_store()
    raw = store.get("analyses", {}).get(ticker.upper())
    if raw is None:
        return None
    return _normalize_stored_ticker_record(ticker, raw)


def save_investor_analysis(
    ticker: str, result: dict[str, Any], mode: str = "quick"
) -> None:
    if mode not in ANALYSIS_MODES:
        raise InvestorAnalysisError(f"无效 analysis mode: {mode}")
    store = _load_store()
    analyses = store.setdefault("analyses", {})
    tk = ticker.upper()
    bucket = analyses.get(tk)
    if bucket is None:
        analyses[tk] = {}
        bucket = analyses[tk]
    elif "framework_scores" in bucket:
        analyses[tk] = {"quick": bucket}
        bucket = analyses[tk]
    bucket[mode] = result
    _save_store(store)


def _load_compact_framework() -> str:
    global _COMPACT_CACHE
    if _COMPACT_CACHE is not None:
        return _COMPACT_CACHE
    if COMPACT_FRAMEWORK_PATH.exists():
        _COMPACT_CACHE = COMPACT_FRAMEWORK_PATH.read_text(encoding="utf-8")
    else:
        _COMPACT_CACHE = "（框架文档缺失）"
    return _COMPACT_CACHE


def _build_investor_sections() -> dict[str, str]:
    global _INVESTOR_SECTIONS
    if _INVESTOR_SECTIONS is not None:
        return _INVESTOR_SECTIONS
    text = _load_compact_framework()
    sections: dict[str, str] = {}
    for chunk in re.split(r"\n## ", text):
        chunk = chunk.strip()
        if not chunk or chunk.startswith("# 大佬框架"):
            continue
        lines = chunk.split("\n", 1)
        header = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        canon = _normalize_investor_name(header)
        if canon and canon in REQUIRED_INVESTORS:
            sections[canon] = f"## {header}\n{body}"
    _INVESTOR_SECTIONS = sections
    return sections


def _extract_investor_compact(investor: str) -> str:
    sections = _build_investor_sections()
    block = sections.get(investor)
    if block:
        return block
    return f"## {investor}\n（框架段落缺失，请按该投资风格的一般原则评估。）"


_MASTER_SECTIONS: dict[str, str] | None = None


def _build_master_sections() -> dict[str, str]:
    global _MASTER_SECTIONS
    if _MASTER_SECTIONS is not None:
        return _MASTER_SECTIONS
    sections: dict[str, str] = {}
    if MASTER_FRAMEWORK_PATH.exists():
        text = MASTER_FRAMEWORK_PATH.read_text(encoding="utf-8")
        for part in re.split(r"\n(?=## \d+\. )", text):
            if not part.strip().startswith("## "):
                continue
            header = part.split("\n", 1)[0]
            for inv in REQUIRED_INVESTORS:
                if inv == "PTJ" and "Paul Tudor Jones" in header:
                    sections[inv] = part.strip()
                    break
                if inv == "Cathie Wood" and "Cathie Wood" in header:
                    sections[inv] = part.strip()
                    break
                if inv == "Weinstein" and "Weinstein" in header:
                    sections[inv] = part.strip()
                    break
                if inv in header:
                    sections[inv] = part.strip()
                    break
    _MASTER_SECTIONS = sections
    return sections


def _load_investor_playbook(investor: str) -> str:
    slug = INVESTOR_SLUGS.get(investor, investor.lower().replace(" ", "_"))
    path = PLAYBOOKS_DIR / slug / "methodology.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    block = _build_master_sections().get(investor)
    if block:
        return f"# {investor} Playbook（fallback master）\n\n{block}"
    return _extract_investor_compact(investor)


def _run_precompute(
    ticker: str, item: dict[str, Any], investor: str
) -> dict[str, Any]:
    slug = INVESTOR_SLUGS.get(investor, "")
    if not PRECOMPUTE_SCRIPT.exists():
        return {"ticker": ticker.upper(), "note": "precompute script missing"}
    spec = importlib.util.spec_from_file_location(
        "precompute_context", PRECOMPUTE_SCRIPT
    )
    if spec is None or spec.loader is None:
        return {"ticker": ticker.upper(), "note": "precompute load failed"}
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.precompute(ticker, item, slug)  # type: ignore[attr-defined]


def _find_ticker_item(ticker: str) -> dict[str, Any]:
    latest = load_latest()
    tk = ticker.upper()
    for item in latest.get("tickers") or []:
        if (item.get("ticker") or "").upper() == tk:
            return item
    raise TickerNotFoundError(
        f"未找到 {tk} 的追踪数据，请先在「个股追踪」页面刷新数据。"
    )


def _normalize_investor_name(raw: str) -> str | None:
    key = (raw or "").strip().lower()
    if key in _INVESTOR_ALIAS:
        return _INVESTOR_ALIAS[key]
    for canon in REQUIRED_INVESTORS:
        if canon.lower() == key or canon.lower() in key:
            return canon
    return None


def _normalize_verdict(raw: Any) -> str:
    key = str(raw or "").strip().lower()
    if key in _VERDICT_ALIASES:
        return _VERDICT_ALIASES[key]
    for alias, canon in _VERDICT_ALIASES.items():
        if alias in key:
            return canon
    raise InvestorAnalysisError(f"无效 verdict: {raw}")


def build_stock_snapshot_prompt(ticker: str, item: dict[str, Any]) -> str:
    tech = item.get("technical") or {}
    fund = item.get("fundamental") or {}
    llm = item.get("llm") or {}
    tb = tech.get("trend_buy") if isinstance(tech.get("trend_buy"), dict) else {}
    eps_h = (fund.get("eps_history") or [])[:4]
    eps_str = ", ".join(
        f"{e.get('date', '?')}: {e.get('surprise_pct', 'N/A')}%"
        for e in eps_h
    )
    qrev = (fund.get("quarterly_revenue") or [])[:4]
    qrev_str = ", ".join(
        f"{r.get('date', '?')}: QoQ {r.get('qoq_pct', 'N/A')}%"
        for r in qrev
    )
    catalysts = llm.get("catalysts") or []
    cat_str = "; ".join(str(c) for c in catalysts[:4]) if catalysts else "无"

    return f"""请分析股票 {ticker.upper()}（{item.get('name', '')}）。

【技术面】
close={tech.get('close')} change_pct={tech.get('change_pct')}%
ma50={tech.get('ma50')} ma150={tech.get('ma150')} ma200={tech.get('ma200')}
pct_vs_ma150={tech.get('pct_vs_ma150')}% ma150_slope_4w={tech.get('ma150_slope_4w')}%
rsi14={tech.get('rsi14')} rs_slope_3m={tech.get('rs_slope_3m')} score={tech.get('score')}/9
macd_hist={tech.get('macd_hist')} volume_vs_ma20={tech.get('volume_vs_ma20')}
golden_cross={tech.get('golden_cross_label')} extension={tech.get('extension_label')}
trend_buy_verdict={tb.get('verdict')} trend_buy_summary={tb.get('one_liner', '')}

【基本面】
pe_ttm={fund.get('pe_ttm')} industry_pe={fund.get('industry_pe_avg')} ({fund.get('industry_label', '')})
revenue_growth_yoy={fund.get('revenue_growth_yoy')}% gross_margin={fund.get('gross_margin')}%
fcf={fund.get('free_cashflow')} market_cap={fund.get('market_cap')}
analyst_target={fund.get('analyst_target')} rating={fund.get('analyst_rating')}
eps_beats=[{eps_str}] qrev=[{qrev_str}]

【已有 Weinstein/阶段 LLM 输出（仅作对照，勿照抄为结论）】
stage_label={llm.get('stage_label')} action_type={llm.get('action_type')}
confidence={llm.get('confidence')} stop_reference={llm.get('stop_reference')}
stage_narrative={llm.get('stage_narrative', '')[:200]}
catalysts={cat_str}"""


def build_single_investor_user_prompt(
    ticker: str,
    item: dict[str, Any],
    investor: str,
    mode: str = "quick",
    retry_hint: str | None = None,
    computed_context: dict[str, Any] | None = None,
) -> str:
    snapshot = build_stock_snapshot_prompt(ticker, item)
    tech = item.get("technical") or {}
    close = tech.get("close")
    close_hint = (
        f"\n当前股价 close={close}（美元）。ideal_price、max_chase_price、stop_loss.price "
        "必须是**纯数字 JSON number**（可带小数），禁止 null/N/A/文字/货币符号；"
        "须满足 stop_loss.price < ideal_price <= max_chase_price。"
        if close is not None
        else ""
    )
    computed_block = ""
    if computed_context:
        computed_block = (
            "\n【computed_context（脚本预计算，事实参考）】\n"
            + json.dumps(computed_context, ensure_ascii=False, indent=2)
        )
    retry_block = f"\n\n【上次输出未通过校验，请修正】\n{retry_hint}\n" if retry_hint else ""

    base_fields = f"""- investor: "{investor}"（必须与上述名称完全一致）
- score: 1-5 整数
- verdict: "buy" | "watch" | "avoid"（仅此三值）
- key_reason: string, 中文, <=80字
- concern: string, 中文, <=80字
- entry: {{ ideal_price, max_chase_price, trigger_condition, note }}
- stop_loss: {{ price, pct_from_ideal, logic }}
- holding_period: {{ range, rationale }}"""

    deep_fields = """
- investment_thesis: string, 中文, 200-500字
- bull_case: string, 中文, <=200字
- bear_case: string, 中文, <=200字
- catalysts: [string, 2-4条]
- position_sizing: string, 中文, <=120字
- analysis_steps_done: [string, 3-6条，对应 Playbook 步骤摘要]"""

    fields = base_fields + (deep_fields if mode == "deep" else "")
    mode_note = (
        "按 Playbook 执行清单逐步分析，再输出 JSON。"
        if mode == "deep"
        else "保持简洁。"
    )

    return f"""{snapshot}
{close_hint}
{computed_block}

你仅代表 **{investor}** 这一投资框架进行分析。不得引用、模拟或评判其他投资风格。
{mode_note}
数据不足时在 concern 中说明，仍须给出该框架下的买/止损/持有建议（价格仍须为数字）。

输出单个 JSON 对象（非数组），字段：
{fields}

要求：纯 JSON，无 markdown 围栏，无额外文字。{retry_block}"""


def _parse_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        return json.loads(m.group(0))
    raise ValueError("no JSON object in model output")


_NON_NUMERIC_PRICE = frozenset(
    {"n/a", "na", "none", "null", "—", "-", "unknown", "tbd", "无", "暂无"}
)


def _coerce_price(
    raw: Any,
    *,
    close: float | None = None,
    fallback_ratio: float | None = None,
) -> float | None:
    if raw is None or raw == "":
        if close is not None and close > 0 and fallback_ratio is not None:
            return round(close * fallback_ratio, 2)
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        v = float(raw)
        if math.isfinite(v) and v > 0:
            return round(v, 2)
        return None
    s = str(raw).strip()
    if not s or s.lower() in _NON_NUMERIC_PRICE:
        if close is not None and close > 0 and fallback_ratio is not None:
            return round(close * fallback_ratio, 2)
        return None
    s = (
        s.replace(",", "")
        .replace("$", "")
        .replace("USD", "")
        .replace("usd", "")
        .replace("美元", "")
        .strip()
    )
    m = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", s)
    if m:
        v = float(m.group(0))
        if math.isfinite(v) and v > 0:
            return round(v, 2)
    if close is not None and close > 0 and fallback_ratio is not None:
        return round(close * fallback_ratio, 2)
    return None


def _extract_trade_payload(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    entry = data.get("entry") if isinstance(data.get("entry"), dict) else {}
    stop = data.get("stop_loss") if isinstance(data.get("stop_loss"), dict) else {}

    for key in ("ideal_price", "ideal_buy", "ideal_entry", "buy_price", "target_entry"):
        if "ideal_price" not in entry and key in data:
            entry["ideal_price"] = data[key]
        if "ideal_price" not in entry and key in entry:
            entry["ideal_price"] = entry[key]

    for key in ("max_chase_price", "max_chase", "max_price", "chase_price"):
        if "max_chase_price" not in entry and key in data:
            entry["max_chase_price"] = data[key]
        if "max_chase_price" not in entry and key in entry:
            entry["max_chase_price"] = entry[key]

    for key in ("price", "stop_price", "stop"):
        if "price" not in stop and key in stop:
            stop["price"] = stop[key]
        if "price" not in stop and key in data:
            val = data[key]
            if isinstance(val, (int, float, str)):
                stop["price"] = val
            elif isinstance(val, dict) and "price" in val:
                stop["price"] = val["price"]

    if "price" not in stop and isinstance(data.get("stop_loss"), (int, float, str)):
        stop["price"] = data["stop_loss"]

    return entry, stop


def _repair_price_order(
    ideal: float, max_chase: float, stop_p: float
) -> tuple[float, float, float]:
    if ideal <= 0:
        raise InvestorAnalysisError("ideal_price 须为正数")
    if max_chase < ideal:
        max_chase = round(ideal * 1.03, 2)
    if stop_p >= ideal:
        stop_p = round(ideal * 0.92, 2)
    if not (stop_p < ideal <= max_chase):
        raise InvestorAnalysisError(
            f"价格关系无效：止损({stop_p}) < 理想买入({ideal}) <= 最高追价({max_chase})"
        )
    return ideal, max_chase, stop_p


def _normalize_trade_fields(
    entry: dict[str, Any],
    stop: dict[str, Any],
    close: float | None,
    investor: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    derived_note = ""
    raw_ideal = entry.get("ideal_price")
    raw_max = entry.get("max_chase_price")
    raw_stop = stop.get("price")

    ideal = _coerce_price(raw_ideal, close=close, fallback_ratio=0.92)
    max_chase = _coerce_price(raw_max, close=close, fallback_ratio=1.0)
    stop_p = _coerce_price(raw_stop, close=close, fallback_ratio=0.85)

    if ideal is None or max_chase is None or stop_p is None:
        raise InvestorAnalysisError(
            f"{investor or '框架'} entry/stop_loss 价格须为数字"
            f"（ideal={raw_ideal!r}, max={raw_max!r}, stop={raw_stop!r}）"
        )

    for raw in (raw_ideal, raw_max, raw_stop):
        if raw is None or str(raw).strip().lower() in _NON_NUMERIC_PRICE:
            derived_note = "部分价格由现价推算"
            break

    ideal, max_chase, stop_p = _repair_price_order(ideal, max_chase, stop_p)

    if close is not None and close > 0:
        if max_chase < close * 0.5 or ideal > close * 1.5:
            raise InvestorAnalysisError("买入价相对现价偏离过大")

    pct_raw = stop.get("pct_from_ideal")
    pct_from_ideal: float | None = None
    if pct_raw is not None and pct_raw != "":
        try:
            pct_from_ideal = float(pct_raw)
        except (TypeError, ValueError):
            pct_from_ideal = None
    if pct_from_ideal is None and ideal != 0:
        pct_from_ideal = round((stop_p - ideal) / ideal * 100, 2)

    note = str(entry.get("note", ""))[:200]
    if derived_note and derived_note not in note:
        note = f"{derived_note}；{note}" if note else derived_note

    norm_entry = {
        "ideal_price": ideal,
        "max_chase_price": max_chase,
        "trigger_condition": str(entry.get("trigger_condition", ""))[:200],
        "note": note,
    }
    norm_stop = {
        "price": stop_p,
        "pct_from_ideal": pct_from_ideal if pct_from_ideal is not None else 0.0,
        "logic": str(stop.get("logic", ""))[:300],
    }
    return norm_entry, norm_stop


def _validate_single_row(
    data: dict[str, Any], investor: str, close: float | None
) -> dict[str, Any]:
    inv = _normalize_investor_name(str(data.get("investor", investor)))
    if inv != investor:
        data["investor"] = investor
    else:
        data["investor"] = inv

    verdict = _normalize_verdict(data.get("verdict"))

    try:
        sc_int = int(float(data.get("score")))
    except (TypeError, ValueError) as exc:
        raise InvestorAnalysisError(f"{investor} score 无效") from exc
    if sc_int < 1 or sc_int > 5:
        raise InvestorAnalysisError(f"{investor} score 须在 1-5")

    entry, stop = _extract_trade_payload(data)
    entry, stop = _normalize_trade_fields(entry, stop, close, investor)
    hp = data.get("holding_period") or {}

    return {
        "investor": investor,
        "score": sc_int,
        "verdict": verdict,
        "key_reason": str(data.get("key_reason", ""))[:300],
        "concern": str(data.get("concern", ""))[:300],
        "entry": entry,
        "stop_loss": stop,
        "holding_period": {
            "range": str(hp.get("range", ""))[:64],
            "rationale": str(hp.get("rationale", ""))[:300],
        },
    }


def _validate_single_row_deep(
    data: dict[str, Any], investor: str, close: float | None
) -> dict[str, Any]:
    row = _validate_single_row(data, investor, close)
    catalysts = data.get("catalysts")
    if not isinstance(catalysts, list):
        catalysts = []
    steps = data.get("analysis_steps_done")
    if not isinstance(steps, list):
        steps = []
    row["investment_thesis"] = str(data.get("investment_thesis", ""))[:800]
    row["bull_case"] = str(data.get("bull_case", ""))[:400]
    row["bear_case"] = str(data.get("bear_case", ""))[:400]
    row["catalysts"] = [str(c)[:120] for c in catalysts[:4]]
    row["position_sizing"] = str(data.get("position_sizing", ""))[:200]
    row["analysis_steps_done"] = [str(s)[:120] for s in steps[:6]]
    return row


def _build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"buy": 0, "watch": 0, "avoid": 0}
    for row in rows:
        v = row.get("verdict", "watch")
        if v in counts:
            counts[v] += 1

    max_count = max(counts.values())
    top = [k for k, v in counts.items() if v == max_count]
    if len(top) > 1:
        verdict = "watch"
        tie_note = "（平票，显示为观望）"
    else:
        verdict = top[0]
        tie_note = ""

    verdict_summary = (
        f"{counts['buy']} 位买入、{counts['watch']} 位观望、{counts['avoid']} 位回避"
        f"（按各框架独立 verdict 计票，非加权）{tie_note}"
    )

    ideals = [float(r["entry"]["ideal_price"]) for r in rows]
    ideals_sorted = sorted(ideals)
    median = round(statistics.median(ideals_sorted), 2)

    seen_risks: set[str] = set()
    key_risks: list[str] = []
    for row in sorted(rows, key=lambda x: x.get("score", 3)):
        c = (row.get("concern") or "").strip()
        if c and c not in seen_risks:
            seen_risks.add(c)
            key_risks.append(c[:120])
        if len(key_risks) >= 4:
            break

    return {
        "verdict_mode": "plurality",
        "verdict": verdict,
        "verdict_counts": counts,
        "verdict_summary": verdict_summary,
        "ideal_price_median": median,
        "ideal_price_range": [ideals_sorted[0], ideals_sorted[-1]],
        "key_risks": key_risks,
    }


def assemble_v2_result(
    ticker: str,
    rows: list[dict[str, Any]],
    source_updated_at: str | None,
    item: dict[str, Any],
    mode: str = "quick",
) -> dict[str, Any]:
    order = {name: idx for idx, name in enumerate(REQUIRED_INVESTORS)}
    rows_sorted = sorted(rows, key=lambda x: order.get(x["investor"], 99))
    summary = _build_summary(rows_sorted)

    tech = item.get("technical") or {}
    fund = item.get("fundamental") or {}
    llm = item.get("llm") or {}
    close = tech.get("close")
    try:
        close_f = float(close) if close is not None else None
    except (TypeError, ValueError):
        close_f = None

    out: dict[str, Any] = {
        "ticker": ticker.upper(),
        "analyzed_at": _now_iso(),
        "source_updated_at": source_updated_at,
        "analysis_mode": mode,
        "framework_version": "2.1-deep" if mode == "deep" else "2.0",
        "data_snapshot": {
            "close": close_f,
            "stage_label": llm.get("stage_label"),
            "pe_ttm": fund.get("pe_ttm"),
            "trend_buy_verdict": (tech.get("trend_buy") or {}).get("verdict")
            if isinstance(tech.get("trend_buy"), dict)
            else None,
        },
        "summary": summary,
        "framework_scores": rows_sorted,
    }
    if mode == "deep":
        out["playbook_manifest_version"] = "1.0"
    return out


def run_single_investor_analysis(
    ticker: str,
    item: dict[str, Any],
    investor: str,
    close: float | None,
    mode: str = "quick",
    retry_hint: str | None = None,
) -> dict[str, Any]:
    if mode == "deep":
        playbook = _load_investor_playbook(investor)
        computed = _run_precompute(ticker, item, investor)
        system = (
            f"你是投资分析助手。你**只**使用下列 {investor} 的深度 Playbook 评估股票，"
            "须按 Playbook 步骤执行，不得扮演其他投资风格。\n\n"
            + playbook
        )
        user = build_single_investor_user_prompt(
            ticker,
            item,
            investor,
            mode="deep",
            retry_hint=retry_hint,
            computed_context=computed,
        )
        validate_fn = _validate_single_row_deep
    else:
        system = (
            f"你是投资分析助手。你**只**使用下列 {investor} 框架评估股票，"
            "不得扮演其他投资风格。数据不足时在 concern 中说明。\n\n"
            + _extract_investor_compact(investor)
        )
        user = build_single_investor_user_prompt(
            ticker, item, investor, mode="quick", retry_hint=retry_hint
        )
        validate_fn = _validate_single_row

    llm = _get_deep_llm()
    resp = llm.invoke(
        [SystemMessage(content=system), HumanMessage(content=user)],
    )
    raw = _msg_text(resp)
    parsed = _parse_json_object(raw)
    return validate_fn(parsed, investor, close)


def run_investor_framework_analysis_v2(
    ticker: str,
    item: dict[str, Any],
    source_updated_at: str | None,
    mode: str = "quick",
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict[str, Any]:
    if mode not in ANALYSIS_MODES:
        raise InvestorAnalysisError(f"无效 mode: {mode}")
    tech = item.get("technical") or {}
    close = tech.get("close")
    try:
        close_f = float(close) if close is not None else None
    except (TypeError, ValueError):
        close_f = None

    total = len(REQUIRED_INVESTORS)
    completed = 0
    progress_lock = threading.Lock()
    rows_by_investor: dict[str, dict[str, Any]] = {}
    first_error: list[str] = []

    def _run_one(investor: str) -> None:
        last_err: Exception | None = None
        retry_hint: str | None = None
        for attempt in range(MAX_INVESTOR_RETRIES + 1):
            try:
                row = run_single_investor_analysis(
                    ticker,
                    item,
                    investor,
                    close_f,
                    mode=mode,
                    retry_hint=retry_hint,
                )
                with progress_lock:
                    rows_by_investor[investor] = row
                return
            except Exception as exc:
                last_err = exc
                retry_hint = str(exc)
        with progress_lock:
            if not first_error:
                first_error.append(f"{investor}: {last_err}")

    def _report_done(investor: str) -> None:
        nonlocal completed
        with progress_lock:
            completed += 1
            if on_progress:
                on_progress(completed, total, investor)

    with ThreadPoolExecutor(max_workers=MAX_LLM_WORKERS) as pool:
        futures = {
            pool.submit(_run_one, inv): inv for inv in REQUIRED_INVESTORS
        }
        for fut in as_completed(futures):
            inv = futures[fut]
            fut.result()
            _report_done(inv)

    if first_error:
        raise InvestorAnalysisError(
            f"部分框架分析失败: {first_error[0]}"
        )

    missing = [i for i in REQUIRED_INVESTORS if i not in rows_by_investor]
    if missing:
        raise InvestorAnalysisError(f"缺少框架评分: {', '.join(missing)}")

    rows = [rows_by_investor[i] for i in REQUIRED_INVESTORS]
    return assemble_v2_result(ticker, rows, source_updated_at, item, mode=mode)


def _running_job_for_ticker(ticker: str) -> InvestorJob | None:
    tk = ticker.upper()
    with _JOB_LOCK:
        for job in _INVESTOR_JOBS.values():
            if job.ticker == tk and job.status == "running":
                return job
    return None


def _update_job_progress(job_id: str, text: str) -> None:
    with _JOB_LOCK:
        if job_id in _INVESTOR_JOBS:
            _INVESTOR_JOBS[job_id].progress = text
            _INVESTOR_JOBS[job_id].updated_at = _now_iso()


def _run_investor_job(job_id: str, ticker: str, mode: str = "quick") -> None:
    try:
        _update_job_progress(job_id, "① 加载追踪快照")

        latest = load_latest()
        source_updated_at = latest.get("updated_at")
        item = _find_ticker_item(ticker)
        mode_label = "深度" if mode == "deep" else "快速"

        def on_progress(done: int, total: int, investor: str) -> None:
            _update_job_progress(
                job_id, f"② {done}/{total} · {investor}（{mode_label}）"
            )

        _update_job_progress(
            job_id, f"② 0/{len(REQUIRED_INVESTORS)} · 准备中（{mode_label}）"
        )

        result = run_investor_framework_analysis_v2(
            ticker,
            item,
            source_updated_at,
            mode=mode,
            on_progress=on_progress,
        )
        save_investor_analysis(ticker, result, mode=mode)

        with _JOB_LOCK:
            if job_id in _INVESTOR_JOBS:
                j = _INVESTOR_JOBS[job_id]
                j.status = "completed"
                j.updated_at = _now_iso()
                j.progress = "③ 完成"
                j.result = {
                    "ticker": ticker.upper(),
                    "analyzed_at": result["analyzed_at"],
                    "mode": mode,
                }
    except Exception as exc:
        with _JOB_LOCK:
            if job_id in _INVESTOR_JOBS:
                j = _INVESTOR_JOBS[job_id]
                j.status = "failed"
                j.updated_at = _now_iso()
                j.error = str(exc)
                j.progress = "failed"


def create_investor_analysis_job(ticker: str, mode: str = "quick") -> InvestorJob:
    tk = ticker.upper().strip()
    if not tk:
        raise InvestorAnalysisError("ticker 不能为空")
    if mode not in ANALYSIS_MODES:
        raise InvestorAnalysisError(f"无效 mode: {mode}")

    existing = _running_job_for_ticker(tk)
    if existing is not None:
        raise InvestorJobConflictError(
            f"{tk} 已有分析任务进行中（job_id={existing.job_id}）"
        )

    _find_ticker_item(tk)

    job_id = uuid.uuid4().hex
    job = InvestorJob(
        job_id=job_id,
        ticker=tk,
        mode=mode,
        status="running",
        created_at=_now_iso(),
        progress="queued",
    )
    with _JOB_LOCK:
        _INVESTOR_JOBS[job_id] = job
    th = threading.Thread(
        target=_run_investor_job, args=(job_id, tk, mode), daemon=True
    )
    th.start()
    return job


def get_investor_job(job_id: str) -> InvestorJob | None:
    with _JOB_LOCK:
        return _INVESTOR_JOBS.get(job_id)


def serialize_investor_job(job: InvestorJob) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "ticker": job.ticker,
        "mode": job.mode,
        "status": job.status,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "progress": job.progress,
        "result": job.result,
        "error": job.error,
    }
