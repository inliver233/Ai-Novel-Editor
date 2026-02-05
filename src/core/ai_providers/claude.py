from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import BaseProviderStrategy
from ..multimodal_types import MultimodalMessage
from ..tool_types import ToolCall, ToolDefinition


class ClaudeProvider(BaseProviderStrategy):
    def get_headers(self) -> Dict[str, str]:
        headers = self._base_headers()
        headers["x-api-key"] = self.config.api_key
        headers["anthropic-version"] = "2023-06-01"
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
            return f"{base_url}/v1/messages"
        return "https://api.anthropic.com/v1/messages"

    def format_multimodal_message(self, message: MultimodalMessage) -> Optional[Dict[str, Any]]:
        return message.to_claude_format()

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

        system_msg = None
        user_messages = []
        for msg in messages:
            if msg["role"] in ["system", "developer"]:
                system_msg = msg["content"]
            else:
                user_messages.append(msg)

        data["messages"] = user_messages
        if system_msg:
            data["system"] = system_msg
        data["max_tokens"] = self.config.max_tokens
        data["temperature"] = self.config.temperature

        if tools:
            data["tools"] = [tool.to_claude_format() for tool in tools]

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
            if "content" in response_data and len(response_data["content"]) > 0:
                return response_data["content"][0].get("text", "")
            self.logger.warning("无法从响应中提取内容")
            return None
        except Exception as exc:  # noqa: BLE001
            self.logger.error(f"提取响应内容失败: {exc}")
            return None

    def extract_tool_calls(self, response_data: Dict[str, Any]) -> List[ToolCall]:
        tool_calls: List[ToolCall] = []
        try:
            if "content" in response_data:
                for content_block in response_data["content"]:
                    if content_block.get("type") == "tool_use":
                        tool_calls.append(
                            ToolCall(
                                id=content_block["id"],
                                tool_name=content_block["name"],
                                parameters=content_block["input"],
                            )
                        )
            if tool_calls:
                self.logger.info(f"提取到 {len(tool_calls)} 个工具调用")
            return tool_calls
        except Exception as exc:  # noqa: BLE001
            self.logger.error(f"提取工具调用失败: {exc}")
            return []

    def has_tool_calls(self, response_data: Dict[str, Any]) -> bool:
        try:
            if "content" in response_data:
                return any(block.get("type") == "tool_use" for block in response_data["content"])
            return False
        except Exception:
            return False

    def extract_stream_content(self, chunk_data: Dict[str, Any]) -> Optional[str]:
        try:
            if chunk_data.get("type") == "content_block_delta":
                delta = chunk_data.get("delta", {})
                return delta.get("text", "")
            return None
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(f"提取流式内容失败: {exc}")
            return None
