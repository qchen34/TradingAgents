from __future__ import annotations

import re
import os
import collections
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
import json
import time


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]


def watchlist_path() -> Path:
    return _workspace_root() / "Claude_input" / "x资讯" / "关注列表.md"


def brief_config_path() -> Path:
    return _workspace_root() / "Claude_input" / "x资讯" / "简报配置.md"


def x_input_dir() -> Path:
    return _workspace_root() / "Claude_input" / "x资讯"


def x_cache_dir() -> Path:
    return _repo_root() / "data" / "x_brief"


def latest_json_path() -> Path:
    return x_cache_dir() / "latest.json"


def latest_raw_path() -> Path:
    return x_cache_dir() / "latest_raw.json"


def _clean_handle(raw: str) -> str:
    token = raw.strip()
    if token.startswith("@"):
        token = token[1:]
    # 兼容历史写法/旧 handle，统一映射到当前可用 handle。
    aliases = {
        "andrejkarpathy": "karpathy",
    }
    token = aliases.get(token.lower(), token)
    return token


def parse_watchers_from_markdown(md_text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in md_text.splitlines():
        if "|" not in line or line.count("|") < 5:
            continue
        cells = [c.strip() for c in line.strip().split("|")]
        if len(cells) < 4:
            continue
        # 兼容两种格式：
        # 1) 关注列表.md：| 序号 | 账号 | 名称 | 简介 | 当前分 |
        # 2) 简报配置.md：| 账号 | 名称 | 当前权重 | 偏好内容类型 | 备注 |
        account_idx = -1
        for i, c in enumerate(cells):
            if c.startswith("@"):
                account_idx = i
                break
        if account_idx < 0:
            continue
        account_cell = cells[account_idx]
        name_cell = ""
        if account_idx + 1 < len(cells):
            name_cell = cells[account_idx + 1]
        handle = _clean_handle(account_cell)
        if not re.fullmatch(r"[A-Za-z0-9_]+", handle):
            rows.append(
                {
                    "handle": handle,
                    "account": account_cell,
                    "name": name_cell,
                    "category": "",
                    "score": cells[6] if len(cells) > 6 else "",
                    "skip_reason": "invalid_handle_for_nitter",
                }
            )
            continue
        rows.append(
            {
                "handle": handle,
                "account": f"@{handle}",
                    "name": name_cell,
                "category": "",
                "score": cells[6] if len(cells) > 6 else "",
                "skip_reason": "",
            }
        )
    return rows


def load_watchers() -> list[dict[str, Any]]:
    cfg = brief_config_path()
    if cfg.exists():
        rows = parse_watchers_from_markdown(cfg.read_text(encoding="utf-8"))
        if rows:
            return rows
    p = watchlist_path()
    if not p.exists():
        raise RuntimeError(f"关注列表不存在: {p}")
    return parse_watchers_from_markdown(p.read_text(encoding="utf-8"))


def _fetch_url(url: str, timeout: int = 12) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; TradingAgents-XBrief/1.0)",
            "Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _parse_rss_items(xml_bytes: bytes) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_bytes)
    out: list[dict[str, Any]] = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        if not link:
            continue
        dt: datetime | None = None
        if pub:
            try:
                dt = parsedate_to_datetime(pub)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
            except Exception:
                dt = None
        out.append(
            {
                "title": title,
                "link": link,
                "published_at": dt.isoformat() if dt else "",
                "published_at_obj": dt,
            }
        )
    return out


def _extract_tweet_id(link: str) -> str:
    m = re.search(r"/status/(\d+)", link)
    return m.group(1) if m else link


def _to_x_post_url(link: str, handle: str) -> str:
    link = (link or "").strip()
    if not link:
        return ""
    tweet_id = _extract_tweet_id(link)
    if tweet_id and re.fullmatch(r"\d+", tweet_id):
        return f"https://x.com/{handle}/status/{tweet_id}"
    # 非标准链接时仅做域名替换兜底
    return re.sub(r"^https?://nitter\.[^/]+", "https://x.com", link)


