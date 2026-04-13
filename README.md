# 个性化多智能体金融分析工具

## 基于TradingAgents底层框架打造

- 【2026-04】搭建Webui仪表盘作为观察大盘数据的入口，个股分析作为TradingAgents分析工具的入口
- 【2026-04】后续预告：交易策略工具搭建中，包括回测，开仓信号，平仓信号等

基于 TradingAgents 多智能体框架，提供：

- 交互式 CLI 分析流程
- Streamlit WebUI（市场总览、个股分析、报告回看、持仓管理）
- 本地报告与快照持久化能力

> 仅用于研究与学习，不构成任何投资建议。

---

## 当前功能（WebUI）

WebUI 入口：`app.py`

一级页面（当前实现）：

1. **仪表盘**
   - 指数、宏观代理、板块 Top3、Top10 新闻
   - LLM 新闻立场与摘要
   - LLM 大盘总结
   - 手动刷新并写入快照（latest + history）
2. **个股分析**
   - 启动分析任务、查看运行进度与日志
   - 展示最新报告摘要
   - 内嵌历史报告浏览
3. **策略**
   - 当前为占位页（后续实现）
4. **股票筛选**
   - 搜索/排序/查看 ticker
   - 跳转股票详情页
5. **股票详情**
   - 概览指标、最新分析引导、历史报告
6. **持仓**
   - 本地持仓录入、同 ticker 合并、均价重算

产品规格文档见：`docs/webui_prd.md`

---

## 项目结构（核心目录）

```text
TradingAgents/
├── app.py                        # WebUI 入口
├── web/
│   ├── pages/                    # 各页面实现
│   ├── services/                 # 数据拉取/存储/LLM 服务
│   ├── theme.py                  # 全局主题样式
│   ├── sidebar_nav.py            # 侧栏导航
│   ├── history.py                # 报告历史扫描
│   └── report_viewer.py          # 报告渲染
├── tradingagents/                # 多智能体核心框架
├── cli/                          # CLI 入口与交互
├── docs/                         # 文档
├── data/                         # 本地运行数据（建议忽略运行产物）
├── reports/                      # Web 分析报告输出（运行产物）
├── results/                      # CLI 结果输出（运行产物）
└── eval_results/                 # 评估日志输出（运行产物）
```

---

## 安装

```bash
git clone https://github.com/qchen34/TradingAgents.git
cd TradingAgents
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 环境变量

至少配置一个 LLM Provider 的 Key（按需）：

```bash
export OPENAI_API_KEY=...
export SILICONFLOW_API_KEY=...
export GOOGLE_API_KEY=...
export ANTHROPIC_API_KEY=...
export XAI_API_KEY=...
export OPENROUTER_API_KEY=...
export ALPHA_VANTAGE_API_KEY=...
```

也可使用 `.env`：

```bash
cp .env.example .env
```

---

## 启动方式

### 1) 启动 WebUI

```bash
streamlit run app.py
```

### 或
### 2) 启动 CLI

```bash
python -m cli.main
# 或（安装后）
tradingagents
```

---

## 运行数据与输出目录说明

以下目录/文件通常为运行自动生成，建议加入 `.gitignore`：

- `eval_results/`
- `reports/`
- `results/`
- `data/dashboard/history/`
- `data/dashboard/latest.json`
- `data/cache/`
- `data/portfolio.json`

如果你希望仓库“干净可复现”，建议只保留代码与文档，运行产物不入库。




## 引用

本项目底层引用Tauric Research的TradingAgents框架：https://github.com/TauricResearch/TradingAgents