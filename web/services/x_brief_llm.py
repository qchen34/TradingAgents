from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage

from tradingagents.llm_clients.base_client import normalize_content
from tradingagents.llm_clients.factory import create_llm_client
from web.services.x_brief_data import brief_config_path, x_cache_dir


def _write_debug_file(filename: str, content: str) -> None:
    debug_dir = x_cache_dir() / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / filename).write_text(content, encoding="utf-8")


def _llm_for_role(cfg: dict[str, Any], role: str):
    if role == "orchestrator":
        provider = cfg.get("xbrief_orchestrator_provider") or cfg.get("llm_provider")
        model = cfg.get("xbrief_orchestrator_model") or cfg.get("deep_think_llm") or cfg.get("quick_think_llm")
        base_url = cfg.get("xbrief_orchestrator_base_url") or cfg.get("backend_url")
    else:
        provider = cfg.get("xbrief_translate_provider") or cfg.get("llm_provider")
        model = cfg.get("xbrief_translate_model") or cfg.get("quick_think_llm") or cfg.get("deep_think_llm")
        base_url = cfg.get("xbrief_translate_base_url") or cfg.get("backend_url")
    client = create_llm_client(
        provider=provider,
        model=model,
        base_url=base_url,
        google_thinking_level=cfg.get("google_thinking_level"),
        openai_reasoning_effort=cfg.get("openai_reasoning_effort"),
        anthropic_effort=cfg.get("anthropic_effort"),
    )
    print(f"[xbrief][llm] role={role} provider={provider} model={model} base_url={base_url}")
    return client.get_llm()


def _to_text(resp: Any) -> str:
    if hasattr(resp, "content"):
        normalize_content(resp)
        c = resp.content
        return c if isinstance(c, str) else str(c)
    return str(resp)


def _parse_json_obj(text: str) -> dict[str, Any]:
    raw = text.strip()
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        obj = json.loads(m.group(0))
        if isinstance(obj, dict):
            return obj
    raise ValueError("LLM output does not contain a JSON object")


def _parse_json_array(text: str) -> list[Any]:
    raw = text.strip()
    try:
        arr = json.loads(raw)
        if isinstance(arr, list):
            return arr
    except json.JSONDecodeError:
        pass
    m = re.search(r"\[[\s\S]*\]", raw)
    if m:
        arr = json.loads(m.group(0))
        if isinstance(arr, list):
            return arr
    raise ValueError("LLM output does not contain a JSON array")


def _translate_one(llm: Any, text: str) -> str:
    prompt = f"""请将这条推文总结为“中文新闻播报语气”的一句话快讯，只输出结果本身：
- 不要直译，不要逐字对应；
- 提炼核心信息与影响，长度 28~70 字；
- 保持客观，不要口语化和夸张词。

{text[:800]}
"""
    resp = llm.invoke([HumanMessage(content=prompt)])
    return _to_text(resp).strip()


def _translate_texts(llm: Any, texts: list[str], chunk_size: int = 20) -> list[str]:
    out = [""] * len(texts)
    for start in range(0, len(texts), chunk_size):
        chunk = texts[start : start + chunk_size]
        # first try: batch translation
        zh_list: list[str] | None = None
        for _ in range(2):
            try:
                lines = [f"{i}. {t[:500]}" for i, t in enumerate(chunk)]
                prompt = f"""你是财经频道快讯编辑。请把下面每条推文改写成“新闻播报语气”的中文摘要。

要求：
1) 仅输出 JSON 数组，长度与输入一致。
2) 每个元素格式：{{"title_zh":"..."}}
3) 不要附加解释、不要省略任何一条。
4) 不要直译原句；要总结“这条在说什么、对市场/行业意味着什么”，每条 28~70 字。
5) 语言风格客观、凝练、可播报。

输入：
{chr(10).join(lines)}
"""
                resp = llm.invoke([HumanMessage(content=prompt)])
                arr = _parse_json_array(_to_text(resp))
                trial: list[str] = []
                for i in range(len(chunk)):
                    if i < len(arr) and isinstance(arr[i], dict):
                        trial.append(str(arr[i].get("title_zh", "")).strip())
                    else:
                        trial.append("")
                if len(trial) == len(chunk) and all(x.strip() for x in trial):
                    zh_list = trial
                    break
            except Exception:
                continue
        if zh_list is None:
            # second try: per-item translation
            zh_list = []
            for t in chunk:
                src = t.strip()
                if not src:
                    zh_list.append("")
                    continue
                try:
                    one = _translate_one(llm, src)
                    zh_list.append(one or src)
                except Exception:
                    zh_list.append(src)
        for i, val in enumerate(zh_list):
            out[start + i] = val
    return out


