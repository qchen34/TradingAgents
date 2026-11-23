# 个股追踪页面 PRD（v1.2）

## 1. 定位与范围

- 路由：`/analysis`（原「个股分析」，重命名为**个股追踪**）
- 入口文件：`frontend/src/app/analysis/page.tsx`（当前为空壳）
- 详情子页：`frontend/src/app/stock-detail/page.tsx`（当前为空壳）
- 数据来源标的：`data/follows/ai_compute_watchlist.json` 中「核心13」组
- 风格：与 Dashboard 页面保持一致（深色、monospace、`border-[#2B2F36]`、`bg-[#161A1E]`）

---

## 2. 页面结构与导航

```
/analysis（个股追踪主页）
├── 顶部控制栏（刷新按钮 + 最后更新时间 + 刷新进度）
└── 核心13 追踪总表（每行整行可点击）
    └── onClick → router.push('/stock-detail?ticker=NVDA')

/stock-detail?ticker=NVDA（个股详情页）
├── Sticky Header（固定顶部，滚动不消失）
│   ├── [ ← 个股追踪 ] 面包屑导航
│   └── Ticker · 公司名 · 收盘价 · 涨跌幅 · Stage标签 · 买点类型 · 评分
└── 三个可展开/收起的大模块（accordion，纵向依次排列）
    ├── 大模块 1：基本面分析（收起时显示摘要 chip）
    │   ├── 中卡片 1-A：估值指标
    │   ├── 中卡片 1-B：盈利质量
    │   ├── 中卡片 1-C：财报达标历史
    │   └── 中卡片 1-D：分析师共识
    ├── 大模块 2：技术面分析（收起时显示摘要 chip）
    │   ├── 中卡片 2-A：趋势结构
    │   ├── 中卡片 2-B：动量与量能
    │   └── 中卡片 2-C：Weinstein 技术图表（全宽）
    └── 大模块 3：LLM 深度分析（收起时显示摘要 chip）
        ├── 中卡片 3-A：阶段判断
        ├── 中卡片 3-B：买点指引
        ├── 中卡片 3-C：催化剂监控
        └── 中卡片 3-D：收入达标评估
```

**导航实现**：主表每行 `onClick` 使用 Next.js `useRouter().push('/stock-detail?ticker=' + ticker)`，详情页用 `useSearchParams().get('ticker')` 读取。

---

## 3. 指标体系

### 3.1 yfinance 可用性核查（实测结果）

**稳定可用（直接取 `Ticker.info`）**

| 字段        | yfinance key                   | 备注                       |
| --------- | ------------------------------ | ------------------------ |
| 市值        | `marketCap`                    |                          |
| PE TTM    | `trailingPE`                   |                          |
| 预期 PE     | `forwardPE`                    | 基于分析师一致预期，可能缺失           |
| PS TTM    | `priceToSalesTrailing12Months` |                          |
| 收入增速 YoY  | `revenueGrowth`                | trailing 12M             |
| 毛利率       | `grossMargins`                 |                          |
| 营业利润率     | `operatingMargins`             |                          |
| 自由现金流     | `freeCashflow`                 |                          |
| 分析师目标价    | `targetMeanPrice`              |                          |
| 分析师评级     | `recommendationKey`            | strong_buy/buy/hold/sell |
| 分析师人数     | `numberOfAnalystOpinions`      |                          |
| PEG ratio | `pegRatio`                     |                          |
| EV/EBITDA | `enterpriseToEbitda`           |                          |

**可用但需要额外处理**

| 字段          | 获取方式                                               | 备注                                         |
| ----------- | -------------------------------------------------- | ------------------------------------------ |
| 最近4季 EPS 达标 | `Ticker.earnings_history` DataFrame                | 含 epsActual/epsEstimate/surprisePercent，稳定 |
| 下次财报日       | `Ticker.calendar['Earnings Date']`                 | 返回 list，取第一个                               |
| 分析师买卖分布     | `Ticker.recommendations_summary` DataFrame         | strongBuy/buy/hold/sell/strongSell 最新月     |
| 季度营收实际值     | `Ticker.quarterly_income_stmt` 中 `Total Revenue` 行 | 可计算 QoQ 增速                                 |

