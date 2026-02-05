from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ..multimodal_types import MultimodalMessage
from ..tool_types import ToolCall


class BaseProviderStrategy:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

    def _base_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "User-Agent": "AI-Novel-Editor/0.1.0 (compatible; requests)",
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    def get_headers(self) -> Dict[str, str]:
        raise NotImplementedError

    def get_endpoint_url(self) -> str:
        raise NotImplementedError

    def format_multimodal_message(self, message: MultimodalMessage) -> Optional[Dict[str, Any]]:
        return message.to_openai_format()

    def build_request_data(
        self,
        messages: List[Dict[str, Any]],
        stream: bool = False,
        tools=None,
        **kwargs,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    def extract_content(self, response_data: Dict[str, Any]) -> Optional[str]:
        return None

    def extract_tool_calls(self, response_data: Dict[str, Any]) -> List[ToolCall]:
        return []

    def has_tool_calls(self, response_data: Dict[str, Any]) -> bool:
        return False

    def extract_stream_content(self, chunk_data: Dict[str, Any]) -> Optional[str]:
        return None


class OpenAICompatibleProvider(BaseProviderStrategy):
    def format_multimodal_message(self, message: MultimodalMessage) -> Optional[Dict[str, Any]]:
        return message.to_openai_format()

    def extract_content(self, response_data: Dict[str, Any]) -> Optional[str]:
        try:
            if "choices" in response_data and len(response_data["choices"]) > 0:
                choice = response_data["choices"][0]
                if "message" in choice:
                    return choice["message"].get("content", "")
                if "text" in choice:
                    return choice["text"]
            self.logger.warning("无法从响应中提取内容")
            return None
        except Exception as exc:  # noqa: BLE001
            self.logger.error(f"提取响应内容失败: {exc}")
            return None

    def extract_tool_calls(self, response_data: Dict[str, Any]) -> List[ToolCall]:
        tool_calls: List[ToolCall] = []
        try:
            if "choices" in response_data and len(response_data["choices"]) > 0:
                choice = response_data["choices"][0]
                if "message" in choice and "tool_calls" in choice["message"]:
                    for tc in choice["message"]["tool_calls"]:
                        try:
                            parameters = json.loads(tc["function"]["arguments"])
                        except json.JSONDecodeError:
                            parameters = {}
                            self.logger.warning(f"工具调用参数JSON解析失败: {tc['function']['arguments']}")
                        tool_calls.append(
                            ToolCall(
                                id=tc["id"],
                                tool_name=tc["function"]["name"],
                                parameters=parameters,
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
            if "choices" in response_data and len(response_data["choices"]) > 0:
                choice = response_data["choices"][0]
                return bool(
                    "message" in choice
                    and "tool_calls" in choice["message"]
                    and choice["message"]["tool_calls"]
                )
            return False
        except Exception:
            return False

    def extract_stream_content(self, chunk_data: Dict[str, Any]) -> Optional[str]:
        try:
            if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                choice = chunk_data["choices"][0]
                delta = choice.get("delta", {})
                return delta.get("content", "")
            return None
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(f"提取流式内容失败: {exc}")
            return None
