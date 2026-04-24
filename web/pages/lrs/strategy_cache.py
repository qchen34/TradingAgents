"""Local cache utilities for LRS Strategy dashboard.

Saves analysis snapshots to <app_root>/data/dashboard/strategy/{key}.json
where app_root is the cwd when Streamlit runs (TradingAgents/TradingAgents/).
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path


def _base() -> Path:
    p = Path(os.getcwd()) / "data" / "dashboard" / "strategy"
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

def save_figure(key: str, fig) -> None:
    """将 matplotlib figure 保存为 PNG（应在 st.pyplot 前调用）。"""
    import io
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
    buf.seek(0)
    (_base() / f"{key}.png").write_bytes(buf.read())


def figure_path(key: str) -> str | None:
    """返回已保存 PNG 的路径字符串，不存在则返回 None。"""
    p = _base() / f"{key}.png"
    return str(p) if p.exists() else None

