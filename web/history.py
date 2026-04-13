"""Scan local reports directories for Streamlit history sidebar."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List


def _parse_folder_name(name: str) -> tuple[str, str]:
    """From ``TICKER_YYYYMMDD`` return (ticker, analysis_date or '—')."""
    if "_" not in name:
        return name, "—"
    i = name.rfind("_")
    ticker, suf = name[:i], name[i + 1 :]
    if suf.isdigit() and len(suf) == 8:
        return ticker.upper(), f"{suf[:4]}-{suf[4:6]}-{suf[6:8]}"
    return name, "—"


@dataclass
class ReportRun:
    """One analysis output folder under reports/."""

    path: Path
    name: str
    mtime: float
    has_complete: bool

    @property
    def status(self) -> str:
        return "已完成" if self.has_complete else "部分"

    def label(self) -> str:
        from datetime import datetime

        ticker, analysis_date = _parse_folder_name(self.name)
        ts = datetime.fromtimestamp(self.mtime).strftime("%Y-%m-%d %H:%M")
        # ticker、分析日、目录修改时间、目录名、完成状态
        return (
            f"{ticker} · run {ts} · dir `{self.name}` · analysis {analysis_date} · {self.status}"
        )


def list_report_runs(reports_root: str | Path = "reports") -> List[ReportRun]:
    root = Path(reports_root)
    if not root.is_dir():
        return []
    runs: List[ReportRun] = []
    for p in root.iterdir():
        if not p.is_dir():
            continue
        if p.name.startswith("."):
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        complete = (p / "complete_report.md").is_file()
        runs.append(
            ReportRun(path=p.resolve(), name=p.name, mtime=st.st_mtime, has_complete=complete)
        )
    runs.sort(key=lambda r: r.mtime, reverse=True)
    return runs
