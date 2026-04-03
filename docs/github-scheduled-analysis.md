# GitHub 定时自动分析

本仓库通过 **新增** 脚本 [`scripts/github_scheduled_analysis.py`](../scripts/github_scheduled_analysis.py) 与 [`.github/workflows/`](../.github/workflows/) 下的 workflow，在 Actions 中无交互跑完整分析。  
**不会修改** 本地交互式 CLI（`tradingagents` / `python -m cli.main analyze`）。

## 前置条件

- GitHub 仓库根目录须为包含 `pyproject.toml` 的目录（与本 `docs` 文件夹同级）。若你的远端仓库多包了一层父目录，请在 workflow 里增加 `defaults.run.working-directory` 并相应调整 Artifact 路径。
- `schedule` 使用 **UTC**。请自行把本地时间换算为 cron。

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

## Repository Variables（非敏感）

| Variable | 必填 | 说明 |
|----------|------|------|
| `SCHEDULE_TICKER` | 定时运行时必填 | 标的代码，如 `QQQM` |
| `SCHEDULE_ANALYSIS_DATE` | 否 | `YYYY-MM-DD`；不填则定时任务使用 **UTC 意义下的昨天** |
| `SCHEDULE_ANALYST_LIST` | 否 | `all` 或逗号分隔：`market,social,news,fundamentals` |
| `SCHEDULE_RESEARCH_DEPTH` | 否 | `1`、`3` 或 `5`（与本地 CLI 深度一致） |
| `SCHEDULE_LLM_PROVIDER` | 否 | 如 `openai`、`siliconflow`；不填用 `default_config` |
| `SCHEDULE_BACKEND_URL` | 否 | 兼容 OpenAI 的 API base |
| `SCHEDULE_QUICK_MODEL` | 否 | quick 模型名 |
| `SCHEDULE_DEEP_MODEL` | 否 | deep 模型名 |
| `SCHEDULE_OUTPUT_LANGUAGE` | 否 | 如 `English`、`中文` |
| `SCHEDULE_OPENAI_REASONING_EFFORT` | 否 | OpenAI 系 reasoning effort |
| `SCHEDULE_GOOGLE_THINKING_LEVEL` | 否 | Gemini thinking |
| `SCHEDULE_ANTHROPIC_EFFORT` | 否 | Claude effort |

## Workflows

- **`scheduled-analysis-daily.yml`**：`cron: "13 0 * * *"`（每天 00:13 UTC）— 请按需要修改。
- **`scheduled-analysis-weekly.yml`**：`cron: "15 1 * * 1"`（每周一 01:15 UTC）— 不需要每周跑时可删除该文件或清空 `on.schedule`。

二者均支持 **`workflow_dispatch`**：手动运行时需填写 `ticker` 与 `analysis_date`，会覆盖 Variables 中的 ticker/date 逻辑。

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
