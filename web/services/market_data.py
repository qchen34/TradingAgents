from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yfinance as yf

from web.services.dashboard_store import append_history, load_latest, save_latest
from web.services.dashboard_llm import build_llm_config, enrich_news_opinions, generate_market_digest
from web.services.time_utils import format_et, market_status_text, now_et

INDEX_TICKERS = {
    "SPY": "S&P 500 (SPY)",
    "QQQ": "Nasdaq 100 (QQQ)",
    "DIA": "Dow Jones (DIA)",
    "^VIX": "VIX",
}

INDEX_SUBTITLE_CN: dict[str, str] = {
    "SPY": "标普500指数 ETF",
    "QQQ": "纳斯达克100指数 ETF",
    "DIA": "道琼斯工业平均指数 ETF",
    "^VIX": "标普500波动率指数（恐慌指数）",
}

SECTOR_PROXIES = ["XLK", "SOXX", "XLC", "QQQ"]

SECTOR_SUBTITLE_CN: dict[str, str] = {
    "XLK": "信息技术板块 ETF",
    "SOXX": "半导体板块 ETF",
    "XLC": "通信服务板块 ETF",
    "QQQ": "纳斯达克100指数 ETF",
}

# Yahoo 可交易代理：美债收益率曲线、美元、通胀保值 ETF（非官方 CPI）
MACRO_ENTRIES: list[tuple[str, str, str]] = [
    ("^IRX", "美国13周国债收益率", "短期无风险利率锚，影响资金成本预期。"),
    ("^FVX", "美国5年期国债收益率", "中期利率与增长预期参考。"),
    ("^TNX", "美国10年期国债收益率", "全球资产定价常用贴现率与风险偏好锚。"),
    ("^TYX", "美国30年期国债收益率", "长期通胀与期限溢价参考。"),
    ("DX-Y.NYB", "美元指数", "美元相对一篮子货币强弱。"),
    ("TIP", "通胀保值债券 ETF", "与通胀预期大致同向；非官方 CPI 读数。"),
]

CACHE_PATH = Path("data/cache/market_snapshot.json")


@dataclass
class QuoteRow:
    ticker: str
    label: str
    price: float | None
    prev_close: float | None
    change: float | None
    change_pct: float | None


def _quote(symbol: str, label: str) -> QuoteRow:
    try:
        t = yf.Ticker(symbol)
        fast = t.fast_info
        price = float(fast.get("lastPrice")) if fast.get("lastPrice") is not None else None
        prev_close = (
            float(fast.get("previousClose")) if fast.get("previousClose") is not None else None
        )
        if price is not None and prev_close:
            change = price - prev_close
            change_pct = change / prev_close * 100
        else:
            change, change_pct = None, None
        return QuoteRow(symbol, label, price, prev_close, change, change_pct)
    except Exception:
        return QuoteRow(symbol, label, None, None, None, None)


def get_macro_strip() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ticker, label, hint in MACRO_ENTRIES:
        q = _quote(ticker, label)
        if q.price is not None:
            if ticker.startswith("^"):
                display_value = f"{q.price:.2f}"
            else:
                display_value = f"{q.price:.2f}"
        else:
            display_value = "N/A"
        rows.append(
            {
                "ticker": ticker,
                "label": label,
                "hint": hint,
                "price": q.price,
                "change_pct": q.change_pct,
                "display_value": display_value,
            }
        )
    return rows


