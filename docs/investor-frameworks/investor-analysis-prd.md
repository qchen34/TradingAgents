# PRD：个股详情页 — 大佬框架投资分析模块

**版本：** v2.1  
**日期：** 2026-05-21  
**状态：** 已实现规范  

---

## 1. 背景与目标

### 1.1 现状
TradingAgents 详情页（`/stock-detail`）已有 Weinstein 阶段、趋势买点、基本面与分析师目标价。

**v1.0 问题：** 单次 LLM 同时扮演 13 位大佬并输出顶层「合成买卖价」，用户无法知道权重与计算方式，且易出现多重人格幻觉。

### 1.2 v2.0 目标（快速结论，保持）
- **13 次独立 LLM 调用**，每次仅一位投资框架（逐人 Agent）
- **每位大佬**输出：判决、评分、理想买入、止损、建议持有（[`framework-prompt-compact.md`](framework-prompt-compact.md)）
- **顶层 `summary`** 仅含可解释的**规则统计**（计票众数、理想买入中位数/区间），**不做** LLM 加权合成价位
- 与 stock_tracker 全量 `refresh` 解耦；模块内手动触发 Job

### 1.3 v2.1 目标（深度结论，新增）
- **快速 / 深度双模式**：同一 ticker 可分别缓存 `quick` 与 `deep`
- **深度**读取 `docs/investor-frameworks/investors/{slug}/methodology.md`（Per-Investor Playbook）
- **预计算**：`scripts/precompute_context.py` 注入 `computed_context`（均线、PE vs 行业、趋势买点等事实）
- 深度每人扩展字段：`investment_thesis`、`bull_case`、`bear_case`、`catalysts`、`position_sizing`、`analysis_steps_done`
- **仍无**第 14 次 LLM 合成买卖价

---

## 2. 用户价值

| 用户场景 | v1.0 | v2.0 快速 | v2.1 深度 |
|---------|------|-----------|-----------|
| 想知道「Buffett 会怎么买」 | 只有一行文字 | 独立买/止损/持有价 | + 论点、多空、催化剂、仓位 |
| 不信任黑箱合成价 | 顶层一组 entry/stop | 顶层仅计票 + 中位数 | 同左 |
| 担心价位幻觉 | LLM 心算 | compact 短 prompt | Playbook 分步 + script 事实 |
| 时间成本 | 一次快 | 3–8 分钟 | 8–15 分钟 |

---

## 3. 功能范围

### 3.1 In Scope（v2.1）
- `POST` body：`{ "mode": "quick" | "deep" }`（默认 `quick`）
- `GET` 返回 `{ ticker, quick, deep }`（v1/v2 扁平缓存兼容为 `quick`）
- `investor_analysis.json` schema **2.1**：`analyses[TK] = { quick?, deep? }`
- 13 份 `investors/{slug}/methodology.md` + [`manifest.json`](manifest.json)
- 共享 `precompute_context.py`（白名单，非用户脚本 exec）
- 前端：双按钮触发 + Tab 切换查看；深度卡片展示扩展字段
- CRCL 入 AI 算力 watchlist（`data/follows/ai_compute_watchlist.json`）

### 3.2 Out of Scope
- 第 14 次 LLM 叙事合成
- 13 个独立 Python 脚本（维护爆炸）→ 仅 1 个共享预计算
- 用户自选大佬子集
- 同一 ticker 同时跑 quick + deep 两个 Job（任意 mode 互斥一个 Job）

---

## 4. 参与分析的框架（13 位）

Buffett, Klarman, Marks, Druckenmiller, PTJ, Dalio, Cathie Wood, Ackman, Burry, Asness, Greenblatt, Loeb, Weinstein。  
索引见 [`manifest.json`](manifest.json)（`slug` → `methodology_path`）。

---

## 5. 数据架构

### 5.1 输入
`data/stock_tracker/latest.json` 单 ticker 快照。

### 5.2 存储（schema_version `2.1`）

路径：`data/stock_tracker/investor_analysis.json`

