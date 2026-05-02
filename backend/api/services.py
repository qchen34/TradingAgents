from __future__ import annotations

import os

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import yfinance as yf

from web.services import backtesting_core as bt
from web.services import market_data as md
from web.services.x_brief_data import collect_x_rss_last_week, normalize_to_x_url, save_raw_payload
from web.services.x_brief_llm import build_fallback_modules, build_x_brief_modules, translate_display_content
from web.services.x_brief_renderer import (
    build_monthly_analysis_markdown,
    build_tweet_summary_markdown,
    load_latest_view,
    persist_outputs,
)
from web.pages.wheel.style_profiles import STYLE_PROFILES
from web.pages.wheel.strategy_shared import rsi
from web.services.dashboard_llm import build_llm_config
from web.services.strategy_api_service import answer_lrs_question, get_lrs_doc_markdown


DEFAULT_SESSION_STATE: dict[str, Any] = {
    "current_page": "仪表盘",
    "ui_mode": "idle",
    "show_config": False,
    "event_log": [],
    "runtime_stage": "",
    "latest_run_dir": "",
    "last_params": None,
    "selected_params_summary": "",
    "active_output_dir": "",
    "runtime_stats": {},
    "selected_ticker": "QQQ",
    "error": "",
    "strategy_sub_menu": "LRS TQQQ策略",
}


def strategy_metadata() -> dict[str, Any]:
    return {
        "sub_strategies": ["LRS TQQQ策略", "Wheel策略"],
        "lrs_doc_md": get_lrs_doc_markdown(),
    }


def answer_lrs_chat(question: str, last_params: dict[str, Any] | None) -> str:
    cfg = build_llm_config(last_params)
    prompt = (
        "你是量化策略研究助手。请围绕 LRS TQQQ 策略回答问题，"
        "要求中文、结构化、可执行。\n\n用户问题："
        f"{question}"
    )
    return answer_lrs_question(prompt, cfg)


@dataclass
class BacktestJob:
    job_id: str
    period_key: str
    status: str
    created_at: str
    result: dict[str, Any] | None = None
    error: str | None = None
    updated_at: str = field(default_factory=lambda: _now_iso())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_JOBS: dict[str, BacktestJob] = {}
_LOCK = threading.Lock()


def _run_backtest(period_key: str, job_id: str) -> None:
    try:
        qqq_df, tqqq_df = bt._fetch(period_key)
        if qqq_df.empty or tqqq_df.empty:
            raise RuntimeError("QQQ 或 TQQQ 数据为空")
        qqq_full = qqq_df["Close"].squeeze().dropna()
        tqqq_full = tqqq_df["Close"].squeeze().dropna()
        if len(qqq_full) < 220:
            raise RuntimeError(f"数据量不足（{len(qqq_full)} 天），无法计算 MA200")
        trade_start = bt._get_effective_start(qqq_full, tqqq_full, period_key)
        qqq_eff = qqq_full[trade_start:]
        sig = bt._build_signals(qqq_full)
        trades, equity = bt._simulate(sig, tqqq_full, trade_start=trade_start)
        metrics = bt._metrics(trades, equity, qqq_eff)
        with _LOCK:
            _JOBS[job_id].status = "completed"
            _JOBS[job_id].updated_at = _now_iso()
            _JOBS[job_id].result = {
                "period_key": period_key,
                "period_label": bt._PERIOD_SPECS[period_key]["label"],
                "date_range": {
                    "start": str(qqq_eff.index[0].date()),
                    "end": str(qqq_eff.index[-1].date()),
                },
                "metrics": metrics,
                "trades": [t.__dict__ for t in trades],
            }
    except Exception as exc:  # pragma: no cover - best effort background task
        with _LOCK:
            _JOBS[job_id].status = "failed"
            _JOBS[job_id].updated_at = _now_iso()
            _JOBS[job_id].error = str(exc)


def create_backtest_job(period_key: str) -> BacktestJob:
    job_id = uuid.uuid4().hex
    job = BacktestJob(
        job_id=job_id,
        period_key=period_key,
        status="running",
        created_at=_now_iso(),
    )
    with _LOCK:
        _JOBS[job_id] = job
    th = threading.Thread(target=_run_backtest, args=(period_key, job_id), daemon=True)
    th.start()
    return job


def get_backtest_job(job_id: str) -> BacktestJob | None:
    with _LOCK:
        return _JOBS.get(job_id)


def _serialize_quote_row(row: Any) -> dict[str, Any]:
    return {
        "ticker": getattr(row, "ticker", ""),
        "label": getattr(row, "label", ""),
        "price": getattr(row, "price", None),
        "prev_close": getattr(row, "prev_close", None),
        "change": getattr(row, "change", None),
        "change_pct": getattr(row, "change_pct", None),
    }