def normalize_to_x_url(link: str, handle: str = "") -> str:
    """
    对外暴露的 URL 规范化函数：
    - 优先产出 x.com/<handle>/status/<id>
    - 无法提取状态 ID 时做 nitter 域名替换兜底
    """
    return _to_x_post_url(link, handle)


def fetch_nitter_rss_for_handle(handle: str) -> list[dict[str, Any]]:
    mirrors = [
        f"https://nitter.net/{handle}/rss",
        f"https://nitter.privacydev.net/{handle}/rss",
    ]
    last_error: str = "unknown_error"
    for url in mirrors:
        try:
            body = _fetch_url(url)
            return _parse_rss_items(body)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ET.ParseError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            continue
    raise RuntimeError(last_error)


def fetch_rsshub_for_handle(handle: str) -> list[dict[str, Any]]:
    mirrors = [
        f"https://rsshub.app/twitter/user/{handle}",
        f"https://rsshub.rssforever.com/twitter/user/{handle}",
    ]
    last_error: str = "unknown_error"
    for url in mirrors:
        try:
            body = _fetch_url(url)
            return _parse_rss_items(body)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ET.ParseError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            continue
    raise RuntimeError(last_error)


def fetch_snscrape_for_handle(handle: str) -> list[dict[str, Any]]:
    try:
        from snscrape.modules.twitter import TwitterUserScraper  # type: ignore
    except Exception as exc:
        raise RuntimeError(f"snscrape_unavailable: {exc}") from exc

    out: list[dict[str, Any]] = []
    try:
        scraper = TwitterUserScraper(handle)
        for tw in scraper.get_items():
            dt = getattr(tw, "date", None)
            if dt is not None:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
            url = getattr(tw, "url", "") or ""
            out.append(
                {
                    "title": (getattr(tw, "rawContent", None) or getattr(tw, "content", None) or "").strip(),
                    "link": url,
                    "published_at": dt.isoformat() if isinstance(dt, datetime) else "",
                    "published_at_obj": dt if isinstance(dt, datetime) else None,
                }
            )
            if len(out) >= 300:
                break
    except Exception as exc:
        raise RuntimeError(f"snscrape_error: {exc}") from exc
    return out


def _parse_source_priority() -> list[str]:
    raw = os.getenv("X_SOURCE_PRIORITY", "nitter,snscrape,rsshub")
    items = [x.strip().lower() for x in raw.split(",") if x.strip()]
    allowed = {"nitter", "snscrape", "rsshub"}
    ordered = [x for x in items if x in allowed]
    if not ordered:
        ordered = ["nitter", "snscrape", "rsshub"]
    # dedup keep order
    seen: set[str] = set()
    out: list[str] = []
    for x in ordered:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


def _fetch_with_priority(handle: str, source_priority: list[str]) -> tuple[str, list[dict[str, Any]], dict[str, str]]:
    errors: dict[str, str] = {}
    for source in source_priority:
        try:
            if source == "nitter":
                return source, fetch_nitter_rss_for_handle(handle), errors
            if source == "snscrape":
                return source, fetch_snscrape_for_handle(handle), errors
            if source == "rsshub":
                return source, fetch_rsshub_for_handle(handle), errors
            errors[source] = "unsupported_source"
        except Exception as exc:
            errors[source] = str(exc)
            continue
    return "none", [], errors