**无法从 yfinance 获取（需注明 N/A 或依赖 LLM）**

| 字段                                     | 原因                                       | 替代方案                                     |
| -------------------------------------- | ---------------------------------------- | ---------------------------------------- |
| 历史季度**收入预期 vs 实际**（revenue surprise %） | yfinance earnings_history 只有 EPS，无收入预期历史 | 仅展示季度环比增速作为替代；收入超预期评估交给 LLM              |
| `Ticker.get_earnings_dates()`          | 测试环境 TLS 错误，部分网络不可用                      | 改用 `Ticker.calendar['Earnings Date']` 替代 |
| 短期借贷/做空比例                              | yfinance 无此字段                            | 不展示                                      |
| 机构持仓变化（delta）                          | 数据有限且滞后                                  | 不展示                                      |

### 3.2 全量指标表

| 指标组          | 字段                              | 类型         | 来源              | 获取方式                       | 需 LLM |
| ------------ | ------------------------------- | ---------- | --------------- | -------------------------- | ----- |
| **基础行情**     | `close` 收盘价                     | float      | yfinance        | `history()`                | 否     |
|              | `change_pct` 当日涨跌幅              | float%     | yfinance        | `history()`                | 否     |
|              | `high_52w` 52周高                 | float      | yfinance        | 计算                         | 否     |
|              | `pullback_from_52w_high` 距高回撤   | float%     | yfinance        | 计算                         | 否     |
| **基本面**      | `market_cap`                    | float      | yfinance        | `info`                     | 否     |
|              | `pe_ttm` PE TTM                 | float      | yfinance        | `info`                     | 否     |
|              | `pe_fwd` 预期 PE                  | float      | yfinance        | `info`                     | 否     |
|              | `ps_ttm` PS TTM                 | float      | yfinance        | `info`                     | 否     |
|              | `peg_ratio`                     | float      | yfinance        | `info`                     | 否     |
|              | `debt_to_equity` D/E            | float      | yfinance        | `info`                     | 否     |
|              | `ev_ebitda` EV/EBITDA           | float      | yfinance        | `info`                     | 否     |
|              | `revenue_growth_yoy` 收入增速       | float%     | yfinance        | `info`                     | 否     |
|              | `eps_growth_5y_pct` EPS Past 5Y% | float%   | yfinance        | `income_stmt` CAGR         | 否     |
|              | `sales_growth_5y_pct` Sales Past 5Y% | float% | yfinance      | `income_stmt` CAGR         | 否     |
|              | `eps_growth_this_y_pct` EPS This Y% | float% | yfinance      | `get_earnings_estimate` 0y | 否     |
|              | `eps_growth_next_y_pct` EPS Next Y% | float% | yfinance      | `get_earnings_estimate` +1y | 否    |
|              | `eps_growth_next_5y_pct` EPS Next 5Y% | float% | yfinance    | `get_growth_estimates` LTG | 否     |
|              | `eps_growth_qoq_pct` EPS Q/Q%   | float%     | yfinance        | `quarterly_income_stmt`    | 否     |
|              | `sales_growth_qoq_pct` Sales Q/Q% | float%   | yfinance        | `quarterly_income_stmt`    | 否     |
|              | `gross_margin` 毛利率              | float%     | yfinance        | `info`                     | 否     |
|              | `operating_margin` 营业利润率        | float%     | yfinance        | `info`                     | 否     |
|              | `free_cashflow` 自由现金流           | float      | yfinance        | `info`                     | 否     |
|              | `analyst_target` 分析师目标价         | float      | yfinance        | `info`                     | 否     |
|              | `analyst_rating` 综合评级           | str        | yfinance        | `info`                     | 否     |
|              | `analyst_count` 分析师人数           | int        | yfinance        | `info`                     | 否     |
|              | `analyst_breakdown` 买卖分布        | dict       | yfinance        | `recommendations_summary`  | 否     |
|              | `eps_history` 最近4季 EPS 达标       | list[dict] | yfinance        | `earnings_history`         | 否     |
|              | `quarterly_revenue` 季度营收        | list[dict] | yfinance        | `quarterly_income_stmt`    | 否     |
|              | `next_earnings_date` 下次财报       | date       | yfinance        | `calendar`                 | 否     |
|              | `eps_guidance_range` EPS 指引区间   | dict       | yfinance        | `calendar`                 | 否     |
|              | `revenue_guidance_range` 收入指引区间 | dict       | yfinance        | `calendar`                 | 否     |
|              | `revenue_surprise_pct` 收入超预期率   | **N/A**    | 无原始来源           | **LLM 根据季报语义判断**           | **是** |
| **技术面（原始）**  | `ma50`, `ma150`                 | float      | 计算              | 滚动均线                       | 否     |
|              | `pct_vs_ma150` 偏离MA150          | float%     | 计算              | 同上                         | 否     |
|              | `ma150_slope_4w` MA150斜率        | float%     | 计算              | 同上                         | 否     |
|              | `rsi14` RSI(14)                 | float      | 计算              | 同上                         | 否     |
|              | `rs_slope_3m` RS vs QQQ 3M      | float%     | 计算              | 同上                         | 否     |
|              | `vol_ratio` 涨跌量比                | float      | 计算              | 同上                         | 否     |
|              | `volume_vs_ma20` 当日量/20日均量     | float      | 计算              | Volume÷MA20(量)              | 否     |
|              | `macd_line` / `macd_signal` / `macd_hist` | float | 计算        | MACD(12,26,9) 末值            | 否     |
|              | `macd_hist_slope` MACD柱斜率趋势     | str        | 计算              | 近5根柱线性拟合 up/down/flat | 否     |
|              | `golden_cross_label` MA50·200 摘要 | str        | 计算              | 金叉/死叉距今或排列            | 否     |
|              | `trend_buy` 规则化趋势买点           | dict       | 规则              | 见 `buy_point_methodology` 附录 | 否     |
|              | `obv_trend` OBV趋势               | str        | 计算              | 同上                         | 否     |
|              | `monthly_highs_trend` 月度高点趋势    | str        | 计算              | 同上                         | 否     |
|              | `ma_cross` 均线交叉                 | dict       | 计算              | 含 ma50_above_ma200、最近金叉/死叉事件 | 否     |
|              | `range_3m_pct` 3月振幅             | float%     | 计算              | 同上                         | 否     |
|              | `score` 综合评分                    | int 0–9    | 计算              | 规则评分                       | 否     |
|              | `extension_label` 偏离区间标签        | str        | 规则              | `extension_label()`        | 否     |
| **技术面（LLM）** | `stage_label` 阶段判断              | str        | LLM             | Thinking LLM               | **是** |
|              | `stage_narrative` 阶段叙述          | str        | LLM             | 同上                         | **是** |
|              | `action_type` 买点类型              | str        | LLM             | 同上                         | **是** |
|              | `next_buy_guidance` 买点价格指引      | str        | LLM             | 同上                         | **是** |
|              | `stop_reference` 止损参考           | float      | 规则+LLM          | MA150×0.92，LLM 可覆盖         | 部分    |
|              | `catalysts` 催化剂监控               | list[str]  | LLM             | 同上                         | **是** |
|              | `revenue_surprise_assessment`   | str        | LLM             | 结合季度营收数据判断                 | **是** |
|              | `confidence` 分析置信度              | str        | LLM             | 同上                         | **是** |

