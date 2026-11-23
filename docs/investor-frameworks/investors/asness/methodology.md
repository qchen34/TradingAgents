# Asness — 个股深度分析 Playbook

## 10. Cliff Asness
**机构：** AQR Capital Management · **风格：** 多因子量化 / 系统化

### 核心信条
> "因子溢价是真实的，但会经历痛苦的回撤期。坚持纪律是获取因子回报的唯一方法。"

### 核心因子框架
| 因子 | 定义 | 代理指标 |
|------|------|---------|
| **价值（Value）** | 便宜的资产长期跑赢 | B/P、E/P、CF/P、销售额/市值 |
| **动量（Momentum）** | 近期上涨的资产短期内继续上涨 | 过去 12 个月收益（去掉最近 1 个月） |
| **质量（Quality）** | 高盈利质量公司长期跑赢 | ROE、盈利稳定性、低杠杆 |
| **低波动（Low Vol）** | 低波动资产风险调整后回报更高 | Beta、历史波动率 |

### 使用方法
- 对 Watchlist 股票按四个因子分别打分（1–5分）
- 综合评分高 + 任何单一因子不极端低 → 进入候选池
- 不择时，系统性执行

### 对每只股票要问的问题
1. 在价值、动量、质量、低波动四个维度分别是什么水平？
2. 当前的价格走势是否与基本面因子一致？
3. 这只股票的因子暴露是否分散了我的整体组合风险？

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