def _collect_x_rss(days: int, per_account_limit: int) -> dict[str, Any]:
    watchers = load_watchers()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    all_tweets: list[dict[str, Any]] = []
    account_stats: list[dict[str, Any]] = []
    seen: set[str] = set()
    source_priority = _parse_source_priority()
    source_hits: collections.Counter[str] = collections.Counter()
    source_errors: collections.Counter[str] = collections.Counter()
    t0 = time.perf_counter()
    valid_watchers = [w for w in watchers if not w.get("skip_reason")]
    print(
        f"[xbrief] fetch-start mode=weekly days={days} watchers={len(watchers)} "
        f"valid={len(valid_watchers)} per_account_limit={per_account_limit} sources={'>'.join(source_priority)}"
    )

    for w in watchers:
        handle = w["handle"]
        if w.get("skip_reason"):
            account_stats.append(
                {
                    **w,
                    "status": "skipped",
                    "tweets_count": 0,
                    "error": w["skip_reason"],
                }
            )
            continue
        try:
            source, items, errors = _fetch_with_priority(handle, source_priority)
            if source == "none":
                raise RuntimeError("; ".join([f"{k}={v}" for k, v in errors.items()]) or "all_sources_failed")
            kept = 0
            for it in items:
                dt = it.get("published_at_obj")
                if not isinstance(dt, datetime) or dt < cutoff:
                    continue
                tweet_id = _extract_tweet_id(it.get("link", ""))
                dedup_key = f"{handle}:{tweet_id}"
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)
                all_tweets.append(
                    {
                        "handle": handle,
                        "account": w["account"],
                        "name": w["name"],
                        "title": it.get("title", ""),
                        "url": _to_x_post_url(str(it.get("link", "")), handle),
                        "published_at": dt.isoformat(),
                        "source": source,
                    }
                )
                kept += 1
                if kept >= per_account_limit:
                    break
            source_hits[source] += 1
            account_stats.append(
                {
                    **w,
                    "status": "ok",
                    "tweets_count": kept,
                    "error": "",
                    "source": source,
                }
            )
        except Exception as exc:
            err_s = str(exc)
            for s in source_priority:
                if f"{s}=" in err_s or s in err_s:
                    source_errors[s] += 1
            account_stats.append(
                {
                    **w,
                    "status": "error",
                    "tweets_count": 0,
                    "error": err_s,
                    "source": "none",
                }
            )

    all_tweets.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    active_accounts = len([x for x in account_stats if x.get("tweets_count", 0) > 0])
    error_accounts = [x for x in account_stats if x.get("status") == "error"]
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    sample_fail = ",".join(x.get("handle", "") for x in error_accounts[:3]) or "-"
    hit_ratio = ",".join([f"{k}:{v}" for k, v in source_hits.items()]) or "-"
    err_ratio = ",".join([f"{k}:{v}" for k, v in source_errors.items()]) or "-"
    print(
        f"[xbrief] fetch-done mode=weekly active={active_accounts}/{len(account_stats)} "
        f"tweets={len(all_tweets)} failed={len(error_accounts)} elapsed_ms={elapsed_ms} "
        f"source_hits={hit_ratio} source_errors={err_ratio} fail_sample={sample_fail}"
    )
    period_end = datetime.now(timezone.utc)
    period_start = cutoff
    month_tag = period_end.strftime("%Y%m")
    return {
        "generated_at": period_end.isoformat(),
        "report_type": "weekly",
        "input": {
            "watchlist_path": str(brief_config_path() if brief_config_path().exists() else watchlist_path()),
            "watchers": [{"handle": w.get("handle", ""), "name": w.get("name", "")} for w in watchers],
            "days": days,
            "per_account_limit": per_account_limit,
        },
        "output": {
            "description": "关注博主近一周推文",
            "tweet_window_days": days,
            "tweet_count": len(all_tweets),
        },
        "period": {
            "days": days,
            "start_utc": period_start.isoformat(),
            "end_utc": period_end.isoformat(),
            "month_tag": month_tag,
        },
        "overview": {
            "total_accounts": len(account_stats),
            "active_accounts": active_accounts,
            "total_tweets": len(all_tweets),
            "failed_accounts": len([x for x in account_stats if x.get("status") == "error"]),
            "source_hits": dict(source_hits),
            "source_errors": dict(source_errors),
        },
        "accounts": account_stats,
        "tweets": all_tweets,
    }


def collect_x_rss_last_week(days: int = 7, per_account_limit: int = 80) -> dict[str, Any]:
    # 周报默认 7 天，允许调用方传更短/更长窗口。
    return _collect_x_rss(days=days, per_account_limit=per_account_limit)


def collect_x_rss_last_month(days: int = 30, per_account_limit: int = 80) -> dict[str, Any]:
    # 兼容旧调用；内部统一走同一数据请求链路。
    return _collect_x_rss(days=days, per_account_limit=per_account_limit)


def save_raw_payload(payload: dict[str, Any]) -> None:
    cache_dir = x_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    latest_raw_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