def _serialize_snapshot(snapshot: dict[str, Any], news: list[dict[str, Any]] | None) -> dict[str, Any]:
    top6_raw = snapshot.get("top6_sectors")
    if top6_raw is None:
        top6_raw = snapshot.get("top3_sectors", [])
    return {
        "market_status": snapshot.get("market_status", "N/A"),
        "last_updated_et": snapshot.get("last_updated_et", "N/A"),
        "fetched_at_utc": snapshot.get("fetched_at_utc", ""),
        "llm_model": snapshot.get("llm_model", ""),
        "llm_provider": snapshot.get("llm_provider", ""),
        "llm_news_error": snapshot.get("llm_news_error", ""),
        "llm_digest_error": snapshot.get("llm_digest_error", ""),
        "market_digest_md": snapshot.get("market_digest_md", ""),
        "indexes": [_serialize_quote_row(x) for x in snapshot.get("indexes", [])],
        "top6_sectors": [_serialize_quote_row(x) for x in top6_raw],
        "macro_strip": snapshot.get("macro_strip") or [],
        "news": news or [],
    }


def get_dashboard_snapshot() -> dict[str, Any]:
    snapshot, news = md.load_dashboard_display()
    if snapshot is None:
        snapshot = md.get_dashboard_market_snapshot()
    return _serialize_snapshot(snapshot, news)


def refresh_dashboard_snapshot(limit: int = 10) -> dict[str, Any]:
    snapshot, news = md.refresh_dashboard_cache(limit=limit)
    return _serialize_snapshot(snapshot, news)


def wheel_profiles() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key, p in STYLE_PROFILES.items():
        out.append(
            {
                "key": key,
                "label": p.label,
                "dte": p.dte,
                "ivr_min": p.ivr_min,
                "rsi_max": p.rsi_max,
                "put_otm": p.put_otm,
                "call_otm": p.call_otm,
                "put_tp": p.put_tp,
                "call_tp": p.call_tp,
                "put_sl": p.put_sl,
            }
        )
    return out


def _fetch_close(ticker: str) -> Any:
    df = yf.download(ticker, period="6mo", auto_adjust=True, progress=False)
    if df.empty:
        raise RuntimeError(f"{ticker} 无可用行情")
    close = df["Close"]
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]
    return close.dropna()


def _estimate_ivr(underlying_close: Any) -> float:
    ret = underlying_close.pct_change().dropna()
    if len(ret) < 20:
        return 50.0
    hv = ret.rolling(20).std() * np.sqrt(252)
    iv = (hv * 1.15).clip(lower=0.1, upper=2.5)
    iv_min = iv.rolling(126, min_periods=20).min()
    iv_max = iv.rolling(126, min_periods=20).max()
    ivr = ((iv - iv_min) / (iv_max - iv_min).replace(0, np.nan) * 100.0).fillna(50.0)
    return float(ivr.iloc[-1])


def wheel_evaluate(style_key: str, underlying_ticker: str, signal_ticker: str) -> dict[str, Any]:
    if style_key not in STYLE_PROFILES:
        raise RuntimeError(f"未知风格：{style_key}")
    style = STYLE_PROFILES[style_key]
    ul = _fetch_close(underlying_ticker.upper())
    sig = _fetch_close(signal_ticker.upper())
    rs = rsi(sig, 14).fillna(50.0)
    latest_ul = float(ul.iloc[-1])
    latest_sig = float(sig.iloc[-1])
    latest_rsi = float(rs.iloc[-1])
    latest_ivr = _estimate_ivr(ul)

    put_strike = round(latest_ul * (1.0 - style.put_otm), 2)
    call_strike = round(latest_ul * (1.0 + style.call_otm), 2)
    put_entry_ok = latest_ivr >= style.ivr_min and latest_rsi <= style.rsi_max
    regime = "bullish" if latest_sig >= float(sig.iloc[-20:].mean()) else "neutral_to_weak"
    if put_entry_ok:
        action = f"可考虑卖出现金担保Put（行权价约 {put_strike}）"
    elif regime == "bullish":
        action = "等待更优波动率窗口（IVR 偏低），暂不卖Put"
    else:
        action = "信号偏弱，优先观望或缩小仓位"

    return {
        "style": {
            "key": style.key,
            "label": style.label,
            "dte": style.dte,
            "ivr_min": style.ivr_min,
            "rsi_max": style.rsi_max,
            "put_otm": style.put_otm,
            "call_otm": style.call_otm,
            "put_tp": style.put_tp,
            "call_tp": style.call_tp,
            "put_sl": style.put_sl,
        },
        "signal": {
            "underlying_ticker": underlying_ticker.upper(),
            "signal_ticker": signal_ticker.upper(),
            "underlying_price": latest_ul,
            "signal_price": latest_sig,
            "rsi14": latest_rsi,
            "ivr_est": latest_ivr,
            "put_entry_ok": put_entry_ok,
            "regime": regime,
        },
        "execution_hint": {
            "suggested_action": action,
            "put_strike_hint": put_strike,
            "call_strike_hint": call_strike,
            "dte_hint": style.dte,
            "take_profit": {
                "put": style.put_tp,
                "call": style.call_tp,
            },
        },
    }


