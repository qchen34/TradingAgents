# GitHub 定时自动分析

本仓库通过 **新增** 脚本 [`scripts/github_scheduled_analysis.py`](../scripts/github_scheduled_analysis.py) 与 [`.github/workflows/`](../.github/workflows/) 下的 workflow，在 Actions 中无交互跑完整分析。  
**不会修改** 本地交互式 CLI（`tradingagents` / `python -m cli.main analyze`）。

## 推荐：在「Run workflow」里填参数（无需配置 Variables）

在 GitHub 打开 **Actions** → 选择下列任一 workflow → **Run workflow**，在表单中填写即可（留空则见下方「优先级」说明）。

**`Scheduled analysis (manual now)`** 仅支持手动运行，适合第一次试用：**`ticker` 为必填文本**；**`analysis_date` 留空则使用 UTC 当日**；**`research_depth` 为下拉单选**（与 CLI 中 Shallow=1 / Medium=3 / Deep=5 一致）。

**`Scheduled analysis (daily)`** / **`Scheduled analysis (weekly)`** 除定时 cron 外，同样支持手动运行；手动时也可只在表单里填写，而不去仓库 Settings 里配 Variables。

表单字段与含义（对齐本地 CLI）：

| 表单字段 (workflow input) | 说明 |
|----------------------------|------|
| `ticker` | 标的代码，如 `QQQM`（**manual workflow 中为必填**） |
| `analysis_date` | `YYYY-MM-DD`；**留空则使用 UTC 当日**（与「默认今日」一致；Runner 使用 UTC） |
| `research_depth` | **下拉单选**：`1`（Shallow）、`3`（Medium）、`5`（Deep），默认 `1` |
| `analyst_list` | 文本：`all` 或逗号分隔 `market,social,news,fundamentals` |
| `llm_provider` | 如 `openai`、`siliconflow` |
| `backend_url` | OpenAI 兼容 API 的 base URL |
| `quick_model` / `deep_model` | quick / deep 模型 id |
| `output_language` | 如 `English`、`中文` |
| `openai_reasoning_effort` | OpenAI 系 reasoning effort（若适用） |
| `google_thinking_level` | Gemini thinking（若适用） |
| `anthropic_effort` | Claude effort（若适用） |

**优先级**：某一字段在表单里**非空**（或 `research_depth` 下拉已选）→ 使用表单值；**留空** → 再尝试同名的 **Repository Variable**（见下表）；`analysis_date` 仍无则使用 **UTC 当日**；其余仍无则脚本使用 `default_config`。

## Repository Secrets（敏感，对应 `.env` 中的密钥）

在 **Settings → Secrets and variables → Actions** 中按需配置（未使用的可留空）：

| Secret | 说明 |
|--------|------|
| `OPENAI_API_KEY` | OpenAI |
| `SILICONFLOW_API_KEY` | SiliconFlow |
| `GOOGLE_API_KEY` | Google Gemini |
| `ANTHROPIC_API_KEY` | Anthropic |
| `XAI_API_KEY` | xAI Grok |
| `OPENROUTER_API_KEY` | OpenRouter |
| `ALPHA_VANTAGE_API_KEY` | Alpha Vantage（若数据源需要） |

Workflow 会将它们注入为同名环境变量，与本地 `.env` 一致。

## Repository Variables（非敏感，可选）

以下 **仅在**「Run workflow 表单留空」或 **无人值守的定时 cron** 需要默认配置时使用。若你每次都在表单里填完整，可以**不配置**任何 Variable。

| Variable | 典型用途 |
|----------|----------|
| `SCHEDULE_TICKER` | **定时 cron 无人运行时**必填之一：标的代码（或每次手动在表单填 `ticker`） |
| `SCHEDULE_ANALYSIS_DATE` | 后备分析日；不设且表单也未填时，工作流使用 **UTC 当日** |
| `SCHEDULE_ANALYST_LIST` | 表单 `analyst_list` 留空时的后备 |
| `SCHEDULE_RESEARCH_DEPTH` | 定时任务无表单时，作为 1/3/5 的后备 |
| `SCHEDULE_LLM_PROVIDER` | 表单留空时的后备 |
| `SCHEDULE_BACKEND_URL` | 表单留空时的后备 |
| `SCHEDULE_QUICK_MODEL` | 表单留空时的后备 |
| `SCHEDULE_DEEP_MODEL` | 表单留空时的后备 |
| `SCHEDULE_OUTPUT_LANGUAGE` | 表单留空时的后备 |
| `SCHEDULE_OPENAI_REASONING_EFFORT` | 表单留空时的后备 |
| `SCHEDULE_GOOGLE_THINKING_LEVEL` | 表单留空时的后备 |
| `SCHEDULE_ANTHROPIC_EFFORT` | 表单留空时的后备 |

## Workflows

- **`scheduled-analysis-manual.yml`**：仅手动运行，在表单中填参即可（可不配置任何 Variable）。
- **`scheduled-analysis-daily.yml`** / **`scheduled-analysis-weekly.yml`**：支持 **定时 cron**（UTC）与 **手动 Run workflow**。  
  - **手动运行**：在表单里填写 `ticker` 等即可，不必去 Settings 配 Variables。  
  - **定时、无人值守**：`workflow_dispatch` 表单不可用，此时需在 Repository Variables 中至少设置 **`SCHEDULE_TICKER`**（其他项可选用 Variables 作为默认）；分析日不设则用 **UTC 当日**。

`cron` 使用 **UTC**，请自行换算本地时间。

## 产物

- 每次运行将报告写入 `reports/_ci/<run_id>/`（与本地 `reports/TQQQ_*` 目录结构相同：`complete_report.md` 与子目录）。
- 通过 **Actions → 对应运行 → Artifacts** 下载 zip；默认保留 14 天。

## 本地模拟（无 UI）

在包含 `pyproject.toml` 的目录下：

```bash
pip install -e .
export OPENAI_API_KEY=...   # 或其他 provider 的 key
mkdir -p reports/_ci/test
python scripts/github_scheduled_analysis.py \
  --ticker SPY \
  --date 2026-04-01 \
  --output-dir reports/_ci/test
```

也可用与 CI 相同的环境变量名（`SCHEDULE_*`）代替部分参数。

## 并发与超时

- `timeout-minutes: 240` 可按实际 LLM 耗时调整。
- `concurrency` 按分支分组，避免同一分支上多次定时重叠；如需完全禁止排队可再收紧策略。