def _safe_modules(modules: dict[str, Any]) -> dict[str, Any]:
    out = {
        "headline": str(modules.get("headline") or ""),
        "trending_keywords": modules.get("trending_keywords") or [],
        "themes": modules.get("themes") or [],
        "p0_events": modules.get("p0_events") or [],
        "top_quotes": modules.get("top_quotes") or [],
        "category_updates": modules.get("category_updates") or [],
        "risk_signals": modules.get("risk_signals") or [],
    }
    # hard caps
    out["trending_keywords"] = [str(k) for k in out["trending_keywords"] if k][:6]
    out["themes"] = out["themes"][:3]
    out["p0_events"] = out["p0_events"][:6]
    out["top_quotes"] = out["top_quotes"][:3]
    out["category_updates"] = out["category_updates"][:6]
    out["risk_signals"] = out["risk_signals"][:6]
    return out


def _dedupe_modules_by_url(modules: dict[str, Any]) -> dict[str, Any]:
    """
    去重规则：同一条推文（同一 url）只允许在一个模块出现。
    模块优先级：themes > p0_events > top_quotes > category_updates
    """
    seen_urls: set[str] = set()

    def _take(url: str) -> bool:
        u = (url or "").strip()
        if not u:
            return True
        if u in seen_urls:
            return False
        seen_urls.add(u)
        return True

    out = dict(modules)

    themes = []
    for t in out.get("themes", []) or []:
        t2 = dict(t)
        samples = []
        for s in t.get("samples", []) or []:
            if _take(str(s.get("url", ""))):
                samples.append(s)
        t2["samples"] = samples
        themes.append(t2)
    out["themes"] = themes

    p0 = []
    for e in out.get("p0_events", []) or []:
        if _take(str(e.get("url", ""))):
            p0.append(e)
    out["p0_events"] = p0

    quotes = []
    for q in out.get("top_quotes", []) or []:
        if _take(str(q.get("url", ""))):
            quotes.append(q)
    out["top_quotes"] = quotes

    cats = []
    for c in out.get("category_updates", []) or []:
        c2 = dict(c)
        items = []
        for it in c.get("items", []) or []:
            if _take(str(it.get("url", ""))):
                items.append(it)
        c2["items"] = items
        cats.append(c2)
    out["category_updates"] = cats
    return out


def _load_brief_config_context(max_chars: int = 12000) -> str:
    """
    第一层 LLM 的编辑偏好上下文：
    - 读取 Claude_input/x资讯/简报配置.md
    - 传入“关心主题、账号权重、内容偏好、简报格式偏好”等约束
    """
    p: Path = brief_config_path()
    if not p.exists():
        return ""
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        return ""
    clean = text.strip()
    if len(clean) <= max_chars:
        return clean
    return clean[:max_chars]


