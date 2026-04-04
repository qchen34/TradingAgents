#!/usr/bin/env python3
"""Emit workflow_call input fragments from cli/utils.py + model_catalog (single source of truth)."""

from __future__ import annotations

import textwrap

from tradingagents.llm_clients.model_catalog import MODEL_OPTIONS

# Mirrors cli/utils.py select_llm_provider BASE_URLS order (display -> url); keys = config llm_provider
PROVIDERS = [
    ("openai", "https://api.openai.com/v1"),
    ("siliconflow", "https://api.siliconflow.cn/v1"),
    ("google", "https://generativelanguage.googleapis.com/v1"),
    ("anthropic", "https://api.anthropic.com/"),
    ("xai", "https://api.x.ai/v1"),
    ("openrouter", "https://openrouter.ai/api/v1"),
    ("ollama", "http://localhost:11434/v1"),
]

OUTPUT_LANGS = [
    ("English (default)", "English"),
    ("Chinese (中文)", "Chinese"),
    ("Japanese (日本語)", "Japanese"),
    ("Korean (한국어)", "Korean"),
    ("Hindi (हिन्दी)", "Hindi"),
    ("Spanish (Español)", "Spanish"),
    ("Portuguese (Português)", "Portuguese"),
    ("French (Français)", "French"),
    ("German (Deutsch)", "German"),
    ("Arabic (العربية)", "Arabic"),
    ("Russian (Русский)", "Russian"),
    ("Custom (use output_language_custom input)", "custom"),
]


def _yaml_quote(s: str) -> str:
    if any(c in s for c in (":", "#", "'", '"', "\n", "\\")) or s.strip() != s:
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def emit_choice_options_lines(values: list[str], indent: str = "          ") -> str:
    lines = []
    for v in values:
        lines.append(f"{indent}- {_yaml_quote(v)}")
    return "\n".join(lines)


def main() -> None:
    quick_vals: list[str] = []
    deep_vals: list[str] = []
    for _p, modes in MODEL_OPTIONS.items():
        for _label, val in modes["quick"]:
            quick_vals.append(val)
        for _label, val in modes["deep"]:
            deep_vals.append(val)

    print("=== quick_model options (paste under workflow_call.inputs.quick_model.options) ===")
    print(emit_choice_options_lines(quick_vals))
    print()
    print("=== deep_model options ===")
    print(emit_choice_options_lines(deep_vals))
    print()
    print("=== llm_provider options ===")
    for key, url in PROVIDERS:
        print(f"          - {_yaml_quote(key)}")
    print()
    print("=== output_language options ===")
    for disp, val in OUTPUT_LANGS:
        print(f"          - {_yaml_quote(val)}  # {disp}")


if __name__ == "__main__":
    main()