```json
{
  "schema_version": "2.1",
  "analyses": {
    "NVDA": {
      "quick": {
        "analysis_mode": "quick",
        "framework_version": "2.0",
        "summary": { "...": "..." },
        "framework_scores": [ "..."]
      },
      "deep": {
        "analysis_mode": "deep",
        "framework_version": "2.1-deep",
        "playbook_manifest_version": "1.0",
        "summary": { "...": "..." },
        "framework_scores": [
          {
            "investor": "Buffett",
            "investment_thesis": "...",
            "bull_case": "...",
            "bear_case": "...",
            "catalysts": ["..."],
            "position_sizing": "...",
            "entry": { "...": "..." },
            "stop_loss": { "...": "..." }
          }
        ]
      }
    }
  }
}
```

### 5.3 知识库分工

| 模式 | 知识库 | 预计算 | 版本标签 |
|------|--------|--------|----------|
| quick | `framework-prompt-compact.md` 单节 | 无 | `2.0` |
| deep | `investors/{slug}/methodology.md` | `precompute_context.py` | `2.1-deep` |

目录：

```
docs/investor-frameworks/
  manifest.json
  framework-prompt-compact.md
  master-investors-framework.md   # 溯源/总览
  investors/{slug}/methodology.md
  scripts/precompute_context.py
```

### 5.4 summary 规则（确定性，quick/deep 共用）
- `verdict`：13 票众数；平票 → `watch`
- `ideal_price_median` / `ideal_price_range`：各 `entry.ideal_price` 统计，UI 标注「非推荐仓位」
- `key_risks`：按 `score` 升序取 `concern` 去重，最多 4 条

### 5.5 script 边界
- 仅输出**事实与参考区间**（close、MA、PE 溢价、`trend_buy.verdict` 等）
- `verdict`、论点、最终买卖价由 LLM 在 Playbook 步骤下生成
- 通过 service 内 import/subprocess 调用仓库内脚本，禁止任意 exec

---

## 6. 后端

文件：[`web/services/investor_framework_service.py`](../../web/services/investor_framework_service.py)

| 能力 | quick | deep |
|------|-------|------|
| 框架加载 | `_extract_investor_compact` | `_load_investor_playbook(slug)` |
| 预计算 | — | `run_precompute(ticker, item, slug)` |
| 校验 | `_validate_single_row` | `_validate_single_row_deep` |
| 存取 | `save_investor_analysis(ticker, result, mode)` | 同左 |

API：
- `POST /api/v1/stock-tracker/investor-analysis/{ticker}` — body `{ "mode": "quick" | "deep" }`
- `GET /api/v1/stock-tracker/investor-analysis/{ticker}` — `{ ticker, quick, deep }`
- `GET /api/v1/stock-tracker/investor-analysis/jobs/{job_id}` — 含 `mode`

### 6.1 性能
- 并发 `max_workers=2`
- quick：约 3–8 分钟；deep：约 8–15 分钟

---

## 7. 前端

类型：`InvestorAnalysisRecord`、`InvestorAnalysisMode`、`triggerInvestorAnalysis(ticker, mode)`。

UI：[`investor-analysis-section.tsx`](../../frontend/src/components/investor-analysis-section.tsx)
- **快速结论** / **深度结论** 双按钮
- Tab 切换 `viewMode` 查看已缓存结果
- 深度卡片：thesis / bull / bear / catalysts / position_sizing
- 运行中进度区分模式耗时文案

详情页摘要：优先展示 `quick`，无则 `deep`。

---

## 8. 验收标准

- [ ] CRCL 在 watchlist；追踪刷新后 `latest.json` 含 CRCL
- [ ] 快速结论行为与 v2.0 一致（compact + 13 次）
- [ ] 深度结论独立缓存；UI 双按钮 + Tab 切换
- [ ] 深度至少 1 位 playbook 端到端（其余 fallback master 段落直至 playbook 完善）
- [ ] deep prompt / `data_snapshot` 可含预计算字段
- [ ] 同一 ticker 仅允许一个 Job（任意 mode）
- [ ] `npm run lint` && `npm run build` 通过

---

*文档版本：v2.1*
