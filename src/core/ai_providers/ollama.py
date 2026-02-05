from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import OpenAICompatibleProvider
from ..tool_types import ToolDefinition


class OllamaProvider(OpenAICompatibleProvider):
    def get_headers(self) -> Dict[str, str]:
        return self._base_headers()

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
        return "http://localhost:11434/v1/chat/completions"

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
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
        }

        ollama_options: Dict[str, Any] = {}
        for key in ["num_ctx", "num_predict", "repeat_penalty", "top_k", "seed"]:
            if key in kwargs:
                ollama_options[key] = kwargs[key]

        if ollama_options:
            data["options"] = ollama_options

        if tools:
            data["tools"] = [tool.to_openai_format() for tool in tools]
            data["tool_choice"] = kwargs.get("tool_choice", "auto")

        for key, value in kwargs.items():
            if key == "max_tokens":
                data["max_tokens"] = value
            elif key == "temperature":
                data["temperature"] = value
            elif key == "top_p":
                data["top_p"] = value

        return data

    def extract_content(self, response_data: Dict[str, Any]) -> Optional[str]:
        try:
            if "choices" in response_data and len(response_data["choices"]) > 0:
                choice = response_data["choices"][0]
                if "message" in choice:
                    return choice["message"].get("content", "")
                if "text" in choice:
                    return choice["text"]
            if "response" in response_data:
                return response_data["response"]
            self.logger.warning("无法从响应中提取内容")
            return None
        except Exception as exc:  # noqa: BLE001
            self.logger.error(f"提取响应内容失败: {exc}")
            return None
