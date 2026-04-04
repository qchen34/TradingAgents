#!/usr/bin/env bash
# Local test: same CLI-parity parameters as .github/workflows/tradingagents-analysis-run.yml
# (mirrors cli/utils.py get_user_selections + backend URL mapping).
#
# Usage (from repo root that contains pyproject.toml):
#   chmod +x scripts/local_dispatch_like_cli.sh
#   export OPENAI_API_KEY=...   # or other provider keys
#   ./scripts/local_dispatch_like_cli.sh
#
# Override any variable below before running, e.g.:
#   TICKER=NVDA ANALYSIS_DATE=2026-04-04 RESEARCH_DEPTH=3 ./scripts/local_dispatch_like_cli.sh

set -euo pipefail

cd "$(dirname "$0")/.."

TICKER="${TICKER:-SPY}"
ANALYSIS_DATE="${ANALYSIS_DATE:-}" # empty => UTC today
OUTPUT_LANGUAGE="${OUTPUT_LANGUAGE:-English}"
OUTPUT_LANGUAGE_CUSTOM="${OUTPUT_LANGUAGE_CUSTOM:-}"

INCLUDE_MARKET="${INCLUDE_MARKET:-true}"
INCLUDE_SOCIAL="${INCLUDE_SOCIAL:-true}"
INCLUDE_NEWS="${INCLUDE_NEWS:-true}"
INCLUDE_FUNDAMENTALS="${INCLUDE_FUNDAMENTALS:-true}"

RESEARCH_DEPTH="${RESEARCH_DEPTH:-1}"
LLM_PROVIDER="${LLM_PROVIDER:-openai}"
QUICK_MODEL="${QUICK_MODEL:-gpt-5.4-mini}"
DEEP_MODEL="${DEEP_MODEL:-gpt-5.4}"

GOOGLE_THINKING_LEVEL="${GOOGLE_THINKING_LEVEL:-none}"
OPENAI_REASONING_EFFORT="${OPENAI_REASONING_EFFORT:-none}"
ANTHROPIC_EFFORT="${ANTHROPIC_EFFORT:-none}"

if [[ -z "${ANALYSIS_DATE}" ]]; then
  ANALYSIS_DATE="$(date -u +%Y-%m-%d)"
fi

if [[ "${OUTPUT_LANGUAGE}" == "custom" ]]; then
  if [[ -z "${OUTPUT_LANGUAGE_CUSTOM// }" ]]; then
    echo "OUTPUT_LANGUAGE=custom requires OUTPUT_LANGUAGE_CUSTOM"
    exit 1
  fi
  OUT_LANG="${OUTPUT_LANGUAGE_CUSTOM}"
else
  OUT_LANG="${OUTPUT_LANGUAGE}"
fi

PARTS=()
[[ "${INCLUDE_MARKET}" == "true" ]] && PARTS+=("market")
[[ "${INCLUDE_SOCIAL}" == "true" ]] && PARTS+=("social")
[[ "${INCLUDE_NEWS}" == "true" ]] && PARTS+=("news")
[[ "${INCLUDE_FUNDAMENTALS}" == "true" ]] && PARTS+=("fundamentals")
if [[ ${#PARTS[@]} -eq 0 ]]; then
  echo "Select at least one analyst (INCLUDE_*=true)."
  exit 1
fi
IFS=','; ANALYSTS="${PARTS[*]}"; unset IFS

case "${LLM_PROVIDER}" in
  openai) BACKEND="https://api.openai.com/v1" ;;
  siliconflow) BACKEND="https://api.siliconflow.cn/v1" ;;
  google) BACKEND="https://generativelanguage.googleapis.com/v1" ;;
  anthropic) BACKEND="https://api.anthropic.com/" ;;
  xai) BACKEND="https://api.x.ai/v1" ;;
  openrouter) BACKEND="https://openrouter.ai/api/v1" ;;
  ollama) BACKEND="http://localhost:11434/v1" ;;
  *) echo "Unknown LLM_PROVIDER"; exit 1 ;;
esac

GTL="${GOOGLE_THINKING_LEVEL}"; [[ "${GTL}" == "none" ]] && GTL=""
ORE="${OPENAI_REASONING_EFFORT}"; [[ "${ORE}" == "none" ]] && ORE=""
AE="${ANTHROPIC_EFFORT}"; [[ "${AE}" == "none" ]] && AE=""

OUT_DIR="reports/_ci/local-test-$(date -u +%Y%m%d-%H%M%S)"
mkdir -p "${OUT_DIR}"

set -x
python scripts/github_scheduled_analysis.py \
  --ticker "${TICKER}" \
  --date "${ANALYSIS_DATE}" \
  --output-dir "${OUT_DIR}" \
  --analysts "${ANALYSTS}" \
  --research-depth "${RESEARCH_DEPTH}" \
  --llm-provider "${LLM_PROVIDER}" \
  --backend-url "${BACKEND}" \
  --quick-model "${QUICK_MODEL}" \
  --deep-model "${DEEP_MODEL}" \
  --output-language "${OUT_LANG}" \
  ${ORE:+--openai-reasoning-effort "${ORE}"} \
  ${GTL:+--google-thinking-level "${GTL}"} \
  ${AE:+--anthropic-effort "${AE}"}
set +x

echo "OK: ${OUT_DIR}/complete_report.md"
