#!/usr/bin/env python3
"""Headless TradingAgents analysis for GitHub Actions (no Rich / no prompts).

Reads configuration from CLI args and environment variables (for GitHub Variables).
Imports report helpers from cli.main without modifying that module.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

from cli.main import ANALYST_ORDER, save_report_to_disk
from cli.models import AnalystType
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

VALID_RESEARCH_DEPTHS = frozenset({1, 3, 5})


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is not None and v.strip() != "":
        return v
    return default


def _parse_analysts(raw: str) -> list[str]:
    r = raw.strip().lower()
    if r == "all":
        wanted = set(ANALYST_ORDER)
    else:
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        valid = {a.value for a in AnalystType}
        unknown = [p for p in parts if p not in valid]
        if unknown:
            raise SystemExit(f"Unknown analyst keys: {unknown}. Valid: {sorted(valid)}")
        wanted = set(parts)
    return [a for a in ANALYST_ORDER if a in wanted]


def _validate_date(date_str: str) -> str:
    try:
        d = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError as e:
        raise SystemExit(f"Invalid date {date_str!r}, use YYYY-MM-DD") from e
    if d > dt.date.today():
        raise SystemExit("Analysis date cannot be in the future")
    return date_str


def _build_config(args: argparse.Namespace) -> dict:
    if args.research_depth not in VALID_RESEARCH_DEPTHS:
        raise SystemExit(f"--research-depth must be one of {sorted(VALID_RESEARCH_DEPTHS)}")

    config = DEFAULT_CONFIG.copy()
    config["max_debate_rounds"] = args.research_depth
    config["max_risk_discuss_rounds"] = args.research_depth
    config["quick_think_llm"] = args.quick_model
    config["deep_think_llm"] = args.deep_model
    config["backend_url"] = args.backend_url
    config["llm_provider"] = args.llm_provider.lower()
    config["output_language"] = args.output_language

    config["google_thinking_level"] = args.google_thinking_level or None
    config["openai_reasoning_effort"] = args.openai_reasoning_effort or None
    config["anthropic_effort"] = args.anthropic_effort or None

    return config


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run TradingAgents analysis without interactive CLI.")
    p.add_argument(
        "--ticker",
        default=_env("SCHEDULE_TICKER"),
        help="Stock ticker (or SCHEDULE_TICKER)",
    )
    p.add_argument(
        "--date",
        default=_env("SCHEDULE_ANALYSIS_DATE"),
        help="Analysis date YYYY-MM-DD (or SCHEDULE_ANALYSIS_DATE)",
    )
    p.add_argument(
        "--output-dir",
        default=_env("SCHEDULE_OUTPUT_DIR"),
        help="Report output directory (or SCHEDULE_OUTPUT_DIR)",
    )
    p.add_argument(
        "--output-language",
        default=_env("SCHEDULE_OUTPUT_LANGUAGE", DEFAULT_CONFIG["output_language"]),
        help="or SCHEDULE_OUTPUT_LANGUAGE",
    )
    p.add_argument(
        "--analysts",
        default=_env("SCHEDULE_ANALYST_LIST", "all"),
        help="Comma-separated analyst keys or 'all' (or SCHEDULE_ANALYST_LIST)",
    )
    p.add_argument(
        "--research-depth",
        type=int,
        default=int(_env("SCHEDULE_RESEARCH_DEPTH", "1") or "1"),
        help="1, 3, or 5 (or SCHEDULE_RESEARCH_DEPTH)",
    )
    p.add_argument(
        "--llm-provider",
        default=_env("SCHEDULE_LLM_PROVIDER", DEFAULT_CONFIG["llm_provider"]),
        help="or SCHEDULE_LLM_PROVIDER",
    )
    p.add_argument(
        "--backend-url",
        default=_env("SCHEDULE_BACKEND_URL", DEFAULT_CONFIG["backend_url"]),
        help="or SCHEDULE_BACKEND_URL",
    )
    p.add_argument(
        "--quick-model",
        default=_env("SCHEDULE_QUICK_MODEL", DEFAULT_CONFIG["quick_think_llm"]),
        help="or SCHEDULE_QUICK_MODEL",
    )
    p.add_argument(
        "--deep-model",
        default=_env("SCHEDULE_DEEP_MODEL", DEFAULT_CONFIG["deep_think_llm"]),
        help="or SCHEDULE_DEEP_MODEL",
    )
    p.add_argument(
        "--openai-reasoning-effort",
        default=_env("SCHEDULE_OPENAI_REASONING_EFFORT"),
        help="or SCHEDULE_OPENAI_REASONING_EFFORT",
    )
    p.add_argument(
        "--google-thinking-level",
        default=_env("SCHEDULE_GOOGLE_THINKING_LEVEL"),
        help="or SCHEDULE_GOOGLE_THINKING_LEVEL",
    )
    p.add_argument(
        "--anthropic-effort",
        default=_env("SCHEDULE_ANTHROPIC_EFFORT"),
        help="or SCHEDULE_ANTHROPIC_EFFORT",
    )
    args = p.parse_args()

    if not args.ticker:
        p.error("--ticker or SCHEDULE_TICKER is required")
    if not args.date:
        p.error("--date or SCHEDULE_ANALYSIS_DATE is required")
    if not args.output_dir:
        p.error("--output-dir or SCHEDULE_OUTPUT_DIR is required")

    args.ticker = args.ticker.strip().upper()
    args.date = _validate_date(args.date.strip())
    args.output_dir = str(Path(args.output_dir).resolve())

    return args


def main() -> None:
    args = parse_args()
    selected = _parse_analysts(args.analysts)
    if not selected:
        raise SystemExit("No analysts selected after filtering")

    config = _build_config(args)
    graph = TradingAgentsGraph(selected, config=config, debug=False, callbacks=[])
    final_state, _signal = graph.propagate(args.ticker, args.date)

    out = Path(args.output_dir)
    save_report_to_disk(final_state, args.ticker, out)

    complete = out / "complete_report.md"
    if not complete.is_file():
        print(f"ERROR: expected report missing: {complete}", file=sys.stderr)
        sys.exit(1)
    print(f"OK: wrote {complete}")


if __name__ == "__main__":
    main()
