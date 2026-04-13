from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def now_et() -> datetime:
    return datetime.now(ET)


def is_market_open_et(ts: datetime | None = None) -> bool:
    t = ts or now_et()
    if t.weekday() >= 5:
        return False
    return time(9, 30) <= t.time() <= time(16, 0)


def market_status_text(ts: datetime | None = None) -> str:
    t = ts or now_et()
    return "盘中" if is_market_open_et(t) else "盘后/休市"


def format_et(ts: datetime | None = None) -> str:
    t = ts or now_et()
    return t.strftime("%Y-%m-%d %H:%M:%S ET")
