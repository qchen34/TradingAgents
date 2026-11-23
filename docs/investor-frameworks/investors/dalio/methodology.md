# Dalio — 个股深度分析 Playbook

## 6. Ray Dalio
**机构：** Bridgewater Associates（已移交管理权，仍发表研究）· **风格：** 宏观周期 / 全天候

### 核心信条
> "债务周期是理解一切经济现象的钥匙。当债务不能再增长时，就是转折点。"

### 核心框架
- **长期债务周期**（75–100年）+ **短期信贷周期**（5–8年）
- **全天候配置**：股票 / 长期债券 / 中期债券 / 黄金 / 大宗商品，按风险贡献平衡
- **风险平价**：不以资金量，以风险量（波动率）分配权重

### 对每只股票/资产类别要问的问题
1. 当前处于债务周期的哪个阶段（扩张/去杠杆/压缩）？
2. 这类资产在当前宏观情景下（通胀/通缩/增长/衰退）的历史表现如何？
3. 持有这只股票是否增加了组合的真实风险集中度？

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
