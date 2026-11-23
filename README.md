# TradingAgents（个性化金融研究工作台）

基于 [TradingAgents](https://github.com/TauricResearch/TradingAgents) 底层框架的扩展版本，面向「研究与学习」场景。**当前主力界面为 Next.js + FastAPI**。

> 仅用于研究与学习，不构成任何投资建议。

## 你可以用它做什么

- **Next.js 控制台**：仪表盘、策略与 X 简报等（`frontend/`）。
- **FastAPI 后端**：为前端提供 JSON API（`backend/`）。
- **CLI 多智能体分析**：交互式标的分析与报告输出（`cli/`）。
- **本地数据持久化**：报告、仪表盘快照与日志。

## 快速开始

### 1) 安装 Python 依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

说明：`requirements.txt` 使用可编辑安装 `-e .`，依赖列表以 **[pyproject.toml](pyproject.toml)** 为准。

安装后可使用 `tradingagents` CLI：

```bash
pip install -e .
```

### 2) 配置环境变量

```bash
cp .env.example .env
```

按需填写 LLM 与各功能所需的 Key（参见 `.env.example`）。

## 启动方式（推荐）

### A. FastAPI + Next.js（主栈）

```bash
# 终端 1：API
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000 --reload

# 终端 2：前端（需设置 NEXT_PUBLIC_API_BASE）
cd frontend
export NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
npm install
npm run dev
```

- API: `http://127.0.0.1:8000`
- 前端: `http://127.0.0.1:3000`

### B. 一键并行（FastAPI + Next.js）

```bash
bash scripts/start_dual_stack.sh
```

### C. CLI 分析

```bash
python -m cli.main
# 或
tradingagents analyze
```

## Vercel 部署前端

详见 [docs/vercel_deploy.md](docs/vercel_deploy.md)（根目录选 `frontend`，配置 `NEXT_PUBLIC_API_BASE`）。

## 依赖检查（开发）

在虚拟环境中可运行：

```bash
pip install deptry
deptry .
```

`[tool.deptry]` 已写在 `pyproject.toml`（包名与 import 映射、部分路径排除）。

## 项目结构（核心目录）

```text
TradingAgents/
├── backend/                  # FastAPI
├── frontend/                 # Next.js
├── web/                      # 服务层与策略共享（供 FastAPI 使用）
├── tradingagents/            # 多智能体核心
├── cli/                      # CLI
├── scripts/                  # 启动脚本、开发用脚本
└── docs/                     # 文档
```

## 运行产物（建议保持不入库）

- `eval_results/`, `reports/`, `results/`
- `data/dashboard/history/`, `data/dashboard/latest.json`, `data/cache/`, `data/portfolio.json`

## 常见问题

- **前端报缺少 `NEXT_PUBLIC_API_BASE`**：先 `export NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000`（或生产 API 地址）。
- **没有分析/LLM 结果**：检查 `.env` 中相关 API Key。

## 致谢

底层框架来自 Tauric Research 的 TradingAgents：
<https://github.com/TauricResearch/TradingAgents>