### 3.3 追踪总表精简列（主视图）

```
# | Ticker | 收盘 | 涨跌 | RSI | 量/MA20 | MACD柱 | 金叉摘要 | 规则买点 | PE | 行业PE | PEG | EPS 5Y | EPS N.Y | D/E | 偏离MA150 | MA150斜率 | RS 3M | Stage | 买点类型 | 评分
```

每行整行可点击，鼠标 hover 显示 cursor:pointer，点击通过 Next.js router 跳转详情页。

---

## 4. 详情页多级卡片布局

### 4.1 整体信息架构（三级嵌套）

```
大模块（可展开/收起，accordion）
  └── 中卡片（固定显示在大模块内，grid 布局）
        └── 小指标行（label + value，最小粒度数据单元）
```

大模块默认**全部展开**；点击大模块 header 右侧箭头图标可收起，收起时 header 仍可见（显示该模块的核心摘要数字，方便快速扫描）。

### 4.2 页面整体骨架

```
/stock-detail?ticker=NVDA

━━━ STICKY HEADER ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[ ← 个股追踪 ]  NVDA · Nvidia   $131.20  +2.31%
                Stage 2 中后期  ·  买点：延伸后等回踩  ·  评分 7/9
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

▼ 大模块 1：基本面分析       [摘要：PE 45x · 收入+73% · 毛利 71%]
▼ 大模块 2：技术面分析       [摘要：规则买点标签 · 偏离MA150 · RSI · RS 3M · 评分]
▼ 大模块 3：LLM 深度分析    [摘要：Stage 2 中后期 · 延伸后等回踩 · 置信度 high]
```

