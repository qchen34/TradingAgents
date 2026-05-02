"""Local cache utilities for Wheel Strategy dashboard/history."""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any
from pathlib import Path
import uuid


def _base() -> Path:
    p = Path(os.getcwd()) / "data" / "dashboard" / "wheel"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _history_base() -> Path:
    p = Path(os.getcwd()) / "data" / "dashboard" / "wheel_history"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _index_path() -> Path:
    return _history_base() / "index.json"


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def save(key: str, data: dict) -> None:
    record = dict(data)
    record["_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _write_json(_base() / f"{key}.json", record)


def load(key: str) -> dict | None:
    return _read_json(_base() / f"{key}.json", None)


def save_report(report: dict, chart_pngs: dict[str, bytes] | None = None) -> str:
    """Persist one report under wheel_history and update index."""
    report_id = str(report.get("report_id") or f"{datetime.now().strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:6]}")
    style = str(report.get("style", "unknown"))
    ticker = str(report.get("ticker", "unknown"))
    run_at = str(report.get("run_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    folder = _history_base() / f"{report_id}_{style}_{ticker}"
    folder.mkdir(parents=True, exist_ok=True)

    _write_json(folder / "meta.json", report.get("meta", {}))
    _write_json(folder / "series.json", report.get("series", {}))
    _write_json(folder / "trades.json", report.get("trades", []))
    _write_json(folder / "metrics.json", report.get("metrics", {}))
    charts_dir = folder / "charts"
    chart_files: dict[str, str] = {}
    if chart_pngs:
        for name, png_bytes in chart_pngs.items():
            fname = f"{name}.png"
            _write_bytes(charts_dir / fname, png_bytes)
            chart_files[name] = str(charts_dir / fname)

    index = _read_json(_index_path(), [])
    index = [x for x in index if x.get("report_id") != report_id]
    index.insert(
        0,
        {
            "report_id": report_id,
            "style": style,
            "ticker": ticker,
            "run_at": run_at,
            "start": report.get("meta", {}).get("start"),
            "end": report.get("meta", {}).get("end"),
            "engine_version": report.get("meta", {}).get("engine_version"),
            "rule_version": report.get("meta", {}).get("rule_version"),
            "path": str(folder),
            "charts": chart_files,
            "total_return": report.get("metrics", {}).get("total_return"),
            "sharpe": report.get("metrics", {}).get("sharpe"),
            "max_dd": report.get("metrics", {}).get("max_dd"),
        },
    )
    _write_json(_index_path(), index)
    return report_id


def list_reports(style: str | None = None, ticker: str | None = None) -> list[dict]:
    rows = _read_json(_index_path(), [])
    out = []
    for r in rows:
        if style and r.get("style") != style:
            continue
        if ticker and str(r.get("ticker", "")).upper() != ticker.upper():
            continue
        out.append(r)
    return out


def load_report(report_id: str) -> dict | None:
    rows = _read_json(_index_path(), [])
    target = next((r for r in rows if r.get("report_id") == report_id), None)
    if not target:
        return None
    folder = Path(str(target.get("path", "")))
    if not folder.exists():
        return None
    return {
        "report_id": report_id,
        "meta": _read_json(folder / "meta.json", {}),
        "series": _read_json(folder / "series.json", {}),
        "trades": _read_json(folder / "trades.json", []),
        "metrics": _read_json(folder / "metrics.json", {}),
        "charts": target.get("charts", {}),
    }

