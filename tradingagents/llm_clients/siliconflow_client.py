import os
from typing import Any, Optional

from langchain_openai import ChatOpenAI

from .base_client import BaseLLMClient, normalize_content
from .validators import validate_model


class NormalizedSiliconFlowChatOpenAI(ChatOpenAI):
    """ChatOpenAI wrapper with normalized content output."""

    def invoke(self, input, config=None, **kwargs):
        return normalize_content(super().invoke(input, config, **kwargs))


_PASSTHROUGH_KWARGS = (
    "timeout",
    "max_retries",
    "reasoning_effort",
    "api_key",
    "callbacks",
    "http_client",
    "http_async_client",
)


class SiliconFlowClient(BaseLLMClient):
    """Client for SiliconFlow OpenAI-compatible API."""

    DEFAULT_BASE_URL = "https://api.siliconflow.cn/v1"
    API_KEY_ENV = "SILICONFLOW_API_KEY"

    def __init__(self, model: str, base_url: Optional[str] = None, **kwargs):
        super().__init__(model, base_url, **kwargs)

    def get_llm(self) -> Any:
        """Return configured ChatOpenAI instance for SiliconFlow."""
        self.warn_if_unknown_model()
        llm_kwargs = {
            "model": self.model,
            "base_url": self.base_url or self.DEFAULT_BASE_URL,
        }

        api_key = os.environ.get(self.API_KEY_ENV)
        if api_key:
            llm_kwargs["api_key"] = api_key

        for key in _PASSTHROUGH_KWARGS:
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        return NormalizedSiliconFlowChatOpenAI(**llm_kwargs)

    def validate_model(self) -> bool:
        """Validate model for SiliconFlow provider."""
        return validate_model("siliconflow", self.model)