### 4.3 大模块 1：基本面分析

中卡片 1-A（估值指标）：PE TTM / PE Fwd / PS TTM / PEG / EV/EBITDA  
中卡片 1-B（盈利质量）：毛利率 / 营业利润率 / 收入增速 YoY / 自由现金流  
中卡片 1-C（财报达标）：最近4季 EPS Beat + 季度营收 QoQ  
中卡片 1-D（分析师共识）：评级 / 目标价 / 分析师数 / 买卖分布 bar / 下次财报 / EPS指引  

### 4.4 大模块 2：技术面分析

中卡片 2-A（趋势结构）：收盘价 / MA50 / MA150 / MA200 / 偏离MA150 / MA150斜率 / 均线交叉状态  
中卡片 2-A2（趋势买点·规则）：`trend_buy.verdict` / 一句话摘要 / 标签 / 「若未到买点」条件列表  
中卡片 2-B（动量与量能）：RSI(14) / RS vs QQQ 3M / 涨跌量比 / 量÷20日均 / MACD 柱与斜率 / OBV趋势 / 3月振幅 / 月度高点 / 综合评分 / 偏离区间  
中卡片 2-C（Weinstein 图表，全宽）：PNG 含 Price·MA·Volume·RSI·MACD·RS vs QQQ（`/api/v1/stock-tracker/{ticker}/chart`）  

### 4.5 大模块 3：LLM 深度分析

中卡片 3-A（阶段判断，全宽）：阶段 / 置信度 / 叙述段落  
中卡片 3-B（买点指引）：买点类型 / 价格指引 / 止损参考  
中卡片 3-C（催化剂监控）：催化剂 bullet list  
中卡片 3-D（收入达标评估，全宽）：LLM 语义判断段落  

### 4.6 收起态摘要 chip

```
► 基本面分析    PE 45x  ·  收入+73%  ·  毛利 71%  ·  下次财报 05-21   [展开 ▼]
► 技术面分析    偏离MA150 +18%  ·  RS 3M +22%  ·  评分 7/9  ·  健康区   [展开 ▼]
► LLM深度分析   Stage 2 中后期  ·  延伸后等回踩  ·  置信度 high        [展开 ▼]
```

### 4.7 组件实现方式

- 大模块 accordion：React `useState` 控制 `isOpen`，chevron 图标旋转 180° 作为展开/收起指示
- 中卡片：`grid grid-cols-2 gap-2`（2列，全宽卡片单独占 `col-span-2`）
- 小指标行：`flex justify-between`，label 左对齐灰色，value 右对齐白色 monospace
- 大模块 header 收起态摘要 chip：从后端数据中提取 3–4 个最关键数字，拼成 `·` 分隔的行内标签

---

## 5. 刷新逻辑

与 Dashboard 一致的**异步后台刷新**：

