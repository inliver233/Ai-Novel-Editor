from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import OpenAICompatibleProvider
from ..tool_types import ToolDefinition


class OpenAIProvider(OpenAICompatibleProvider):
    def get_headers(self) -> Dict[str, str]:
        headers = self._base_headers()
        headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def get_endpoint_url(self) -> str:
        if self.config.endpoint_url:
            if (
                "/chat/completions" in self.config.endpoint_url
                or "/messages" in self.config.endpoint_url
                or ":generateContent" in self.config.endpoint_url
                or "/api/generate" in self.config.endpoint_url
                or "/api/chat" in self.config.endpoint_url
            ):
                return self.config.endpoint_url
            base_url = self.config.endpoint_url.rstrip("/")
            return f"{base_url}/v1/chat/completions"

        return "https://api.openai.com/v1/chat/completions"

    def _is_reasoning_model(self) -> bool:
        reasoning_models = ["o1", "o3", "o4-mini", "o1-mini", "o1-preview", "o3-mini", "o4"]
        model_name = self.config.model.lower()
        return any(rm in model_name for rm in reasoning_models)

    def build_request_data(
        self,
        messages: List[Dict[str, Any]],
        stream: bool = False,
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "model": self.config.model,
            "stream": stream,
        }

        is_reasoning_model = self._is_reasoning_model()

        if is_reasoning_model:
            data["messages"] = messages
            data["max_completion_tokens"] = self.config.max_tokens

            if "reasoning_effort" in kwargs:
                data["reasoning_effort"] = kwargs["reasoning_effort"]
            elif hasattr(self.config, "reasoning_effort"):
                data["reasoning_effort"] = getattr(self.config, "reasoning_effort", "medium")

            model_supports_tools = any(
                model in self.config.model.lower() for model in ["o3-mini", "o4-mini"]
            )
            if tools and model_supports_tools:
                data["tools"] = [tool.to_openai_format() for tool in tools]
                data["tool_choice"] = kwargs.get("tool_choice", "auto")
                data["parallel_tool_calls"] = kwargs.get("parallel_tool_calls", True)
        else:
            data["messages"] = messages
            data["max_tokens"] = self.config.max_tokens
            data["temperature"] = self.config.temperature
            data["top_p"] = self.config.top_p

            if tools:
                data["tools"] = [tool.to_openai_format() for tool in tools]
                data["tool_choice"] = kwargs.get("tool_choice", "auto")
                data["parallel_tool_calls"] = kwargs.get("parallel_tool_calls", True)

        for key, value in kwargs.items():
            if key == "max_tokens" and not is_reasoning_model:
                data["max_tokens"] = value
            elif key == "max_completion_tokens" and is_reasoning_model:
                data["max_completion_tokens"] = value
            elif key == "max_tokens" and is_reasoning_model:
                data["max_completion_tokens"] = value
            elif key == "temperature" and not is_reasoning_model:
                data["temperature"] = value
            elif key == "top_p" and not is_reasoning_model:
                data["top_p"] = value

        return data

    def supports_tools(self) -> bool:
        if self._is_reasoning_model():
            return any(model in self.config.model.lower() for model in ["o3-mini", "o4-mini"])
        return True
