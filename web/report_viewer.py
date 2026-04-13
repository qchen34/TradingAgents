from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import streamlit as st

# complete_report.md 中 ## 标题 -> 折叠区中文标题（与 cli/main.py save_report_to_disk 一致）
SECTION_H2_CN: Dict[str, str] = {
    "I. Analyst Team Reports": "分析师团队报告",
    "II. Research Team Decision": "研究团队结论",
    "III. Trading Team Plan": "交易团队计划",
    "IV. Risk Management Team Decision": "风险管理团队结论",
    "V. Portfolio Manager Decision": "组合经理决策（全文节）",
}


def _read_if_exists(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _parse_h2_sections(md: str) -> List[Tuple[str, str]]:
    """按二级标题 `## ` 切分（不含 `###`）。返回 (标题文本, 正文)。"""
    lines = md.splitlines()
    sections: List[Tuple[str, str]] = []
    current_title: str | None = None
    buf: List[str] = []
    for line in lines:
        if line.startswith("## ") and not line.startswith("###"):
            if current_title is not None:
                sections.append((current_title, "\n".join(buf).strip()))
            current_title = line[3:].strip()
            buf = []
        else:
            buf.append(line)
    if current_title is not None:
        sections.append((current_title, "\n".join(buf).strip()))
    return sections


def _is_final_section_title(title: str) -> bool:
    t = title.strip()
    return t.startswith("V.") or "Portfolio Manager Decision" in t


def _section_expander_label(title: str) -> str:
    return SECTION_H2_CN.get(title.strip(), title.strip())


def collect_snapshot_snippets(output_dir: str, max_chars: int = 2400) -> str:
    """运行过程中尽量拼接已有 Markdown 片段。"""
    base = Path(output_dir)
    if not base.is_dir():
        return ""
    parts: List[str] = []
    budget = max_chars

    complete = base / "complete_report.md"
    if complete.is_file():
        text = complete.read_text(encoding="utf-8", errors="replace")
        snippet = text[:budget]
        parts.append(f"### complete_report.md（预览）\n{snippet}")
        return "\n\n".join(parts)

    for sub, title in (
        (base / "1_analysts", "分析师"),
        (base / "2_research", "研究"),
        (base / "3_trading", "交易"),
    ):
        if not sub.is_dir():
            continue
        mds = sorted(sub.glob("*.md"))
        for md in mds:
            if budget <= 0:
                break
            chunk = md.read_text(encoding="utf-8", errors="replace")
            take = min(len(chunk), budget)
            parts.append(f"### {title}/{md.name}\n{chunk[:take]}")
            budget -= take
        if budget <= 0:
            break

    return "\n\n".join(parts) if parts else "_尚无分文件输出。_"


def render_snapshot_preview(output_dir: str, max_chars: int = 2400) -> None:
    """管线仍在写入时展示磁盘上已有片段。"""
    body = collect_snapshot_snippets(output_dir, max_chars=max_chars)
    if body:
        st.markdown(body)
    else:
        st.caption("等待分析产出写入 reports 目录…")


def render_report_focused(output_dir: str) -> None:
    """优先展示最终交易决策，其余章节以折叠目录形式浏览。"""
    base = Path(output_dir)
    if not base.exists():
        st.warning("未找到报告目录。")
        return

    decision_path = base / "5_portfolio" / "decision.md"
    complete_path = base / "complete_report.md"

    final_from_file = ""
    if decision_path.is_file():
        final_from_file = decision_path.read_text(encoding="utf-8", errors="replace")

    sections: List[Tuple[str, str]] = []
    if complete_path.is_file():
        sections = _parse_h2_sections(complete_path.read_text(encoding="utf-8", errors="replace"))

    final_from_complete = ""
    for title, body in sections:
        if _is_final_section_title(title):
            final_from_complete = body
            break

    hero = (final_from_file or final_from_complete or "").strip()
    if hero:
        st.markdown("#### 最终交易决策")
        with st.container(border=True):
            st.markdown(hero)
    elif not sections and not complete_path.is_file():
        st.info("暂无报告内容。")

    for title, body in sections:
        if _is_final_section_title(title):
            continue
        if not body.strip():
            continue
        label = _section_expander_label(title)
        with st.expander(label, expanded=False):
            st.markdown(body)

    with st.expander("分文件浏览（进阶）", expanded=False):
        render_report_tabs(output_dir)


def render_report_tabs(output_dir: str) -> None:
    base = Path(output_dir)
    if not base.exists():
        st.warning("尚未生成报告目录。")
        return

    mapping: Dict[str, Path] = {
        "分析师": base / "1_analysts",
        "研究": base / "2_research",
        "交易": base / "3_trading",
        "风险": base / "4_risk",
        "组合": base / "5_portfolio",
        "完整报告": base / "complete_report.md",
    }
    tabs = st.tabs(list(mapping.keys()))
    for name, tab in zip(mapping.keys(), tabs):
        with tab:
            target = mapping[name]
            if target.is_dir():
                md_files = sorted(target.glob("*.md"))
                if not md_files:
                    st.info("暂无内容。")
                    continue
                for md in md_files:
                    st.markdown(f"#### {md.name}")
                    st.markdown(_read_if_exists(md))
            else:
                content = _read_if_exists(target)
                if content:
                    st.markdown(content)
                else:
                    st.info("暂无内容。")
