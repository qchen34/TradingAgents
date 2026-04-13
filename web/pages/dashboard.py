from __future__ import annotations

import html
from datetime import datetime

import streamlit as st

try:
    from markdown_it import MarkdownIt
except ImportError:  # 极简环境可回退为原始 Markdown
    MarkdownIt = None  # type: ignore[misc, assignment]

from web.services.market_data import (
    INDEX_SUBTITLE_CN,
    SECTOR_SUBTITLE_CN,
    load_dashboard_display,
    refresh_dashboard_cache,
)

# 指标卡第 4 行「描述」文案来源（勿与 tradingagents 底层混淆；均在 web/services/market_data.py）：
# - 主要指数：字典 INDEX_SUBTITLE_CN（各 ticker 对应中文说明）
# - 宏观与利率：常量 MACRO_ENTRIES 每项第 3 个元素 hint，经 get_macro_strip() 写入 macro_strip[].hint

STANCE_LABEL_CN = {
    "bullish": "看多",
    "bearish": "看空",
    "neutral": "中性",
    "unknown": "未评估",
}

STANCE_CLASS = {
    "bullish": "ta-stance-bull",
    "bearish": "ta-stance-bear",
    "neutral": "ta-stance-neut",
    "unknown": "ta-stance-unknown",
}


def _metric_label_ticker(ticker: str) -> str:
    return "VIX" if ticker == "^VIX" else ticker


def _e(s: object) -> str:
    return html.escape(str(s), quote=True)


def _delta_direction(change_pct: float | None) -> bool | None:
    if change_pct is None:
        return None
    if change_pct > 0:
        return True
    if change_pct < 0:
        return False
    return None


def _stat_card_html(
    code: str,
    value: str,
    change_vs_prev: str,
    description: str,
    *,
    positive: bool | None = None,
) -> str:
    """单卡四层：标的代码 → 数值 → 较昨收涨跌 → 描述（左对齐，内联样式）。"""
    if positive is True:
        ch_color = "#22c55e"
    elif positive is False:
        ch_color = "#ef4444"
    else:
        ch_color = "#94a3b8"
    card = (
        "flex:1 1 148px;min-width:min(148px,100%);box-sizing:border-box;"
        "background:rgba(248,250,252,0.04);border:1px solid rgba(148,163,184,0.22);"
        "border-radius:12px;padding:14px 16px 12px 16px;text-align:left;"
    )
    return (
        f'<div style="{card}">'
        '<div style="font-size:0.82rem;font-weight:600;color:#94a3b8;margin:0 0 6px 0;line-height:1.3;">'
        f"{_e(code)}</div>"
        '<div style="font-size:1.5rem;font-weight:700;color:#f8fafc;margin:0 0 6px 0;'
        'line-height:1.15;letter-spacing:-0.03em;">'
        f"{_e(value)}</div>"
        f'<div style="font-size:0.88rem;font-weight:600;color:{ch_color};margin:0 0 8px 0;line-height:1.3;">'
        f"{_e(change_vs_prev)}</div>"
        '<div style="font-size:0.76rem;font-weight:400;color:#64748b;margin:0;line-height:1.45;">'
        f"{_e(description)}</div>"
        "</div>"
    )


def _stat_row_wrap(inner: str) -> str:
    row = (
        "display:flex;flex-wrap:wrap;gap:0.65rem;margin-top:0.35rem;"
        "align-items:stretch;width:100%;"
    )
    return f'<div style="{row}">{inner}</div>'


def _render_stat_row(html_fragment: str) -> None:
    """优先 st.html（对自定义 HTML/CSS 限制更少）；否则回退 markdown。"""
    html_fn = getattr(st, "html", None)
    if callable(html_fn):
        html_fn(html_fragment, width="stretch")
    else:
        st.markdown(html_fragment, unsafe_allow_html=True)


def _render_macro_two_rows(card_html_parts: list[str], per_row: int = 3) -> None:
    """宏观指标固定为两排：每排 per_row 张（默认 3+3）。"""
    rows: list[str] = []
    for i in range(0, len(card_html_parts), per_row):
        rows.append(_stat_row_wrap("".join(card_html_parts[i : i + per_row])))
    outer = (
        '<div style="display:flex;flex-direction:column;gap:0.65rem;width:100%;">'
        + "".join(rows)
        + "</div>"
    )
    _render_stat_row(outer)


