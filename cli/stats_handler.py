import threading
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_core.messages import AIMessage


def _pick_int(d: Optional[Dict[str, Any]], *keys: str) -> int:
    if not d:
        return 0
    for k in keys:
        v = d.get(k)
        if v is not None:
            try:
                return int(v)
            except (TypeError, ValueError):
                continue
    return 0


def _extract_tokens_from_usage_dict(u: Dict[str, Any]) -> Tuple[int, int]:
    """兼容 OpenAI / Anthropic / Gemini 等字段命名。"""
    tin = _pick_int(u, "input_tokens", "prompt_tokens", "cache_read_input_tokens")
    tout = _pick_int(u, "output_tokens", "completion_tokens", "candidates_token_count")
    return tin, tout


class StatsCallbackHandler(BaseCallbackHandler):
    """Callback handler that tracks LLM calls, tool calls, and token usage."""

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self.llm_calls = 0
        self.tool_calls = 0
        self.tokens_in = 0
        self.tokens_out = 0

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs: Any,
    ) -> None:
        """Increment LLM call counter when an LLM starts."""
        with self._lock:
            self.llm_calls += 1

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[Any]],
        **kwargs: Any,
    ) -> None:
        """Increment LLM call counter when a chat model starts."""
        with self._lock:
            self.llm_calls += 1

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Extract token usage from LLM response."""
        tin, tout = 0, 0
        try:
            generation = response.generations[0][0]
        except (IndexError, TypeError):
            generation = None

        if generation is not None and hasattr(generation, "message"):
            message = generation.message
            if isinstance(message, AIMessage):
                if hasattr(message, "usage_metadata") and message.usage_metadata:
                    um = message.usage_metadata
                    if isinstance(um, dict):
                        tin = _pick_int(um, "input_tokens", "prompt_tokens")
                        tout = _pick_int(um, "output_tokens", "completion_tokens")
                if tin == 0 and tout == 0 and hasattr(message, "response_metadata"):
                    rm = message.response_metadata or {}
                    u = rm.get("token_usage") or rm.get("usage_metadata") or rm.get("usage")
                    if isinstance(u, dict):
                        tin, tout = _extract_tokens_from_usage_dict(u)

        if tin == 0 and tout == 0 and generation is not None:
            gen_info = getattr(generation, "generation_info", None) or {}
            if isinstance(gen_info, dict):
                u = gen_info.get("token_usage") or gen_info.get("usage")
                if isinstance(u, dict):
                    tin, tout = _extract_tokens_from_usage_dict(u)

        if tin == 0 and tout == 0:
            llm_out = getattr(response, "llm_output", None)
            if isinstance(llm_out, dict):
                u = llm_out.get("token_usage") or llm_out.get("usage")
                if isinstance(u, dict):
                    tin, tout = _extract_tokens_from_usage_dict(u)

        if tin or tout:
            with self._lock:
                self.tokens_in += tin
                self.tokens_out += tout

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        """Increment tool call counter when a tool starts."""
        with self._lock:
            self.tool_calls += 1

    def get_stats(self) -> Dict[str, Any]:
        """Return current statistics."""
        with self._lock:
            return {
                "llm_calls": self.llm_calls,
                "tool_calls": self.tool_calls,
                "tokens_in": self.tokens_in,
                "tokens_out": self.tokens_out,
            }