def build_x_brief_modules(payload: dict[str, Any], tweet_summary_md: str, cfg: dict[str, Any]) -> dict[str, Any]:
    t0 = time.perf_counter()
    run_ts = time.strftime("%Y%m%d_%H%M%S")
    tweets = payload.get("tweets", [])[:120]
    compact = []
    for t in tweets:
        compact.append(
            {
                "handle": t.get("handle", ""),
                "name": t.get("name", ""),
                "published_at": t.get("published_at", ""),
                "title": (t.get("title_zh") or t.get("title") or "")[:280],
                "url": t.get("url", ""),
            }
        )
    editorial_context = _load_brief_config_context()
    llm = _llm_for_role(cfg, role="orchestrator")
    print(f"[xbrief][llm][l1] stage=start tweets={len(tweets)} summary_chars={len(tweet_summary_md)} mode=two_stage")
    prompt_stage1 = f"""你是“X资讯月报总编”。请先产出“结构草案 JSON”（阶段1），供后续阶段2定稿使用。

你必须遵循“用户配置文档”的偏好：
- 优先覆盖“我现在最关心的事”；
- 按“账号权重与偏好”做信息优先级排序（高权重账号更容易进入 themes/p0）；
- 按“内容类型偏好（✅/❌）”进行取舍；
- 尽量贴合“简报格式偏好”的表达风格（中文总结为主，保留关键英文原句）；
- 页面是固定模块位，内容应服务于前端模块整合，不要输出散乱信息。

阶段1输出要求（仅草案）：
1) 只输出 JSON 对象，不要 markdown，不要解释文字。
2) 使用如下字段（严格保持键名）：
{{
  "headline":"今日一句话总结，<40字，点出主旋律",
  "trending_keywords":["关键词1","关键词2","关键词3"],
  "themes":[{{"id":"t1","title":"...","subtitle":"...","priority":"P0|P1|P2","bullets":["..."],"sample_urls":["..."]}}],
  "p0_events":[{{"id":"p01","title":"...","meta":"...","summary":"...","url":"..."}}],
  "top_quotes":[{{"id":"q1","quote":"...","speaker":"...","date":"...","note":"...","url":"..."}}],
  "category_updates":[{{"id":"c1","title":"...","subtitle":"...","level":"P0|P1|P2|WARN","item_urls":["..."],"item_texts":["..."]}}],
  "risk_signals":[{{"id":"r1","level":"HIGH|MID|OPP","title":"...","detail":"..."}}]
}}
3) 数量限制：themes=3, p0_events<=6, top_quotes<=3, category_updates<=6, risk_signals<=6。
4) trending_keywords：3-6 个当期最热词条（中英均可），直接从推文内容提炼。
5) themes 的 priority 字段：首个主题通常为 P0，其余为 P1/P2；根据重要性自判。
6) 每个模块优先包含可验证 URL；无法确定时宁缺毋滥。
7) 内容必须中文，简洁可执行。
8) JSON 必须合法：双引号、无注释、无尾逗号。

用户配置文档（用于本次简报编排）：
{editorial_context[:12000] if editorial_context else "（未提供，按默认财经简报策略）"}

上下文（摘要）：
{tweet_summary_md[:12000]}

推文样本（JSON）：
{json.dumps(compact, ensure_ascii=False)}
"""
    _write_debug_file(
        f"{run_ts}_l1_stage1_input.txt",
        "\n\n".join(
            [
                "[meta]",
                f"tweets={len(tweets)}",
                f"tweet_summary_chars={len(tweet_summary_md)}",
                "phase=stage1_draft",
                "",
                "[prompt]",
                prompt_stage1,
            ]
        ),
    )
    resp1 = llm.invoke([HumanMessage(content=prompt_stage1)])
    text1 = _to_text(resp1)
    try:
        draft_obj = _parse_json_obj(text1)
    except Exception as exc:
        _write_debug_file(
            f"{run_ts}_l1_stage1_output_error.json",
            json.dumps(
                {
                    "parse_error": str(exc),
                    "raw_text": text1,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        raise
    _write_debug_file(
        f"{run_ts}_l1_stage1_output.json",
        json.dumps(
            {
                "raw_text": text1,
                "parsed_draft": draft_obj,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )

    prompt_stage2 = f"""你是“X资讯月报总编”。请基于阶段1草案，输出最终可渲染 JSON（阶段2定稿）。

要求：
1) 只输出 JSON 对象，不要 markdown，不要解释文字。
2) 必须严格使用最终字段：
{{
  "headline":"今日一句话总结，<40字，点出主旋律",
  "trending_keywords":["关键词1","关键词2","关键词3"],
  "themes":[{{"id":"t1","title":"...","subtitle":"...","priority":"P0|P1|P2","bullets":["..."],"samples":[{{"text":"...","url":"...","handle":"...","date":"..."}}]}}],
  "p0_events":[{{"id":"p01","title":"...","meta":"...","summary":"...","url":"..."}}],
  "top_quotes":[{{"id":"q1","quote":"...","speaker":"...","date":"...","note":"...","url":"..."}}],
  "category_updates":[{{"id":"c1","title":"...","subtitle":"...","level":"P0|P1|P2|WARN","items":[{{"text":"...","url":"..."}}]}}],
  "risk_signals":[{{"id":"r1","level":"HIGH|MID|OPP","title":"...","detail":"..."}}]
}}
3) 保证 JSON 合法（双引号、无尾逗号）。
4) 引用 URL 时，优先从“推文索引”中取值；samples/items 尽量带 url。
5) 数量限制：themes=3, p0_events<=6, top_quotes<=3, category_updates<=6, risk_signals<=6。
6) 严格保留 stage1 草案中每个 theme 的 priority 字段（P0/P1/P2）。
7) 严格保留 stage1 草案中的 trending_keywords 数组。

阶段1草案（JSON）：
{json.dumps(draft_obj, ensure_ascii=False)}

推文索引（按 url 可回填 handle/date/text）：
{json.dumps(compact, ensure_ascii=False)}
"""
    _write_debug_file(
        f"{run_ts}_l1_stage2_input.txt",
        "\n\n".join(
            [
                "[meta]",
                "phase=stage2_finalize",
                f"tweets={len(tweets)}",
                "",
                "[prompt]",
                prompt_stage2,
            ]
        ),
    )
    resp2 = llm.invoke([HumanMessage(content=prompt_stage2)])
    text2 = _to_text(resp2)
    try:
        obj = _parse_json_obj(text2)
    except Exception as exc:
        _write_debug_file(
            f"{run_ts}_l1_stage2_output_error.json",
            json.dumps(
                {
                    "parse_error": str(exc),
                    "raw_text": text2,
                    "stage1_draft": draft_obj,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        raise
    modules = _dedupe_modules_by_url(_safe_modules(obj))
    _write_debug_file(
        f"{run_ts}_l1_stage2_output.json",
        json.dumps(
            {
                "raw_text": text2,
                "parsed_modules": modules,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    print(
        "[xbrief][llm][l1] stage=done "
        f"themes={len(modules.get('themes', []))} "
        f"p0={len(modules.get('p0_events', []))} "
        f"quotes={len(modules.get('top_quotes', []))} "
        f"cats={len(modules.get('category_updates', []))} "
        f"risk={len(modules.get('risk_signals', []))} "
        f"elapsed_ms={elapsed_ms}"
    )
    return modules


def translate_display_content(payload: dict[str, Any], modules: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """
    第二层翻译：只翻译会展示到前端模块的推文内容，不做全量翻译。
    """
    t0 = time.perf_counter()
    run_ts = time.strftime("%Y%m%d_%H%M%S")
    tweets: list[dict[str, Any]] = list(payload.get("tweets", []))
    if not tweets:
        print("[xbrief][llm][l2] stage=skip reason=no_tweets")
        return payload
    llm = _llm_for_role(cfg, role="translator")
    url_to_idx: dict[str, int] = {}
    for i, t in enumerate(tweets):
        u = str(t.get("url", "")).strip()
        if u:
            url_to_idx[u] = i

    target_indexes: list[int] = []
    seen: set[int] = set()

    def _push_url(url: str) -> None:
        idx = url_to_idx.get((url or "").strip())
        if idx is None:
            return
        if idx in seen:
            return
        seen.add(idx)
        target_indexes.append(idx)

    for theme in modules.get("themes", []) or []:
        for sample in theme.get("samples", []) or []:
            _push_url(str(sample.get("url", "")))
    for e in modules.get("p0_events", []) or []:
        _push_url(str(e.get("url", "")))
    for c in modules.get("category_updates", []) or []:
        for item in c.get("items", []) or []:
            _push_url(str(item.get("url", "")))
    for q in modules.get("top_quotes", []) or []:
        _push_url(str(q.get("url", "")))

    if not target_indexes:
        print("[xbrief][llm][l2] stage=skip reason=no_display_targets")
        return payload

    src_texts = [str(tweets[i].get("title", "")).strip() for i in target_indexes]
    _write_debug_file(
        f"{run_ts}_l2_input.json",
        json.dumps(
            {
                "target_indexes": target_indexes,
                "target_count": len(target_indexes),
                "targets": [
                    {
                        "idx": i,
                        "handle": tweets[i].get("handle", ""),
                        "url": tweets[i].get("url", ""),
                        "title": tweets[i].get("title", ""),
                    }
                    for i in target_indexes
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
    print(
        f"[xbrief][llm][l2] stage=start target_count={len(target_indexes)} "
        f"chunk_size=20 total_tweets={len(tweets)}"
    )
    zh_texts = _translate_texts(llm, src_texts, chunk_size=20)

    out = [dict(t) for t in tweets]
    for i, zh in zip(target_indexes, zh_texts):
        out[i]["title_zh"] = zh or out[i].get("title", "")
    _write_debug_file(
        f"{run_ts}_l2_output.json",
        json.dumps(
            {
                "target_indexes": target_indexes,
                "broadcast_zh": zh_texts,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )

    cloned = dict(payload)
    cloned["tweets"] = out
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    print(f"[xbrief][llm][l2] stage=done translated={len(target_indexes)} elapsed_ms={elapsed_ms}")
    return cloned


def build_fallback_modules(payload: dict[str, Any]) -> dict[str, Any]:
    tweets = payload.get("tweets", [])
    if not tweets:
        return {
            "themes": [],
            "p0_events": [],
            "top_quotes": [],
            "category_updates": [],
            "risk_signals": [],
        }

    theme_counter: Counter[str] = Counter()
    for t in tweets:
        text = (t.get("title") or "").lower()
        if any(k in text for k in ("gpt", "claude", "llm", "model", "openai")):
            theme_counter["模型能力"] += 1
        elif any(k in text for k in ("gpu", "chip", "nvidia", "compute", "inference")):
            theme_counter["算力与芯片"] += 1
        elif any(k in text for k in ("fund", "valuation", "ipo", "acquire", "merger")):
            theme_counter["投融资与并购"] += 1
        elif any(k in text for k in ("stock", "market", "trading", "etf", "crypto", "price")):
            theme_counter["交易与市场"] += 1
        else:
            theme_counter["其他"] += 1

    themes = []
    for idx, (k, v) in enumerate(theme_counter.most_common(3), start=1):
        themes.append(
            {
                "id": f"t{idx}",
                "title": k,
                "subtitle": f"近30天样本 {v} 条",
                "bullets": [f"{k}相关讨论热度位居前列。"],
            }
        )

    latest_tweets = sorted(tweets, key=lambda x: x.get("published_at", ""), reverse=True)
    p0_events = []
    top_quotes = []
    for i, t in enumerate(latest_tweets[:6], start=1):
        p0_events.append(
            {
                "id": f"p{i}",
                "title": (t.get("title") or "")[:60] or "关键动态",
                "meta": f"@{t.get('handle','')} | {t.get('published_at','')}",
                "summary": (t.get("title") or "")[:180],
                "url": t.get("url", ""),
            }
        )
        if i <= 3:
            top_quotes.append(
                {
                    "id": f"q{i}",
                    "quote": (t.get("title") or "")[:160],
                    "speaker": f"@{t.get('handle','')}",
                    "date": t.get("published_at", ""),
                    "note": "自动抽取",
                    "url": t.get("url", ""),
                }
            )

    acc_counter: Counter[str] = Counter([t.get("handle", "") for t in tweets])
    category_updates = []
    for i, (handle, cnt) in enumerate(acc_counter.most_common(4), start=1):
        category_updates.append(
            {
                "id": f"c{i}",
                "title": f"@{handle}",
                "subtitle": f"活跃推文 {cnt} 条",
                "level": "P1",
                "items": [{"text": f"该账号近30天持续活跃，建议重点跟踪。", "url": ""}],
            }
        )

    risk_signals = [
        {
            "id": "r1",
            "level": "MID",
            "title": "已启用规则兜底",
            "detail": "本次 LLM 结构化输出为空，已切换到规则归纳结果。",
        }
    ]
    return {
        "themes": themes,
        "p0_events": p0_events,
        "top_quotes": top_quotes,
        "category_updates": category_updates,
        "risk_signals": risk_signals,
    }