def _parse_h5_sections(md: str) -> list[tuple[str, str]]:
    """按五级标题 `##### ` 切分。首个 `#####` 之前的正文会合并进第一节，避免「经济数据」漂在折叠区外。"""
    lines = md.splitlines()
    sections: list[tuple[str, str]] = []
    buf: list[str] = []
    pending_title: str | None = None
    lead_before_first: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("##### ") and not stripped.startswith("######"):
            title = stripped[6:].strip()
            if pending_title is not None:
                body = "\n".join(buf).strip()
                if len(sections) == 0 and lead_before_first:
                    pre = "\n".join(lead_before_first).strip()
                    if pre:
                        body = (pre + "\n\n" + body).strip() if body else pre
                    lead_before_first = []
                sections.append((pending_title, body))
                buf = []
            else:
                lead_before_first = list(buf)
                buf = []
            pending_title = title
        else:
            buf.append(line)

    if pending_title is not None:
        body = "\n".join(buf).strip()
        if len(sections) == 0 and lead_before_first:
            pre = "\n".join(lead_before_first).strip()
            if pre:
                body = (pre + "\n\n" + body).strip() if body else pre
        sections.append((pending_title, body))
    return sections


def _render_digest_markdown(digest: str) -> None:
    """整段 Markdown → HTML 单容器（无 ##### 分节时使用）。"""
    if MarkdownIt is None:
        st.markdown(digest)
        return
    inner = MarkdownIt().enable("table").render(digest)
    wrap = (
        '<div class="ta-digest-prose ta-digest-prose--block" style="'
        "background:rgba(15,23,42,0.6);border:1px solid rgba(148,163,184,0.22);"
        "border-radius:12px;border-left:4px solid #818cf8;padding:16px 20px 18px 20px;"
        "margin-top:6px;font-size:0.92rem;line-height:1.75;color:#e2e8f0;"
        '">'
        f'<div class="ta-digest-inner">{inner}</div></div>'
    )
    html_fn = getattr(st, "html", None)
    if callable(html_fn):
        html_fn(wrap, width="stretch")
    else:
        st.markdown(wrap, unsafe_allow_html=True)


def _render_digest_subsections_details(
    sections: list[tuple[str, str]],
    *,
    open_first: bool = True,
) -> None:
    """各 ##### 分节统一用 <details>；首节可默认展开（open），避免第一节单独用边框区与后续不一致。"""
    for i, (title, body) in enumerate(sections):
        label = (title or "").strip() or "分节"
        raw = body.strip() or "_（本节无正文）_"
        open_attr = ' open' if (open_first and i == 0) else ""
        if MarkdownIt is not None:
            inner = MarkdownIt().enable("table").render(raw)
            frag = (
                f'<details class="ta-digest-details"{open_attr}>'
                f'<summary class="ta-digest-summary">{_e(label)}</summary>'
                f'<div class="ta-digest-inner ta-digest-details-body">{inner}</div>'
                "</details>"
            )
        else:
            frag = (
                f'<details class="ta-digest-details"{open_attr}>'
                f'<summary class="ta-digest-summary">{_e(label)}</summary>'
                f'<div class="ta-digest-details-body"><pre style="white-space:pre-wrap;margin:0;">'
                f"{_e(raw)}</pre></div></details>"
            )
        html_fn = getattr(st, "html", None)
        if callable(html_fn):
            html_fn(frag, width="stretch")
        else:
            st.markdown(frag, unsafe_allow_html=True)


def _render_digest_structured(digest: str) -> None:
    """所有 ##### 分节统一为 <details>（首节默认展开），与「其他总结」折叠样式一致。"""
    sections = _parse_h5_sections(digest)
    if not sections:
        _render_digest_markdown(digest)
        return
    _render_digest_subsections_details(sections, open_first=True)


