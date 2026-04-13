from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DASHBOARD_ROOT = Path("data/dashboard")
HISTORY_DIR = DASHBOARD_ROOT / "history"
LATEST_PATH = DASHBOARD_ROOT / "latest.json"


def _ensure_dirs() -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def save_latest(payload: dict[str, Any]) -> None:
    """写入最新仪表盘快照（供冷启动优先读取）。"""
    DASHBOARD_ROOT.mkdir(parents=True, exist_ok=True)
    LATEST_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_latest() -> dict[str, Any] | None:
    if not LATEST_PATH.is_file():
        return None
    try:
        return json.loads(LATEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def append_history(payload: dict[str, Any]) -> Path:
    """按 UTC 时间戳写入一条历史快照。"""
    _ensure_dirs()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = HISTORY_DIR / f"{ts}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
