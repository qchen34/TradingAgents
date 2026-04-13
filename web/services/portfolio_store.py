from __future__ import annotations

import json
from pathlib import Path

PORTFOLIO_PATH = Path("data/portfolio.json")


def load_portfolio() -> list[dict]:
    if not PORTFOLIO_PATH.exists():
        return []
    try:
        return json.loads(PORTFOLIO_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_portfolio(rows: list[dict]) -> None:
    PORTFOLIO_PATH.parent.mkdir(parents=True, exist_ok=True)
    PORTFOLIO_PATH.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def upsert_position(ticker: str, quantity: float, buy_price: float) -> list[dict]:
    t = ticker.strip().upper()
    rows = load_portfolio()
    found = None
    for r in rows:
        if r.get("ticker") == t:
            found = r
            break
    if found is None:
        rows.append({"ticker": t, "quantity": quantity, "avg_cost": buy_price})
    else:
        old_q = float(found.get("quantity", 0.0))
        old_cost = float(found.get("avg_cost", 0.0))
        new_q = old_q + quantity
        if new_q <= 0:
            rows = [r for r in rows if r.get("ticker") != t]
        else:
            found["avg_cost"] = (old_q * old_cost + quantity * buy_price) / new_q
            found["quantity"] = new_q
    _save_portfolio(rows)
    return rows
