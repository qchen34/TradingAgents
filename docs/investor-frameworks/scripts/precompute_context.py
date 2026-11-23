#!/usr/bin/env python3
"""为深度大佬分析预计算结构化事实（供 LLM 引用，非最终结论）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _f(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def precompute(ticker: str, item: dict[str, Any], slug: str = "") -> dict[str, Any]:
    tech = item.get("technical") or {}
    fund = item.get("fundamental") or {}
    llm = item.get("llm") or {}
    tb = tech.get("trend_buy") if isinstance(tech.get("trend_buy"), dict) else {}

    close = _f(tech.get("close"))
    ma50 = _f(tech.get("ma50"))
    ma150 = _f(tech.get("ma150"))
    pe = _f(fund.get("pe_ttm"))
    ind_pe = _f(fund.get("industry_pe_avg"))

    pe_premium_pct = None
    if pe is not None and ind_pe is not None and ind_pe > 0:
        pe_premium_pct = round((pe / ind_pe - 1) * 100, 1)

    pct_vs_ma150 = _f(tech.get("pct_vs_ma150"))
    suggested_stop_ma150 = ma150

    ideal_hint = None
    max_chase_hint = None
    if close is not None and close > 0:
        ideal_hint = round(close * 0.95, 2)
        max_chase_hint = round(close * 1.02, 2)

    out: dict[str, Any] = {
        "ticker": ticker.upper(),
        "investor_slug": slug,
        "close": close,
        "ma50": ma50,
        "ma150": ma150,
        "pct_vs_ma150": pct_vs_ma150,
        "pe_ttm": pe,
        "industry_pe_avg": ind_pe,
        "pe_premium_vs_industry_pct": pe_premium_pct,
        "trend_buy_verdict": tb.get("verdict"),
        "stage_label": llm.get("stage_label"),
        "stop_reference_llm": _f(llm.get("stop_reference")),
        "suggested_stop_ma150": suggested_stop_ma150,
        "ideal_price_hint": ideal_hint,
        "max_chase_price_hint": max_chase_hint,
        "note": "以上为脚本参考区间，最终买卖价须由你按 Playbook 论证后写入 JSON 数字字段",
    }
    return out


def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: precompute_context.py <path-to-item-json>"}))
        sys.exit(1)
    item = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))  # type: ignore[name-defined]
    ticker = item.get("ticker", "UNK")
    slug = sys.argv[2] if len(sys.argv) > 2 else ""
    print(json.dumps(precompute(ticker, item, slug), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
