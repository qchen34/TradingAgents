#!/usr/bin/env python3
"""从 master-investors-framework.md 生成 investors/{slug}/methodology.md（可重复运行）。"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FRAMEWORKS = REPO / "docs" / "investor-frameworks"
MASTER = FRAMEWORKS / "master-investors-framework.md"
MANIFEST = FRAMEWORKS / "manifest.json"
INVESTORS_DIR = FRAMEWORKS / "investors"

PLAYBOOK_FOOTER = """
---

## 深度分析 Playbook（执行清单）

### 1. 适用边界
对照上文框架判断本标的是否适用；不适用须在 concern 中说明。

### 2. 分析步骤（必须逐步覆盖，摘要写入 analysis_steps_done 数组）
1. 核对 computed_context 中的价格、均线、估值事实
2. 按本框架标准评估并给出 score（1-5）
3. 确定 verdict：buy / watch / avoid
4. 给出理想买入、最高追价、触发条件（纯数字）
5. 给出止损价与逻辑（stop.price < ideal_price <= max_chase_price）
6. 给出持有周期与仓位建议

### 3. 买点与止损
价位须引用 computed_context，禁止 N/A 或纯文字价。

### 4. 深度 JSON 额外字段
investment_thesis, bull_case, bear_case, catalysts（2-4条）, position_sizing, analysis_steps_done（3-6条短句）
"""

# master 章节标题 → manifest investor 名
CHAPTER_TO_INVESTOR: list[tuple[str, str]] = [
    (r"Warren Buffett", "Buffett"),
    (r"Seth Klarman", "Klarman"),
    (r"Howard Marks", "Marks"),
    (r"Stanley Druckenmiller", "Druckenmiller"),
    (r"Paul Tudor Jones", "PTJ"),
    (r"Ray Dalio", "Dalio"),
    (r"Cathie Wood", "Cathie Wood"),
    (r"Bill Ackman", "Ackman"),
    (r"Michael Burry", "Burry"),
    (r"Cliff Asness", "Asness"),
    (r"Joel Greenblatt", "Greenblatt"),
    (r"Daniel Loeb", "Loeb"),
    (r"Stan Weinstein", "Weinstein"),
]


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    slug_by_investor = {e["investor"]: e["slug"] for e in manifest["investors"]}
    text = MASTER.read_text(encoding="utf-8")
    parts = re.split(r"\n(?=## \d+\. )", text)
    chapters: dict[str, str] = {}
    for part in parts:
        if not part.strip().startswith("## "):
            continue
        for pattern, investor in CHAPTER_TO_INVESTOR:
            if pattern in part.split("\n", 1)[0]:
                chapters[investor] = part.strip()
                break

    INVESTORS_DIR.mkdir(parents=True, exist_ok=True)
    for investor, slug in slug_by_investor.items():
        body = chapters.get(investor, f"## {investor}\n（章节待补充）")
        out_dir = INVESTORS_DIR / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        content = f"# {investor} — 个股深度分析 Playbook\n\n{body}{PLAYBOOK_FOOTER}"
        (out_dir / "methodology.md").write_text(content, encoding="utf-8")
        print(f"Wrote {out_dir / 'methodology.md'}")


if __name__ == "__main__":
    main()
