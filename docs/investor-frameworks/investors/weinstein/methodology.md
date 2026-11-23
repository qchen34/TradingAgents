# Weinstein — 个股深度分析 Playbook

## 13. Stan Weinstein
**体系：** Stage Analysis（阶段分析）· **风格：** 趋势阶段 + 量价确认

### 核心信条
> "只在 Stage 2 上升趋势中买入；Stage 3/4 以防守和出场为主。"

### 选股 / 阶段标准
- **MA150 方向**：Stage 2 要求 MA150 向上；Stage 1 底部积累为观察；Stage 3/4 回避新开仓
- **月线结构**：Stage 2 中期/后期看月度高点是否持续抬升
- **量价**：上涨周放量、回调缩量为健康；上涨缩量/下跌放量为趋势衰竭信号
- **相对强度**：RS vs 大盘（如 QQQ）同步或领先走强

### 入场逻辑
- **买点 A**：突破长期盘整 + 放量，贴近 MA150 附近（±5% 健康区）
- **买点 B**：Stage 2 中期，3–5 周强势整理后再次突破
- **禁追**：偏离 MA150 过度延伸（延伸区/过度延伸）、Stage 2 中后期且 PE 显著高于行业

### 持仓 / 退出
- **止损**：跌破 MA150 或趋势买点规则失效（如 MACD/量能转弱）
- **退出**：进入 Stage 3 派发或 MA150 走平下拐

### 对每只股票要问的问题
1. 当前处于 Stage 几？MA150 斜率与价格相对 MA150 偏离是否匹配该阶段？
2. 量价与 RS 是否支持「仍在 Stage 2」？
3. 规则化 trend_buy 结论与阶段标签是否一致？若冲突，哪条客观数据更可信？
4. 若不在 Stage 2，应等待什么价格/结构条件再考虑建仓？

---

## 使用指南：如何用这份文档分析 Watchlist 中的股票

### 快速诊断流程（5 步）

**Step 1：定性分类**  
这只股票属于哪种类型？
- 已验证护城河的成熟企业 → 优先看 Buffett + Marks
- 高增长早期科技 → 优先看 Cathie Wood + Druckenmiller
- 被市场抛弃的冷门股 → 优先看 Klarman + Burry + Greenblatt
- 有管理层/战略问题的公司 → 优先看 Ackman + Loeb
- 宏观敏感型资产 → 优先看 Druckenmiller + Dalio + PTJ
- 趋势股 / 已走出底部的成长股 → 优先看 **Weinstein** + Druckenmiller + PTJ

**Step 2：选 2–3 个最相关的大佬视角做深度分析**（合成模块需覆盖全部 13 位评分）

**Step 2b（模块合成）：** 大佬框架分析模块对 Watchlist 标的输出 **13 位**独立评分（含 Weinstein），再汇总综合判决。

**Step 3：用所选大佬的"要问的问题"逐一回答**

**Step 4：赔率检查（PTJ 方法）**  
- 上行情景 × 概率 vs 下行情景 × 概率
- 赔率低于 2:1 → 不值得建仓

**Step 5：写出一段结论**  
> "[股票代码] 在 [大佬A] 框架下评分 X/5，理由是____；在 [大佬B] 框架下评分 Y/5，理由是____；综合来看，当前价格的风险赔率____，计划____。"

---

## 版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-05-21 | 初始版本，12位活跃投资人框架 |
| v1.1 | 2026-05-21 | 新增第13位 Stan Weinstein（Stage Analysis） |

---

*仅作个人研究参考，不构成投资建议*
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