def _format_asof_line(data: dict) -> str:
    """仪表盘顶部：优先展示上次手动点击「更新」的 UTC 时间。"""
    fa = (data.get("fetched_at_utc") or "").strip()
    if fa:
        try:
            dt = datetime.fromisoformat(fa.replace("Z", "+00:00"))
            utc_s = dt.strftime("%Y-%m-%d %H:%M UTC")
            local_s = dt.astimezone().strftime("%Y-%m-%d %H:%M")
            return f"当前页数据对应上次手动更新时间：{utc_s}（本地 {local_s}）"
        except ValueError:
            return f"当前页数据对应上次手动更新时间：{fa}"
    et = (data.get("last_updated_et") or "").strip()
    if et:
        return (
            f"快照行情观察时间（ET）：{et}。"
            "尚未记录手动更新 UTC（请重新点击「更新市场数据」以写入归档时间）。"
        )
    return "暂无更新时间记录；请点击「更新市场数据」。"


def _news_article_html(n: dict) -> str:
    """速览卡片：外链「阅读原文」。"""
    title = html.escape(str(n.get("title", "N/A")))
    pub = (n.get("published_at") or "").strip()
    date_html = f'<span class="ta-news-date"> · {html.escape(pub)}</span>' if pub else ""
    prov = html.escape(str(n.get("provider", "Unknown")))
    summary = n.get("summary")
    link = n.get("link", "") or ""
    stance = n.get("stance") or "unknown"
    stance_label = html.escape(STANCE_LABEL_CN.get(stance, "未评估"))
    stance_cls = STANCE_CLASS.get(stance, "ta-stance-unknown")
    llm_text = (n.get("llm_summary") or "").strip()

    parts = [
        '<article class="ta-news-card">',
        f'<p class="ta-news-title">{title}{date_html}</p>',
        f'<p class="ta-news-meta">{prov} · <span class="{stance_cls}">{stance_label}</span></p>',
    ]
    if summary:
        parts.append(f'<p class="ta-news-body">{html.escape(str(summary))}</p>')
    if llm_text:
        parts.append('<p class="ta-llm-hdr">大模型解读</p>')
        parts.append(f'<p class="ta-llm-body">{html.escape(llm_text)}</p>')
    if link:
        safe_link = html.escape(str(link), quote=True)
        parts.append(
            '<p class="ta-news-link-row">'
            f'<a href="{safe_link}" class="ta-news-link-original" target="_blank" '
            'rel="noopener noreferrer">阅读原文</a>'
            "</p>"
        )
    else:
        parts.append('<p class="ta-news-hint">无媒体外链</p>')
    parts.append("</article>")
    return "".join(parts)