def _normalize_quote_code(code: str) -> str:
    c = (code or "").strip().upper()
    if not c:
        return ""
    if c.startswith("US.."):
        return f"^{c[4:]}"
    if c.startswith("US."):
        return c[3:]
    return c


def batch_quotes(codes: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in codes:
        normalized = _normalize_quote_code(raw)
        if not normalized:
            continue
        q = md._quote(normalized, normalized)
        out.append(
            {
                "request_code": raw,
                "normalized_code": normalized,
                "ticker": q.ticker,
                "label": q.label,
                "price": q.price,
                "prev_close": q.prev_close,
                "change": q.change,
                "change_pct": q.change_pct,
            }
        )
    return out


def get_x_brief_latest() -> dict[str, Any] | None:
    return load_latest_view()


def refresh_x_brief(days: int = 7, per_account_limit: int = 80) -> dict[str, Any]:
    payload = collect_x_rss_last_week(days=days, per_account_limit=per_account_limit)
    cfg = build_llm_config(None)
    # X Brief 两层模型：
    # - 第一层编排：thinking（MiniMax）
    # - 第二层翻译：quick（沿用 quick_think_llm）
    cfg["xbrief_orchestrator_provider"] = os.environ.get("XBRIEF_ORCHESTRATOR_PROVIDER", "siliconflow")
    cfg["xbrief_orchestrator_model"] = os.environ.get("XBRIEF_ORCHESTRATOR_MODEL", "Pro/MiniMaxAI/MiniMax-M2.5")
    cfg["xbrief_orchestrator_base_url"] = os.environ.get("XBRIEF_ORCHESTRATOR_BASE_URL", "https://api.siliconflow.cn/v1")
    cfg["xbrief_translate_provider"] = cfg.get("llm_provider")
    cfg["xbrief_translate_model"] = cfg.get("quick_think_llm")
    cfg["xbrief_translate_base_url"] = cfg.get("backend_url")
    save_raw_payload(payload)
    tweet_md = build_tweet_summary_markdown(payload)
    modules: dict[str, Any]
    try:
        modules = build_x_brief_modules(payload, tweet_md, cfg)
    except Exception as exc:
        modules = build_fallback_modules(payload)
        modules["risk_signals"] = modules.get("risk_signals", []) + [
            {
                "id": "llm-fallback-error",
                "level": "MID",
                "title": "LLM 编排暂不可用",
                "detail": f"本次使用规则兜底：{exc}",
            }
        ]
    if not any(modules.get(k) for k in ("themes", "p0_events", "top_quotes", "category_updates", "risk_signals")):
        modules = build_fallback_modules(payload)

    # 最终落盘前统一做一遍 URL 规范化，避免历史链路残留 nitter 链接。
    tweets = payload.get("tweets", []) or []
    norm_tweets: list[dict[str, Any]] = []
    for t in tweets:
        d = dict(t)
        d["url"] = normalize_to_x_url(str(d.get("url", "")), str(d.get("handle", "")))
        norm_tweets.append(d)
    payload["tweets"] = norm_tweets

    for theme in modules.get("themes", []) or []:
        for sample in theme.get("samples", []) or []:
            sample["url"] = normalize_to_x_url(str(sample.get("url", "")), str(sample.get("handle", "")))
    for e in modules.get("p0_events", []) or []:
        e["url"] = normalize_to_x_url(str(e.get("url", "")))
    for q in modules.get("top_quotes", []) or []:
        speaker = str(q.get("speaker", "")).lstrip("@")
        q["url"] = normalize_to_x_url(str(q.get("url", "")), speaker)
    for c in modules.get("category_updates", []) or []:
        for item in c.get("items", []) or []:
            item["url"] = normalize_to_x_url(str(item.get("url", "")))

    try:
        payload = translate_display_content(payload, modules, cfg)
    except Exception as exc:
        modules["risk_signals"] = (modules.get("risk_signals") or []) + [
            {
                "id": "llm-translate-fallback-error",
                "level": "MID",
                "title": "前端内容翻译层异常",
                "detail": f"本次展示内容使用原文兜底：{exc}",
            }
        ]
    analysis_md = build_monthly_analysis_markdown(payload)

    # 统计 modules 实际引用的唯一推文数，写入 overview
    _kept_urls: set[str] = set()
    for _theme in modules.get("themes", []) or []:
        for _s in _theme.get("samples", []) or []:
            if _s.get("url"):
                _kept_urls.add(_s["url"])
    for _e in modules.get("p0_events", []) or []:
        if _e.get("url"):
            _kept_urls.add(_e["url"])
    for _q in modules.get("top_quotes", []) or []:
        if _q.get("url"):
            _kept_urls.add(_q["url"])
    overview = dict(payload.get("overview") or {})
    overview["tweets_kept"] = len(_kept_urls)
    payload = dict(payload)
    payload["overview"] = overview

    return persist_outputs(payload, tweet_md, analysis_md, modules=modules)

