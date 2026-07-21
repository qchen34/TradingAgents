# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A personalized fork of [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents), a multi-agent LLM framework that debates and produces trading decisions for a given ticker/date. This fork adds three UI layers on top of the core `tradingagents` framework:

1. **`tradingagents/`** — the original multi-agent trading framework (LangGraph-based agent pipeline). This is the reusable core; `main.py` shows the minimal way to drive it standalone.
2. **`cli/`** — a Typer + Rich interactive CLI (`python -m cli.main`) that wraps the framework with a live TUI showing agent status, tool calls, and reports as they stream in.
3. **`web/` + `app.py`** — a Streamlit dashboard (market overview, per-stock analysis, report history, portfolio tracking, strategy pages). This is the original/legacy WebUI and is being migrated off.
4. **`backend/api/` + `frontend/`** — a FastAPI backend and Next.js frontend that are actively replacing the Streamlit UI (see `docs/migration/`). New UI work should go here, not in `web/`.

All three UI layers (CLI, Streamlit, Next.js+FastAPI) can call into the same `tradingagents` core and, where applicable, the same `web/services/*` data/service modules (the FastAPI backend imports directly from `web.services.*`, e.g. `backend/api/main.py` imports `web.services.backtesting_core`).

Chinese is used throughout README, docs, and UI strings (this is a personal tool, not upstream TradingAgents); code identifiers and comments are in English.

## Common commands

### Setup
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # matplotlib/seaborn/fastapi/uvicorn only — most deps come via pyproject
pip install -e .                  # installs tradingagents + cli as importable packages (needed for `tradingagents` console script and for tests)
cp .env.example .env              # then fill in at least one LLM provider key
```
This project uses `uv.lock` for reproducible installs; `uv sync` is an alternative to the pip commands above if `uv` is available.

### Running the app
```bash
# Streamlit WebUI (legacy)
streamlit run app.py

# FastAPI backend (new architecture)
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000 --reload

# Next.js frontend (new architecture, separate terminal)
cd frontend && npm install && npm run dev

# All three at once (Streamlit :8501, FastAPI :8000, Next.js :3000)
bash scripts/start_dual_stack.sh

# Interactive CLI
python -m cli.main
# or, after `pip install -e .`:
tradingagents
```

### Tests
```bash
# Whole suite (unittest-based; no pytest dependency in this repo)
python -m unittest discover -s tests -v

