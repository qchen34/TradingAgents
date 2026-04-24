"""Local cache utilities for Wheel Strategy dashboard."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path


def _base() -> Path:
    p = Path(os.getcwd()) / "data" / "dashboard" / "wheel"
    p.mkdir(parents=True, exist_ok=True)
    return p


def save(key: str, data: dict) -> None:
    record = dict(data)
    record["_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with (_base() / f"{key}.json").open("w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2, default=str)


def load(key: str) -> dict | None:
    p = _base() / f"{key}.json"
    if not p.exists():
        return None
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

