# GitHub 定时自动分析

本仓库通过 **新增** 脚本 [`scripts/github_scheduled_analysis.py`](../scripts/github_scheduled_analysis.py) 与 [`.github/workflows/`](../.github/workflows/) 下的 workflow，在 Actions 中无交互跑完整分析。  
**不会修改** 本地交互式 CLI（`tradingagents` / `python -m cli.main analyze`）。

## 与本地 CLI 对齐（交互步骤复刻）

本地 [`cli/utils.py`](../cli/utils.py) 里 `get_user_selections()` 的步骤，在 GitHub 里由可复用工作流 **[`tradingagents-analysis-run.yml`](../.github/workflows/tradingagents-analysis-run.yml)** 实现：

| CLI 步骤 | GitHub Actions（`Run workflow` 表单） |
|----------|----------------------------------------|
| Step 1 Ticker（文本） | `ticker` 字符串 |
| Step 2 分析日（默认今日） | `analysis_date` 留空则 **UTC 当日**（与 CLI 默认「今天」一致；Runner 为 UTC） |
| Step 3 输出语言（单选） | `output_language` 下拉；选 `custom` 时填 `output_language_custom` |
| Step 4 分析师（多选 checkbox） | 四个 **boolean**：`include_market` / `include_social` / `include_news` / `include_fundamentals` |
| Step 5 研究深度（单选） | `research_depth`：`1` = Shallow，`3` = Medium，`5` = Deep（与 CLI 一致） |
| Step 6 Provider（单选） | `llm_provider`（与 `select_llm_provider` 列表一致） |
| Step 7 Quick / Deep 模型（单选） | `quick_model`、`deep_model`（选项来自 [`model_catalog.py`](../tradingagents/llm_clients/model_catalog.py)） |
| Step 8 Provider 附加（单选） | `google_thinking_level` / `openai_reasoning_effort` / `anthropic_effort`；非对应厂商时选 **`none`** |

`backend_url` **不再**在表单里手填，由所选 `llm_provider` **自动映射**（与 `cli/utils.py` 中 `BASE_URLS` 一致）。

## 推荐入口：手动工作流（完整表单）

在 **Actions** 中运行 **`Scheduled analysis (manual now)`** → **Run workflow**，即可看到上述全部选项（与 CLI 同序）。

底层调用 **[`tradingagents-analysis-run.yml`](../.github/workflows/tradingagents-analysis-run.yml)**。

## 定时任务（daily / weekly）：仅用 Variables

**[`scheduled-analysis-daily.yml`](../.github/workflows/scheduled-analysis-daily.yml)** / **[`scheduled-analysis-weekly.yml`](../.github/workflows/scheduled-analysis-weekly.yml)** 仅 **`schedule` 触发**，无表单；通过 **Repository Variables** 传入与可复用工作流相同的参数（带默认值）。

| Variable | 说明 |
|----------|------|
| `SCHEDULE_TICKER` | **必填**（cron 无人值守） |
| `SCHEDULE_ANALYSIS_DATE` | 可选；不填则与可复用逻辑一致（空则 UTC 当日） |
| `SCHEDULE_OUTPUT_LANGUAGE` | 默认 `English` |
| `SCHEDULE_OUTPUT_LANGUAGE_CUSTOM` | `OUTPUT_LANGUAGE=custom` 时的正文 |
| `SCHEDULE_INCLUDE_MARKET` 等 | 设为 `false` 可关闭对应分析师；未设置视为 **true** |
| `SCHEDULE_RESEARCH_DEPTH` | `1` / `3` / `5`，默认 `1` |
| `SCHEDULE_LLM_PROVIDER` | 默认 `openai` |
| `SCHEDULE_QUICK_MODEL` / `SCHEDULE_DEEP_MODEL` | 须与可复用 workflow 中 **choice 列表**完全一致 |
| `SCHEDULE_GOOGLE_THINKING_LEVEL` 等 | 默认 `none`；非 `none` 时须与厂商匹配 |

## Repository Secrets（敏感）

在 **Settings → Secrets and variables → Actions** 中按需配置：

| Secret | 说明 |
|--------|------|
| `OPENAI_API_KEY` | OpenAI |
| `SILICONFLOW_API_KEY` | SiliconFlow |
| `GOOGLE_API_KEY` | Google Gemini |
| `ANTHROPIC_API_KEY` | Anthropic |
| `XAI_API_KEY` | xAI Grok |
| `OPENROUTER_API_KEY` | OpenRouter |
| `ALPHA_VANTAGE_API_KEY` | Alpha Vantage（若需要） |

## 本地测试（与 Actions 同参）

在包含 `pyproject.toml` 的目录下安装依赖后，使用 **[`scripts/local_dispatch_like_cli.sh`](../scripts/local_dispatch_like_cli.sh)**，其参数与 **`tradingagents-analysis-run`** 一致（环境变量可覆盖默认值）：

```bash
cd /path/to/TradingAgents   # 含 pyproject.toml 的目录
source venv/bin/activate    # 若使用 venv
pip install -e .
export OPENAI_API_KEY=sk-...

chmod +x scripts/local_dispatch_like_cli.sh
./scripts/local_dispatch_like_cli.sh
```

常用覆盖示例：

```bash
TICKER=QQQM \
RESEARCH_DEPTH=3 \
LLM_PROVIDER=siliconflow \
QUICK_MODEL="Qwen/Qwen3-32B" \
DEEP_MODEL="deepseek-ai/DeepSeek-V3" \
./scripts/local_dispatch_like_cli.sh
```

报告输出在 `reports/_ci/local-test-<时间戳>/`。

更新 **`model_catalog` 模型列表** 后，可运行 `python scripts/generate_tradingagents_reusable_workflow.py` 查看需同步到 workflow 的 `choice` 选项（再粘贴进 `tradingagents-analysis-run.yml` 与 `scheduled-analysis-manual.yml`）。

## 产物

- 每次运行将报告写入 `reports/_ci/<run_id>/`，与本地 `reports/TQQQ_*` 结构一致。
- **Actions → 运行记录 → Artifacts** 下载 zip。

## 并发与超时

- 可复用工作流中 `timeout-minutes: 240` 可按需调整。