def render_dashboard() -> None:
    st.markdown(
        '<p class="ta-page-title">仪表盘</p>'
        '<p class="ta-page-desc">市场概览与快讯；点击「更新市场数据」将拉取 Yahoo 行情与新闻，'
        "并调用 Fast 模型生成新闻解读与大盘总结。</p>",
        unsafe_allow_html=True,
    )

    col_btn, col_status = st.columns([1, 2], gap="large")
    with col_btn:
        clicked = st.button("更新市场数据", key="refresh_dashboard")
    if clicked:
        # 仪表盘 LLM 与个股分析表单的 last_params 解耦，避免沿用分析任务里的 OpenAI/gpt-5.4-mini
        data, news = refresh_dashboard_cache(limit=10)
        st.session_state.dashboard_data = data
        st.session_state.dashboard_news = news
    else:
        data = st.session_state.get("dashboard_data")
        news = st.session_state.get("dashboard_news")
        if data is None:
            cached_data, cached_news = load_dashboard_display()
            if cached_data is not None:
                data = cached_data
                news = cached_news
                st.session_state.dashboard_data = cached_data
                st.session_state.dashboard_news = cached_news

    with col_status:
        if data is None:
            st.warning("当前无缓存数据。请点击左侧「更新市场数据」拉取最新行情。")
        else:
            st.caption(
                f"市场状态 `{data.get('market_status', 'N/A')}` · "
                f"行情快照 ET `{data.get('last_updated_et', 'N/A')}`"
            )
            lm = (data.get("llm_model") or "").strip()
            lp = (data.get("llm_provider") or "").strip()
            if lp and lm:
                st.caption(f"仪表盘 LLM：`{lp}` / `{lm}`")
            elif lm:
                st.caption(f"仪表盘 LLM（Quick）：`{lm}`")

    if data is None:
        return

    st.markdown(
        f'<p class="ta-data-as-of">{html.escape(_format_asof_line(data))}</p>',
        unsafe_allow_html=True,
    )

    digest = (data.get("market_digest_md") or "").strip()
    digest_err = (data.get("llm_digest_error") or "").strip()
    with st.expander("大盘总结（大模型）", expanded=True, key="dash_exp_digest"):
        if digest:
            _render_digest_structured(digest)
        else:
            st.info("总结暂不可用：模型未返回内容，或未配置密钥/调用失败。")
            if digest_err:
                st.code(digest_err, language="text")

    macro = data.get("macro_strip") or []
    if macro:
        with st.expander("宏观经济数据", expanded=True, key="dash_exp_macro"):
            st.caption("以下为市场可交易品种或收益率指数，非劳工部 CPI、非农等官方发布序列。")
            macro_cards = []
            for m in macro:
                ch = m.get("change_pct")
                dv = str(m.get("display_value", "N/A"))
                tk = str(m.get("ticker", ""))
                hint = str(m.get("hint", "")).strip()
                ch_s = f"{ch:+.2f}%" if ch is not None else "—"
                change_line = f"较昨收 {ch_s}"
                code = tk or "—"
                macro_cards.append(
                    _stat_card_html(
                        code,
                        dv,
                        change_line,
                        hint or "（无说明）",
                        positive=_delta_direction(ch),
                    )
                )
            _render_macro_two_rows(macro_cards, per_row=3)

    with st.expander("主要指数", expanded=True, key="dash_exp_idx"):
        rows = data.get("indexes", [])
        if not rows:
            st.info("暂无指数数据。")
        else:
            idx_cards = []
            for row in rows:
                price = f"{row.price:.2f}" if row.price is not None else "N/A"
                ch = row.change_pct
                ch_s = f"{ch:+.2f}%" if ch is not None else "—"
                desc = (INDEX_SUBTITLE_CN.get(row.ticker) or "").strip() or "（无说明）"
                idx_cards.append(
                    _stat_card_html(
                        _metric_label_ticker(row.ticker),
                        price,
                        f"较昨收 {ch_s}",
                        desc,
                        positive=_delta_direction(ch),
                    )
                )
            _render_stat_row(_stat_row_wrap("".join(idx_cards)))

    with st.expander("板块强弱 Top 3（代理 ETF）", expanded=True, key="dash_exp_sector"):
        sec = data.get("top3_sectors") or []
        if not sec:
            st.info("当前不可用，稍后重试。")
        else:
            sec_cards = []
            for row in sec[:3]:
                price = f"{row.price:.2f}" if row.price is not None else "N/A"
                ch = row.change_pct
                ch_s = f"{ch:+.2f}%" if ch is not None else "—"
                desc = (
                    SECTOR_SUBTITLE_CN.get(row.ticker, f"{row.ticker} 板块/主题 ETF（代理）")
                ).strip()
                sec_cards.append(
                    _stat_card_html(
                        row.ticker,
                        price,
                        f"较昨收 {ch_s}",
                        desc or "（无说明）",
                        positive=_delta_direction(ch),
                    )
                )
            _render_stat_row(_stat_row_wrap("".join(sec_cards)))

    news_list = news or st.session_state.get("dashboard_news") or []
    news_err = (data.get("llm_news_error") or "").strip()

    with st.expander("Top 10 财经新闻", expanded=True, key="dash_exp_news"):
        if news_err:
            st.warning("新闻情绪解读未完全成功，以下为服务端返回摘要：" + news_err[:280])
        if not news_list:
            st.info("暂无新闻数据（点击「更新市场数据」后可拉取）。")
        else:
            cells = "".join(_news_article_html(n) for n in news_list[:10])
            st.markdown(
                f'<div class="ta-news-grid" role="list">{cells}</div>',
                unsafe_allow_html=True,
            )
