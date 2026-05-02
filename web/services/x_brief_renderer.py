from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

from web.services.x_brief_data import latest_json_path, x_cache_dir, x_input_dir


THEME_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("模型能力", ("gpt", "model", "claude", "openai", "agi", "llm")),
    ("算力与芯片", ("gpu", "tpu", "nvidia", "inference", "compute", "chip")),
    ("投融资与并购", ("fund", "vc", "acquire", "merger", "valuation", "ipo")),
    ("交易与市场", ("market", "stock", "trading", "etf", "crypto", "price")),
]


def _pick_theme(text: str) -> str:
    t = text.lower()
    for name, keys in THEME_RULES:
        if any(k in t for k in keys):
            return name
    return "其他"


def _safe_excerpt(text: str, max_len: int = 200) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= max_len:
        return clean
    return clean[: max_len - 1] + "…"


def build_tweet_summary_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    period = payload.get("period", {})
    overview = payload.get("overview", {})
    tweets = payload.get("tweets", [])
    accounts = payload.get("accounts", [])
    lines.append("# X平台关注列表推文汇总")
    lines.append("")
    lines.append(f"**生成日期**: {payload.get('generated_at', '')}")
    lines.append("**数据来源**: Nitter RSS 订阅")
    lines.append(f"**时间范围**: 最近{period.get('days', 30)}天")
    lines.append(
        f"**账号总数**: {overview.get('total_accounts', 0)} | **成功获取**: {overview.get('active_accounts', 0)} | **推文总数**: {overview.get('total_tweets', 0)}"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for tw in tweets:
        grouped[tw.get("handle", "")].append(tw)

    for acc in accounts:
        handle = acc.get("handle", "")
        name = acc.get("name", "")
        status = acc.get("status")
        tlist = grouped.get(handle, [])
        if status != "ok":
            lines.append(f"### ⚠️ @{handle} — {name}（获取失败）")
            lines.append("")
            lines.append(f"- 错误: {acc.get('error', 'unknown')}")
            lines.append("")
            continue
        lines.append(f"### ✅ @{handle} — {name}（{len(tlist)} 条）")
        lines.append("")
        for tw in tlist[:20]:
            lines.append(f"**[{tw.get('published_at', '')}]**")
            lines.append(f"> {_safe_excerpt(tw.get('title', ''))}")
            lines.append(f"[原文链接]({tw.get('url', '')})")
            lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_monthly_analysis_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    overview = payload.get("overview", {})
    tweets: list[dict[str, Any]] = payload.get("tweets", [])
    lines.append("# X平台资讯深度分析报告")
    lines.append("")
    lines.append(f"**报告日期**: {payload.get('generated_at', '')}")
    lines.append(
        f"**分析账号**: {overview.get('total_accounts', 0)}个 | **活跃账号**: {overview.get('active_accounts', 0)}个 | **推文总量**: {overview.get('total_tweets', 0)}条"
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 一、总体概览")
    lines.append("")
    lines.append("- 本报告基于 X 关注列表近30天 RSS 数据自动生成。")
    lines.append("- 默认口径：按账号聚合、按推文主题词粗分层。")
    lines.append("")

    theme_counter: Counter[str] = Counter()
    for tw in tweets:
        theme_counter[_pick_theme(tw.get("title", ""))] += 1

    lines.append("## 二、主题分布")
    lines.append("")
    for theme, cnt in theme_counter.most_common():
        lines.append(f"- **{theme}**：{cnt} 条")
    lines.append("")

    top_accounts: Counter[str] = Counter([tw.get("handle", "") for tw in tweets])
    lines.append("## 三、活跃账号 Top10")
    lines.append("")
    for handle, cnt in top_accounts.most_common(10):
        lines.append(f"- @{handle}: {cnt} 条")
    lines.append("")

    lines.append("## 四、代表性推文")
    lines.append("")
    for tw in tweets[:20]:
        lines.append(
            f"- @{tw.get('handle', '')} | {tw.get('published_at', '')}\n  - {_safe_excerpt(tw.get('title', ''), 180)}\n  - {tw.get('url', '')}"
        )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*本报告由系统自动生成，供月度复盘使用。*")
    return "\n".join(lines).strip() + "\n"


def build_latest_view(
    payload: dict[str, Any],
    tweet_md: str,
    analysis_md: str,
    modules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tweets: list[dict[str, Any]] = payload.get("tweets", [])
    theme_counter: Counter[str] = Counter(_pick_theme(t.get("title", "")) for t in tweets)
    top_themes = [{"title": k, "count": v} for k, v in theme_counter.most_common(6)]
    mods = modules or {}
    headline = str(mods.get("headline") or "")
    trending_keywords = [str(k) for k in (mods.get("trending_keywords") or []) if k]
    return {
        **payload,
        "headline": headline,
        "trending_keywords": trending_keywords,
        "top_themes": top_themes,
        "modules": mods,
        "tweet_summary_md": tweet_md,
        "monthly_analysis_md": analysis_md,
    }


def persist_outputs(
    payload: dict[str, Any],
    tweet_md: str,
    analysis_md: str,
    modules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    month_tag = payload.get("period", {}).get("month_tag", "unknown")
    out_dir = x_input_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    tweet_md_path = out_dir / f"推文汇总_{month_tag}.md"
    analysis_md_path = out_dir / f"月度深度分析_{month_tag}.md"
    tweet_md_path.write_text(tweet_md, encoding="utf-8")
    analysis_md_path.write_text(analysis_md, encoding="utf-8")

    latest = build_latest_view(payload, tweet_md, analysis_md, modules=modules)
    latest["paths"] = {
        "tweet_summary_md": str(tweet_md_path),
        "monthly_analysis_md": str(analysis_md_path),
    }
    cache_dir = x_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    latest_json_path().write_text(json.dumps(latest, ensure_ascii=False, indent=2), encoding="utf-8")
    history_dir = cache_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    (history_dir / f"{ts}.json").write_text(json.dumps(latest, ensure_ascii=False, indent=2), encoding="utf-8")
    return latest


def load_latest_view() -> dict[str, Any] | None:
    p = latest_json_path()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