```
前端 POST /api/v1/stock-tracker/refresh
  → 后端 background thread
      ① 循环核心13只 ticker
      ② 计算 Weinstein 技术指标（MA/RSI/RS/OBV）
      ③ yfinance Ticker.info / earnings_history / calendar 拉基本面
      ④ plot_ticker() 生成 PNG 存 data/stock_tracker/charts/{ticker}.png
      ⑤ Thinking LLM 批量输出结构化 JSON（见第6节）
      ⑥ 写 data/stock_tracker/latest.json
  → 轮询 GET /api/v1/stock-tracker/jobs/{job_id} 查进度
  → done 后 GET /api/v1/stock-tracker/latest 刷新页面
```

---

## 6. LLM 分析流程（Thinking LLM）

### 6.1 触发时机

仅在手动刷新时调用，页面加载直接读缓存。

### 6.2 模型

`deep_think_llm` 配置项（SiliconFlow `Qwen3-32B`，支持 thinking budget 模式）。

### 6.3 Prompt 输入结构

每次刷新一次性传入全部13只的指标，prompt 包含：

- 各 ticker 的技术面原始数字（close/ma50/ma150/pct_vs_ma150/ma150_slope_4w/rsi14/rs_slope_3m/score）
- 基本面摘要（pe_ttm/revenue_growth_yoy/gross_margin/eps_history 最近4季 surprisePercent）
- 季度营收实际值（最近4季 QoQ）
- 下次财报日

### 6.4 输出 Schema（严格 JSON 数组）

```json
[
  {
    "ticker": "NVDA",
    "stage_label": "Stage 2 中后期",
    "stage_narrative": "不超过150字的中文分析",
    "action_type": "延伸后等回踩",
    "next_buy_guidance": "等回踩 $MA50-$MA150×1.15 区间，RS 不破位",
    "stop_reference": 109.0,
    "catalysts": ["下次财报 2026-05-21", "Blackwell 出货节奏"],
    "revenue_surprise_assessment": "最近2季收入环比加速，超预期可能性中等",
    "confidence": "high"
  }
]
```

**枚举约束**

- `stage_label`：`Stage 1 / Stage 2 早期 / Stage 2 中后期 / Stage 3 / Stage 4`
- `action_type`：`买点A候选 / 买点A/B低偏离区 / 买点B等待区 / 延伸后等回踩 / 等待MA150上拐 / 禁追`
- `confidence`：`high / medium / low`
- 输出纯 JSON 数组，无 markdown 围栏，无额外文字

---

## 7. 后端新增 API（FastAPI）

在 `backend/api/main.py` 新增 4 个路由：

| 方法   | 路径                                     | 说明                                                       |
| ---- | -------------------------------------- | -------------------------------------------------------- |
| GET  | `/api/v1/stock-tracker/latest`         | 返回 `data/stock_tracker/latest.json`                      |
| POST | `/api/v1/stock-tracker/refresh`        | 触发异步刷新，返回 `{job_id, status}`                             |
| GET  | `/api/v1/stock-tracker/jobs/{job_id}`  | 查询刷新进度                                                   |
| GET  | `/api/v1/stock-tracker/{ticker}/chart` | 返回 `data/stock_tracker/charts/{ticker}.png`（`image/png`） |

---

## 8. 文件变更清单

```text
新增：
  web/services/stock_tracker_service.py   # 指标计算 + LLM 调用
  data/stock_tracker/latest.json          # 运行产物（.gitignore）
  data/stock_tracker/charts/{ticker}.png  # 运行产物（.gitignore）

修改：
  backend/api/main.py      # 新增4条路由
  backend/api/services.py  # 新增4个 service 函数
  frontend/src/app/analysis/page.tsx        # 改写为追踪总表
  frontend/src/app/stock-detail/page.tsx    # 改写为卡片式详情页
  frontend/src/lib/api.ts                   # 新增4个 API 调用函数
  .gitignore                                # 追加 data/stock_tracker/
```

---

## 9. 实施优先级

- P0：后端 service 骨架 + API 路由 + latest.json schema + 前端主表格（LLM字段占位「待分析」）
- P1：yfinance 基本面字段 + Weinstein 技术指标完整接入 + Chart PNG 生成接口
- P2：Thinking LLM 分析流程接入，详情页 LLM 区展示
- P3：详情页全量卡片完善（财报历史图示、分析师分布 bar）
