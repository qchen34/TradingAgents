#!/usr/bin/env python3
"""LRS lump-sum strategy runner (with 4% idle cash yield).

Strategy:
- Initial capital: $10,000 (lump sum)
- Trading cost: $1.99 / side
- Idle cash yield: 4% annualized, compounded each trading day
- Windows: 2y / 3y / 5y / 10y / 15y

Outputs:
- Metrics markdown table for five windows
- PNG charts for lump-sum strategy analysis
"""
from __future__ import annotations

from pathlib import Path

import generate_charts as core

HERE = Path(__file__).resolve().parent


def run_lump_all_windows() -> list[dict]:
    """Run lump-sum backtest for all five windows."""
    return [core.run_period(k) for k in core._PERIOD_ORDER]


def render_lump_charts(rows: list[dict], out_dir: Path = HERE) -> dict[str, str]:
    """Render lump-sum charts and return output file map."""
    paths = {
        "summary_table": str(out_dir / "lump_chart_a_summary.png"),
        "returns_cagr": str(out_dir / "lump_chart_b_returns.png"),
        "sharpe": str(out_dir / "lump_chart_c_sharpe.png"),
        "drawdown": str(out_dir / "lump_chart_d_drawdown.png"),
        "equity_5y": str(out_dir / "lump_chart_e_equity_5y.png"),
        "equity_10y_15y": str(out_dir / "lump_chart_equity_10y_15y.png"),
    }
    core.chart_a(rows, Path(paths["summary_table"]))
    core.chart_b(rows, Path(paths["returns_cagr"]))
    core.chart_c(rows, Path(paths["sharpe"]))
    core.chart_d(rows, Path(paths["drawdown"]))
    by_key = {r["period_key"]: r for r in rows}
    core.chart_e(by_key["5y"], Path(paths["equity_5y"]))
    core.chart_equity_10y_15y(rows, Path(paths["equity_10y_15y"]))
    return paths


def render_lump_markdown() -> str:
    """Markdown: LRS lump-sum five-window table."""
    return core.format_lrs_lump_five_window_markdown()


def main() -> None:
    rows = run_lump_all_windows()
    chart_paths = render_lump_charts(rows, HERE)
    print(render_lump_markdown())
    print("\n---")
    print("Generated files:")
    for k, v in chart_paths.items():
        print(f"- {k}: {v}")


if __name__ == "__main__":
    main()