# Single test file / test
python -m unittest tests.test_model_validation -v
python -m unittest tests.test_model_validation.ModelValidationTests.test_unknown_model_emits_warning_for_strict_provider -v
```
Tests require the full dependency set installed (`pip install -e .` / `uv sync`) — they import `tradingagents.llm_clients` and `cli.utils`, which pull in `langchain_openai`, `questionary`, etc.

### Frontend (in `frontend/`)
```bash
npm run dev     # Next.js dev server on :3000
npm run build
npm run lint     # eslint (next lint)
```

There is no configured Python linter/formatter (no ruff/black/flake8 config in the repo) — match the existing style in the file you're editing.

## Architecture

### Core agent pipeline (`tradingagents/`)

`TradingAgentsGraph` (`tradingagents/graph/trading_graph.py`) is the entry point. It wires together:

- **LLM clients** (`tradingagents/llm_clients/`): a provider abstraction (`create_llm_client` in `factory.py`) supporting `openai`, `anthropic`, `google`, `xai`, `ollama`, `openrouter`, `siliconflow`. Each provider has a client class extending `BaseLLMClient` (`base_client.py`), which validates the configured model against `model_catalog.py` and emits a `RuntimeWarning` (not an error) for unknown models — except `ollama`/`openrouter`, which allow arbitrary custom model names. Two LLM instances are created per run: `deep_thinking_llm` (for the Research Manager / Portfolio Manager) and `quick_thinking_llm` (for analysts, researchers, and risk debators).
- **Agent graph** (`tradingagents/graph/`): `GraphSetup.setup_graph()` builds a `langgraph.StateGraph` over `AgentState`. The pipeline is: selected analysts (market/social/news/fundamentals, each with a tool-calling loop + "Msg Clear" node) → Bull/Bear Researcher debate (rounds controlled by `max_debate_rounds`) → Research Manager judges the debate → Trader proposes a plan → Aggressive/Neutral/Conservative risk debate (rounds controlled by `max_risk_discuss_rounds`) → Portfolio Manager issues the final decision. `ConditionalLogic` (`conditional_logic.py`) decides when to keep looping tool calls vs. move on, and when a debate round count is reached.
- **Agents** (`tradingagents/agents/`): each agent is a factory function (e.g. `create_market_analyst(llm)`) returning a LangGraph node closure. Organized by role: `analysts/`, `researchers/` (bull/bear), `managers/` (research + portfolio), `risk_mgmt/` (aggressive/neutral/conservative debators), `trader/`. Shared helpers live in `agents/utils/`: `agent_states.py` (TypedDicts for `AgentState`, `InvestDebateState`, `RiskDebateState`), `agent_utils.py` (re-exports tool functions + `get_language_instruction()` + `build_instrument_context()`), `memory.py` (`FinancialSituationMemory`, BM25-based — no vector DB/embeddings API calls; used for reflection/self-improvement across runs).
- **Dataflows** (`tradingagents/dataflows/`): vendor-agnostic tool functions (`get_stock_data`, `get_indicators`, `get_fundamentals`, `get_news`, etc.) that route to a vendor backend at call time via `dataflows/config.py`'s `get_config()`. Vendor selection is two-level: `data_vendors` (category default, e.g. `core_stock_apis`) can be overridden per-tool via `tool_vendors`. Currently implemented vendors: `yfinance` (`y_finance.py`, `yfinance_news.py`, no API key needed) and `alpha_vantage` (`alpha_vantage*.py`, needs `ALPHA_VANTAGE_API_KEY`).
- **Config**: `DEFAULT_CONFIG` in `tradingagents/default_config.py` is the base config dict; callers (CLI, `main.py`, WebUI) copy and override it. Key fields: `llm_provider`, `deep_think_llm`, `quick_think_llm`, `max_debate_rounds`, `max_risk_discuss_rounds`, `output_language` (applied only to user-facing report text via `get_language_instruction()` — internal debate stays in English for reasoning quality), `data_vendors`/`tool_vendors`.
- Ticker handling preserves exchange suffixes (e.g. `.TO`, `.L`, `.HK`, `.T`) end-to-end — see `build_instrument_context()` in `agent_utils.py` and `cli/utils.py::normalize_ticker_symbol`.

### Output/run artifacts (gitignored, generated at runtime — don't commit)
- `eval_results/<TICKER>/TradingAgentsStrategy_logs/` — full state JSON logs from `TradingAgentsGraph._log_state`.
- `results/` — CLI run outputs.
- `reports/` — WebUI analysis report outputs.
- `data/dashboard/latest.json`, `data/dashboard/history/`, `data/cache/`, `data/portfolio.json` — WebUI dashboard snapshots, cache, and local portfolio store.

### CLI (`cli/`)
`cli/main.py` is a Typer app built around a `MessageBuffer` class that tracks agent status/messages/tool calls/report sections for the live Rich TUI as the graph streams. `cli/models.py` defines `AnalystType`; `cli/utils.py` has interactive prompts (ticker/date/analyst/provider/model selection) plus `normalize_ticker_symbol`; `cli/stats_handler.py` is a LangChain callback handler for usage stats, passed into `TradingAgentsGraph(callbacks=[...])`.

### Streamlit WebUI (`web/`, entry `app.py`)
Page-based: `web/pages/PAGES` maps page names (Chinese strings defined in `web/navigation.py`) to render functions, dispatched from `app.py` based on `st.session_state.current_page`. `web/services/` holds data/LLM/storage logic decoupled from page rendering (e.g. `dashboard_store.py`, `dashboard_llm.py`, `market_data.py`, `portfolio_store.py`, `x_brief_*.py` for an X/Twitter-derived news brief, `backtesting_core.py`). `web/pages/lrs/` and `web/pages/wheel/` are sub-strategy modules (LRS = a TQQQ/leveraged-ETF strategy documented in `docs/LRS_notebooks/`; Wheel = an options wheel strategy) each with their own `_shared.py`/`_cache.py` helpers.

### FastAPI + Next.js (new architecture, in progress)
`backend/api/main.py` defines REST endpoints under `/api/v1/...` (dashboard, quotes, x-brief, LRS chat, wheel evaluate, backtest jobs) that call into `backend/api/services.py`, which itself delegates to `web/services/*` — i.e. the new backend reuses the Streamlit app's service layer rather than duplicating it. All responses use a uniform `ApiEnvelope {success, data, error, trace_id}` shape (see `_ok`/`_err` helpers in `main.py`). `frontend/` is a Next.js 15 (App Router) + Zustand app; routes under `frontend/src/app/<page>/page.tsx` map 1:1 to Streamlit pages per `docs/migration/streamlit_to_npm_mapping.md`, which also documents the `st.session_state` → `useUiStore` field mapping. See `docs/migration/cutover_and_rollback.md` and `docs/migration/parallel_validation_checklist.md` for the migration plan and rollback conditions — Streamlit stays live in parallel until the Next.js UI is fully validated.

## Conventions worth knowing

- Adding a new LLM provider: implement a `BaseLLMClient` subclass in `tradingagents/llm_clients/`, register it in `factory.py::create_llm_client`, and add its models to `model_catalog.py::MODEL_OPTIONS` (used by both CLI prompts and `validators.py`).
- Adding a new data vendor/tool: implement the vendor module in `tradingagents/dataflows/`, wire it into `interface.py`'s routing, and register it under the right category in `default_config.py::data_vendors` / expose an override path via `tool_vendors`.
- Agent nodes are plain closures returned by `create_*` factory functions taking an `llm` (and sometimes a `memory`) — follow that pattern rather than introducing classes when adding new agents.
- New backend endpoints belong in `backend/api/`, reusing `web/services/*` where the logic already exists in the Streamlit app, rather than being reimplemented in `web/pages/`.