def _format_published_at(item: dict[str, Any], content: dict[str, Any]) -> str:
    pub = content.get("pubDate")
    if pub:
        try:
            dt = datetime.fromisoformat(str(pub).replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            pass
    ts = item.get("providerPublishTime")
    if ts is not None:
        try:
            dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M")
        except (TypeError, ValueError, OSError):
            pass
    return ""


def get_top_news(limit: int = 10) -> list[dict[str, Any]]:
    try:
        proxy = yf.Ticker("QQQ")
        raw = proxy.get_news(count=max(20, limit))
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    for item in raw:
        content = item.get("content", {})
        title = content.get("title", "") or item.get("title", "")
        if not title:
            continue
        summary = content.get("summary", "")
        provider = (content.get("provider") or {}).get("displayName", "Unknown")
        url_obj = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
        link = url_obj.get("url", "") if isinstance(url_obj, dict) else ""
        published_at = _format_published_at(item, content)
        out.append(
            {
                "title": title,
                "summary": summary,
                "provider": provider,
                "link": link,
                "published_at": published_at,
            }
        )
        if len(out) >= limit:
            break
    return out


def get_dashboard_market_snapshot() -> dict[str, Any]:
    index_rows = [_quote(tk, name) for tk, name in INDEX_TICKERS.items()]
    sectors = [_quote(tk, tk) for tk in SECTOR_PROXIES]
    sectors = [s for s in sectors if s.change_pct is not None]
    sectors.sort(key=lambda s: s.change_pct or -999, reverse=True)
    macro_strip = get_macro_strip()

    return {
        "indexes": index_rows,
        "top3_sectors": sectors[:3],
        "macro_strip": macro_strip,
        "market_status": market_status_text(),
        "last_updated_et": format_et(now_et()),
    }


def _quote_to_dict(q: QuoteRow) -> dict[str, Any]:
    return {
        "ticker": q.ticker,
        "label": q.label,
        "price": q.price,
        "prev_close": q.prev_close,
        "change": q.change,
        "change_pct": q.change_pct,
    }


def _dict_to_quote(d: dict[str, Any]) -> QuoteRow:
    return QuoteRow(
        ticker=d.get("ticker", ""),
        label=d.get("label", ""),
        price=d.get("price"),
        prev_close=d.get("prev_close"),
        change=d.get("change"),
        change_pct=d.get("change_pct"),
    )


def _snapshot_from_stored(snap: dict[str, Any]) -> dict[str, Any]:
    return {
        "indexes": [_dict_to_quote(x) for x in snap.get("indexes", [])],
        "top3_sectors": [_dict_to_quote(x) for x in snap.get("top3_sectors", [])],
        "macro_strip": snap.get("macro_strip") or [],
        "market_status": snap.get("market_status", "N/A"),
        "last_updated_et": snap.get("last_updated_et", "N/A"),
        "market_digest_md": snap.get("market_digest_md") or "",
        "fetched_at_utc": snap.get("fetched_at_utc") or "",
        "llm_model": snap.get("llm_model") or "",
        "llm_provider": snap.get("llm_provider") or "",
        "llm_news_error": snap.get("llm_news_error") or "",
        "llm_digest_error": snap.get("llm_digest_error") or "",
    }


def save_dashboard_cache(snapshot: dict[str, Any], news: list[dict[str, Any]]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "indexes": [_quote_to_dict(x) for x in snapshot.get("indexes", [])],
        "top3_sectors": [_quote_to_dict(x) for x in snapshot.get("top3_sectors", [])],
        "macro_strip": snapshot.get("macro_strip") or [],
        "market_digest_md": snapshot.get("market_digest_md") or "",
        "market_status": snapshot.get("market_status", "N/A"),
        "last_updated_et": snapshot.get("last_updated_et", "N/A"),
        "fetched_at_utc": snapshot.get("fetched_at_utc") or "",
        "llm_model": snapshot.get("llm_model") or "",
        "llm_provider": snapshot.get("llm_provider") or "",
        "llm_news_error": snapshot.get("llm_news_error") or "",
        "llm_digest_error": snapshot.get("llm_digest_error") or "",
        "news": news,
    }
    CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_dashboard_cache() -> tuple[dict[str, Any] | None, list[dict[str, Any]] | None]:
    if not CACHE_PATH.exists():
        return None, None
    try:
        raw = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        snapshot = _snapshot_from_stored(raw)
        return snapshot, raw.get("news", [])
    except Exception:
        return None, None


def load_dashboard_display() -> tuple[dict[str, Any] | None, list[dict[str, Any]] | None]:
    """优先 data/dashboard/latest.json，否则回退 data/cache/market_snapshot.json。"""
    latest = load_latest()
    if latest and latest.get("snapshot") is not None:
        snap = _snapshot_from_stored(latest["snapshot"])
        if not snap.get("fetched_at_utc") and latest.get("fetched_at_utc"):
            snap["fetched_at_utc"] = latest["fetched_at_utc"]
        if not snap.get("llm_model") and latest.get("llm_model"):
            snap["llm_model"] = latest["llm_model"]
        if not snap.get("llm_provider") and latest.get("llm_provider"):
            snap["llm_provider"] = latest["llm_provider"]
        return snap, latest.get("news", [])
    return load_dashboard_cache()


def _build_store_payload(
    snapshot: dict[str, Any],
    news: list[dict[str, Any]],
    llm_model: str,
    fetched_at_utc: str,
) -> dict[str, Any]:
    snap_out = {
        "indexes": [_quote_to_dict(x) for x in snapshot.get("indexes", [])],
        "top3_sectors": [_quote_to_dict(x) for x in snapshot.get("top3_sectors", [])],
        "macro_strip": snapshot.get("macro_strip") or [],
        "market_digest_md": snapshot.get("market_digest_md") or "",
        "market_status": snapshot.get("market_status", "N/A"),
        "last_updated_et": snapshot.get("last_updated_et", "N/A"),
        "fetched_at_utc": fetched_at_utc,
        "llm_model": llm_model,
        "llm_provider": snapshot.get("llm_provider") or "",
        "llm_news_error": snapshot.get("llm_news_error") or "",
        "llm_digest_error": snapshot.get("llm_digest_error") or "",
    }
    return {
        "snapshot": snap_out,
        "news": news,
        "llm_model": llm_model,
        "llm_provider": snapshot.get("llm_provider") or "",
        "fetched_at_utc": fetched_at_utc,
    }


def refresh_dashboard_cache(
    limit: int = 10,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """拉取行情与新闻并调用仪表盘专用 LLM（始终 build_llm_config(None)，与个股分析 last_params 无关）。"""
    snapshot = get_dashboard_market_snapshot()
    news: list[dict[str, Any]] = get_top_news(limit=limit)
    cfg = build_llm_config(None)
    model_name = cfg.get("quick_think_llm", "")
    provider_name = str(cfg.get("llm_provider") or "")
    digest_md = ""
    news_err = ""
    digest_err = ""
    try:
        news = enrich_news_opinions(news, cfg)
    except Exception as e:
        news_err = f"{type(e).__name__}: {e}"[:500]
        for n in news:
            n.setdefault("stance", "unknown")
            n.setdefault("llm_summary", "")
    try:
        digest_md = generate_market_digest(snapshot, news, cfg)
    except Exception as e:
        digest_err = f"{type(e).__name__}: {e}"[:500]
        digest_md = ""

    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    snapshot["market_digest_md"] = digest_md
    snapshot["fetched_at_utc"] = fetched_at
    snapshot["llm_model"] = model_name
    snapshot["llm_provider"] = provider_name
    snapshot["llm_news_error"] = news_err
    snapshot["llm_digest_error"] = digest_err if not digest_md.strip() else ""

    save_dashboard_cache(snapshot, news)

    payload = _build_store_payload(snapshot, news, model_name, fetched_at)
    save_latest(payload)
    append_history(payload)

    return snapshot, news
