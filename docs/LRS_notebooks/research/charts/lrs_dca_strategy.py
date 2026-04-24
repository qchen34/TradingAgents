#!/usr/bin/env python3
"""LRS DCA strategy runner (with 4% idle cash yield on LRS cash).

Strategy:
- DCA: $2,000 on each January first trading day, up to 5 contributions
- Trading cost: $1.99 / side
- LRS idle cash yield: 4% annualized, compounded each trading day
- Windows: 2y / 3y / 5y / 10y / 15y

Outputs:
- Metrics markdown tables for five windows
- Equity PNG charts for each window (LRS DCA vs QQQ DCA vs TQQQ DCA)
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

import generate_charts as core

HERE = Path(__file__).resolve().parent


def run_dca_all_windows() -> list[dict]:
    """Run DCA backtest for all five windows."""
    return core.run_dca_all_periods()


def _plot_single_window_equity(row: dict, out_path: Path) -> None:
    idx = row["idx"]
    fig, ax = plt.subplots(figsize=(11, 4.6))
    ax.plot(idx, row["eq_lrs_dca"].values, color="#38bdf8", lw=1.8, label="LRS DCA")
    ax.plot(idx, row["eq_qqq_dca"].values, color="#a78bfa", lw=1.4, ls="--", label="QQQ DCA")
    ax.plot(idx, row["eq_tqq_dca"].values, color="#fb923c", lw=1.4, ls=":", label="TQQQ DCA")
    for d in row["contrib_dates"]:
        ax.axvline(d, color="#64748b", alpha=0.35, lw=0.85)
    ax.set_title(f"{row['label']} — DCA equity curves")
    ax.set_xlabel("Date")
    ax.set_ylabel("Portfolio ($)")
    ax.legend(loc="upper left", fontsize=8, ncol=3)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    core._apply_dark(fig, ax)
    fig.savefig(out_path, dpi=160, bbox_inches="tight", facecolor=core._DARK_BG)
    plt.close(fig)


def render_dca_charts(rows: list[dict], out_dir: Path = HERE) -> dict[str, str]:
    """Render DCA charts for all windows and return output file map."""
    outs: dict[str, str] = {}
    for row in rows:
        out = out_dir / f"dca_equity_{row['period_key']}.png"
        _plot_single_window_equity(row, out)
        outs[row["period_key"]] = str(out)
    return outs


def render_dca_markdown(rows: list[dict]) -> str:
    """Markdown: DCA five-window table."""
    return core.format_dca_markdown_tables(rows)


def main() -> None:
    rows = run_dca_all_windows()
    chart_paths = render_dca_charts(rows, HERE)
    print(render_dca_markdown(rows))
    print("\n---")
    print("Generated files:")
    for k, v in chart_paths.items():
        print(f"- {k}: {v}")


if __name__ == "__main__":
    main()

