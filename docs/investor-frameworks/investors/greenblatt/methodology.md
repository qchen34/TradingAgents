# Greenblatt — 个股深度分析 Playbook

## 11. Joel Greenblatt
**机构：** Gotham Asset Management · **风格：** 特殊情况 / 神奇公式

### 核心信条
> "在市场短暂疯狂的时候，系统性地做那些让人不舒服的事，长期会赢。"

### 神奇公式（Magic Formula）
- **收益率（Earnings Yield）**= EBIT / 企业价值（EV）→ 越高越好（便宜）
- **资本回报率（ROIC）**= EBIT / （净固定资产 + 净营运资本）→ 越高越好（好公司）
- 两个指标综合排名最高的股票，就是神奇公式选出的标的

### 特殊情况
- **分拆股（Spinoffs）**：母公司分拆出的子公司，初期被机构抛售，往往被低估
- **破产重组后公司**：重组完成后负债大幅减少，盈利能力被低估
- **并购套利**：已宣布并购的目标公司，以折价套利价差

### 对每只股票要问的问题
1. 收益率 + ROIC 综合排名在同行业是什么水平？
2. 是否有特殊情况正在发生（分拆、重组、并购）？
3. 市场讨厌它的理由是暂时性的（坏季报、行业悲观情绪）还是结构性的？

---
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
