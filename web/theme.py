import streamlit as st

from web.ui_shell import (
    COLOR_NAV_RAIL_BASE,
    COLOR_NAV_RAIL_EDGE,
    SIDEBAR_WIDTH_PX,
)


def apply_theme() -> None:
    """Apply a minimal professional dark style (centered layout + panel chrome)."""
    sw = SIDEBAR_WIDTH_PX
    rail_edge = COLOR_NAV_RAIL_EDGE
    rail_base = COLOR_NAV_RAIL_BASE
    _nav_shell = f"""
<style>
/* === AppCanvas：主画布（与侧栏同系底色 + 扫光）=== */
.stApp {{
  font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Inter, sans-serif;
  color: #e5e7eb;
  background: radial-gradient(1200px 600px at 10% -10%, rgba(99, 102, 241, 0.12), transparent 55%),
    radial-gradient(900px 500px at 90% 0%, rgba(34, 211, 238, 0.08), transparent 50%),
    #0b1220;
}}
/* === NavRail：仅展开态固定宽度；收缩态交给 Streamlit 原生逻辑 === */
[data-testid="stSidebar"][aria-expanded="true"] {{
  width: {sw}px !important;
  min-width: {sw}px !important;
  max-width: {sw}px !important;
  background: {rail_base} !important;
  border-right: 1px solid {rail_edge} !important;
  box-shadow: inset -8px 0 24px -12px rgba(2, 6, 23, 0.45);
}}
[data-testid="stSidebar"][aria-expanded="true"] > div:first-child,
[data-testid="stSidebar"][aria-expanded="true"] [data-testid="stSidebarContent"] {{
  width: 100%;
  background: {rail_base} !important;
  padding: 0 !important;
}}
[data-testid="stSidebar"][aria-expanded="true"] [data-testid="stVerticalBlock"] {{
  padding: 0.45rem 0.3rem 0.7rem 0.3rem;
}}
[data-testid="stSidebar"][aria-expanded="false"] {{
  width: 0 !important;
  min-width: 0 !important;
  max-width: 0 !important;
  border-right: 0 !important;
  box-shadow: none !important;
}}
/* NavMenu：option_menu iframe 铺满导航轨 */
[data-testid="stSidebar"] iframe {{
  width: 100% !important;
  min-height: 300px;
  border: none !important;
}}
"""
    _work_pane = """
.main .block-container {
  max-width: __CONTENT_MAX__;
  padding-top: 1.25rem;
  padding-bottom: 2.5rem;
  padding-left: max(1rem, 3vw);
  padding-right: max(1rem, 3vw);
}
.ta-page-title {
  font-size: 1.5rem;
  font-weight: 600;
  letter-spacing: -0.03em;
  margin: 0 0 0.35rem 0;
  color: #f8fafc;
}
.ta-page-desc {
  font-size: 0.92rem;
  color: #94a3b8;
  margin: 0 0 1.25rem 0;
  line-height: 1.45;
}
.ta-data-as-of {
  font-size: 0.88rem;
  color: #cbd5e1;
  background: rgba(30, 41, 59, 0.65);
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 10px;
  padding: 10px 14px;
  margin: 0 0 1rem 0;
  line-height: 1.45;
}
.ta-card {
  background: #111827;
  border: 1px solid #1f2937;
  border-radius: 10px;
  padding: 12px 14px;
  margin-bottom: 10px;
}
.ta-muted {
  color: #9ca3af;
}
.ta-ok {
  color: #22c55e;
}
.ta-warn {
  color: #f59e0b;
}
.ta-bad {
  color: #ef4444;
}
.ta-summary {
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 10px;
  padding: 14px 16px;
  margin: 8px 0 16px 0;
}
.ta-log-panel {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.82rem;
  max-height: 420px;
  overflow-y: auto;
  white-space: pre-wrap;
  background: #020617;
  border: 1px solid #1e293b;
  border-radius: 8px;
  padding: 10px;
}
/* Bordered sections (Streamlit container border) */
[data-testid="stVerticalBlockBorderWrapper"] {
  background: rgba(15, 23, 42, 0.45) !important;
  border: 1px solid rgba(148, 163, 184, 0.22) !important;
  border-radius: 14px !important;
  padding: 1rem 1.15rem 1.1rem 1.15rem !important;
  margin-bottom: 1rem !important;
  box-shadow: 0 12px 32px rgba(2, 6, 23, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}
[data-testid="stVerticalBlockBorderWrapper"] h5 {
  margin-top: 0 !important;
  margin-bottom: 0.75rem !important;
  font-weight: 600 !important;
  font-size: 0.95rem !important;
  color: #cbd5e1 !important;
  letter-spacing: -0.02em;
}
/* 指标下方中文说明（st.caption） */
[data-testid="stHorizontalBlock"] [data-testid="stCaption"] {
  text-align: center;
  color: #94a3b8 !important;
  font-size: 0.78rem !important;
  line-height: 1.35 !important;
  margin-top: 0.1rem !important;
  padding-top: 0 !important;
}
.ta-glass-card {
  background: rgba(15, 23, 42, 0.55);
  border: 1px solid rgba(148, 163, 184, 0.32);
  border-radius: 14px;
  padding: 12px;
  margin-bottom: 12px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  box-shadow: 0 10px 24px rgba(2, 6, 23, 0.35), inset 0 1px 0 rgba(255,255,255,0.04);
}
.ta-news-card {
  background: rgba(15, 23, 42, 0.55);
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 14px;
  padding: 14px 16px 12px 16px;
  margin-bottom: 12px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  box-shadow: 0 10px 24px rgba(2, 6, 23, 0.3);
}
.ta-news-title {
  font-weight: 600;
  font-size: 0.98rem;
  margin: 0 0 0.35rem 0;
  color: #f1f5f9;
  line-height: 1.35;
}
.ta-news-meta {
  font-size: 0.75rem;
  color: #64748b;
  margin: 0 0 0.5rem 0;
}
.ta-news-body {
  font-size: 0.88rem;
  color: #cbd5e1;
  margin: 0 0 0.5rem 0;
  line-height: 1.5;
}
.ta-news-link {
  margin: 0;
  font-size: 0.86rem;
}
.ta-news-link a {
  color: #818cf8;
  text-decoration: none;
  font-weight: 500;
}
.ta-news-link a:hover {
  text-decoration: underline;
  color: #a5b4fc;
}
/* Dashboard：横向指标条，收紧列布局带来的上方空白 */
[data-testid="stHorizontalBlock"] {
  gap: 0.4rem !important;
  align-items: stretch !important;
}
[data-testid="stHorizontalBlock"] > [data-testid="stVerticalBlock"] {
  flex: 1 1 0 !important;
  min-width: 0 !important;
  padding-top: 0 !important;
}
[data-testid="stHorizontalBlock"] [data-testid="stMetric"] {
  margin-top: 0 !important;
}
/* 仪表盘：宏观 / 主要指数 — 单卡内 主标题 → 大数字 → 副标题（左对齐，参考财务卡片层级） */
.ta-stat-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  margin-top: 0.35rem;
  align-items: stretch;
}
.ta-stat-row .ta-stat-card {
  flex: 1 1 148px;
  min-width: min(148px, 100%);
  box-sizing: border-box;
  background: rgba(248, 250, 252, 0.04);
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 12px;
  padding: 14px 16px 12px 16px;
  text-align: left;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.04) inset;
}
.ta-stat-title {
  font-size: 0.82rem;
  font-weight: 500;
  color: #94a3b8;
  margin: 0 0 8px 0;
  line-height: 1.3;
  letter-spacing: -0.01em;
}
.ta-stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #f8fafc;
  margin: 0 0 8px 0;
  line-height: 1.15;
  letter-spacing: -0.03em;
}
.ta-stat-value.ta-stat-up {
  color: #22c55e;
}
.ta-stat-value.ta-stat-down {
  color: #ef4444;
}
.ta-stat-sub {
  font-size: 0.78rem;
  font-weight: 400;
  color: #64748b;
  margin: 0;
  line-height: 1.4;
}
/* 大盘总结（markdown-it 渲染块） */
.ta-digest-prose .ta-digest-inner h1,
.ta-digest-prose .ta-digest-inner h2,
.ta-digest-prose .ta-digest-inner h3,
.ta-digest-prose .ta-digest-inner h4,
.ta-digest-prose .ta-digest-inner h5 {
  color: #f1f5f9 !important;
  font-weight: 600;
  margin: 1rem 0 0.5rem 0;
  line-height: 1.35;
  letter-spacing: -0.02em;
}
.ta-digest-prose .ta-digest-inner h5:first-child,
.ta-digest-prose .ta-digest-inner h4:first-child {
  margin-top: 0;
}
.ta-digest-prose .ta-digest-inner p {
  margin: 0.4rem 0 0.65rem 0;
  color: #e2e8f0;
}
.ta-digest-prose .ta-digest-inner ul,
.ta-digest-prose .ta-digest-inner ol {
  margin: 0.35rem 0 0.75rem 1.1rem;
  padding: 0;
  color: #cbd5e1;
}
.ta-digest-prose .ta-digest-inner li {
  margin: 0.25rem 0;
  line-height: 1.55;
}
.ta-digest-prose .ta-digest-inner strong {
  color: #f8fafc;
  font-weight: 600;
}
.ta-digest-prose .ta-digest-inner a {
  color: #a5b4fc;
  text-decoration: none;
}
.ta-digest-prose .ta-digest-inner a:hover {
  text-decoration: underline;
}
.ta-digest-prose .ta-digest-inner hr {
  border: none;
  border-top: 1px solid rgba(148, 163, 184, 0.25);
  margin: 1rem 0;
}
/* 大盘总结：分节 <details>（嵌在仪表盘 expander 内，避免嵌套 Streamlit expander） */
.ta-digest-details {
  margin: 0.55rem 0;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 10px;
  padding: 4px 12px 12px 14px;
  background: rgba(15, 23, 42, 0.42);
}
.ta-digest-summary {
  cursor: pointer;
  font-weight: 600;
  color: #a5b4fc;
  padding: 6px 0 4px 0;
  font-size: 0.9rem;
  list-style: none;
}
.ta-digest-summary::-webkit-details-marker {
  display: none;
}
.ta-digest-details-body {
  padding-top: 8px;
  margin-top: 4px;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
  font-size: 0.9rem;
  line-height: 1.68;
  color: #e2e8f0;
}
.ta-digest-details-body .ta-digest-inner p {
  margin: 0.35rem 0 0.55rem 0;
  color: #e2e8f0;
}
.ta-digest-details-body .ta-digest-inner ul,
.ta-digest-details-body .ta-digest-inner ol {
  margin: 0.3rem 0 0.6rem 1.1rem;
  color: #cbd5e1;
}
.ta-digest-details-body .ta-digest-inner li {
  margin: 0.2rem 0;
  line-height: 1.55;
}
.ta-digest-details-body .ta-digest-inner strong {
  color: #f8fafc;
}
/* 仪表盘大块折叠：与页面背景区分的轻边框 */
section.main [data-testid="stExpander"] {
  border: 1px solid rgba(148, 163, 184, 0.18) !important;
  border-radius: 12px !important;
  background: rgba(15, 23, 42, 0.28) !important;
  margin-bottom: 0.65rem !important;
}
/* Top 10 新闻：每行约 2～3 条（宽屏 3 列，中屏 2 列） */
.ta-news-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0.85rem;
  margin-top: 0.35rem;
}
@media (min-width: 1100px) {
  .ta-news-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 700px) {
  .ta-news-grid {
    grid-template-columns: 1fr;
  }
}
.ta-news-grid .ta-news-card {
  margin-bottom: 0;
  min-height: 200px;
  height: 100%;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}
.ta-news-grid .ta-news-body {
  flex: 1 1 auto;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 5;
  -webkit-box-orient: vertical;
}
[data-testid="stMetric"] {
  background: rgba(15, 23, 42, 0.65);
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 12px;
  padding: 10px 12px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}
[data-testid="stMetric"] label {
  color: #94a3b8 !important;
}
[data-testid="stMetric"] [data-testid="stMetricValue"] {
  color: #f8fafc !important;
}
.ta-news-date {
  font-weight: 400;
  color: #94a3b8;
  font-size: 0.85em;
}
.ta-stance-bull { color: #22c55e; font-weight: 600; }
.ta-stance-bear { color: #ef4444; font-weight: 600; }
.ta-stance-neut { color: #94a3b8; font-weight: 600; }
.ta-stance-unknown { color: #64748b; font-weight: 500; }
.ta-llm-hdr {
  font-size: 0.78rem;
  font-weight: 600;
  color: #a5b4fc;
  margin: 0.35rem 0 0.15rem 0;
}
.ta-llm-body {
  font-size: 0.82rem;
  color: #cbd5e1;
  margin: 0 0 0.5rem 0;
  line-height: 1.45;
}
.ta-news-link-row {
  margin: 0.35rem 0 0 0;
  font-size: 0.84rem;
}
.ta-news-link-original {
  color: #94a3b8;
  text-decoration: none;
}
.ta-news-link-original:hover { text-decoration: underline; color: #cbd5e1; }
.ta-news-read-full {
  color: #818cf8;
  font-weight: 600;
  text-decoration: none;
}
.ta-news-read-full:hover { text-decoration: underline; color: #a5b4fc; }
.ta-news-link-sep { color: #475569; }
.ta-news-hint {
  color: #64748b;
  font-size: 0.8rem;
  font-weight: 400;
}
.ta-macro-list {
  margin: 0.35rem 0 0 0;
  padding-left: 1.1rem;
  color: #e2e8f0;
  font-size: 0.88rem;
  line-height: 1.5;
}
.ta-macro-hint {
  color: #94a3b8;
  font-size: 0.8rem;
}
</style>
"""
    st.markdown(_nav_shell + _work_pane.replace("__CONTENT_MAX__", "min(1180px, 100%)"), unsafe_allow_html=True)
