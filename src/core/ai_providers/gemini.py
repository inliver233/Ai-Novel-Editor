from __future__ import annotations

import json
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from typing import Any, Dict, List, Optional

from .base import BaseProviderStrategy
from ..multimodal_types import MultimodalMessage
from ..tool_types import ToolCall, ToolDefinition


class GeminiProvider(BaseProviderStrategy):
    def get_headers(self) -> Dict[str, str]:
        headers = self._base_headers()
        headers["x-goog-api-key"] = self.config.api_key
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
            return f"{base_url}/v1beta/models/{self.config.model}:generateContent"
        return f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.model}:generateContent"

    def get_stream_endpoint_url(self) -> str:
        endpoint_url = (self.config.endpoint_url or "").strip()
        if endpoint_url:
            if ":streamGenerateContent" in endpoint_url:
                return self._ensure_alt_sse(endpoint_url)
            if ":generateContent" in endpoint_url:
                return self._ensure_alt_sse(endpoint_url.replace(":generateContent", ":streamGenerateContent"))
            if (
                "/chat/completions" in endpoint_url
                or "/messages" in endpoint_url
                or "/api/generate" in endpoint_url
                or "/api/chat" in endpoint_url
            ):
                return endpoint_url
            base_url = endpoint_url.rstrip("/")
            return f"{base_url}/v1beta/models/{self.config.model}:streamGenerateContent?alt=sse"

        return f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.model}:streamGenerateContent?alt=sse"

    @staticmethod
    def _ensure_alt_sse(url: str) -> str:
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query.setdefault("alt", "sse")
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    def format_multimodal_message(self, message: MultimodalMessage) -> Optional[Dict[str, Any]]:
        return message.to_gemini_format()

    def _is_thinking_model(self) -> bool:
        thinking_models = [
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.0-flash-thinking",
        ]
        model_name = self.config.model.lower()
        return any(tm in model_name for tm in thinking_models)

    def build_request_data(
        self,
        messages: List[Dict[str, Any]],
        stream: bool = False,
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        contents = []
        generation_config = {
            "temperature": self.config.temperature,
            "maxOutputTokens": self.config.max_tokens,
            "topP": self.config.top_p,
        }

        if self._is_thinking_model():
            thinking_config: Dict[str, Any] = {}
            include_thoughts = kwargs.get("include_thoughts", kwargs.get("includeThoughts", False))
            if include_thoughts:
                thinking_config["includeThoughts"] = True

            thinking_budget = kwargs.get("thinking_budget", kwargs.get("thinkingBudget"))
            if thinking_budget is not None:
                thinking_config["thinkingBudget"] = thinking_budget
            elif include_thoughts:
                thinking_config["thinkingBudget"] = 1024

            if thinking_config:
                generation_config["thinkingConfig"] = thinking_config

        system_buffer: List[str] = []
        for msg in messages:
            if msg["role"] == "system":
                system_buffer.append(msg["content"])
                continue

            gemini_role = "model" if msg["role"] == "assistant" else msg["role"]
            text = msg["content"]
            if gemini_role == "user" and system_buffer:
                separator = "\n\n"
                prefix = separator.join(system_buffer)
                text = f"{prefix}{separator}{text}" if text else prefix
                system_buffer = []

            contents.append(
                {
                    "role": gemini_role,
                    "parts": [{"text": text}],
                }
            )

        if system_buffer and not contents:
            contents.append(
                {
                    "role": "user",
                    "parts": [{"text": "\n\n".join(system_buffer)}],
                }
            )

        data: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": generation_config,
        }

        if tools:
            data["tools"] = [
                {
                    "functionDeclarations": [tool.to_gemini_format() for tool in tools],
                }
            ]

        for key, value in kwargs.items():
            if key == "max_tokens":
                data["generationConfig"]["maxOutputTokens"] = value
            elif key in ["temperature"]:
                data["generationConfig"]["temperature"] = value
            elif key in ["top_p"]:
                data["generationConfig"]["topP"] = value
        return data

    def extract_content(self, response_data: Dict[str, Any]) -> Optional[str]:
        try:
            if "candidates" in response_data and len(response_data["candidates"]) > 0:
                candidate = response_data["candidates"][0]
                finish_reason = candidate.get("finishReason")
                if finish_reason == "MAX_TOKENS":
                    self.logger.warning("Gemini响应被截断（达到最大token限制），建议增加maxOutputTokens")
                elif finish_reason == "SAFETY":
                    self.logger.warning("Gemini响应被安全过滤器阻止")
                    return "[内容被安全过滤器阻止]"

                if "content" in candidate:
                    content = candidate["content"]

                    if "parts" in content and content["parts"]:
                        parts = content["parts"]
                        text_parts = []
                        thought_parts = []
                        for part in parts:
                            if "text" in part:
                                if part.get("thought", False):
                                    thought_parts.append(part["text"])
                                else:
                                    text_parts.append(part["text"])
                        if text_parts:
                            return "\n".join(text_parts)
                        if thought_parts:
                            self.logger.info("返回Gemini思考内容（缺少最终回复）")
                            return f"[思考过程] {' '.join(thought_parts[:2])}"

                    if "text" in content:
                        return content["text"]

                if "text" in candidate:
                    return candidate["text"]

                if finish_reason == "MAX_TOKENS":
                    usage = response_data.get("usageMetadata", {})
                    thoughts_count = usage.get("thoughtsTokenCount", 0)
                    if thoughts_count > 0:
                        return (
                            "[Gemini API Bug] 响应因token限制被截断。"
                            f"模型生成了{thoughts_count}个思考token但最终响应丢失。"
                            "请增加maxOutputTokens并重试。"
                        )

            self.logger.debug(
                f"Gemini响应结构: {json.dumps(response_data, indent=2, ensure_ascii=False)[:500]}..."
            )
            self.logger.warning("Gemini响应格式无法识别 - 可能是API bug或新格式")
            return None
        except Exception as exc:  # noqa: BLE001
            self.logger.error(f"解析Gemini响应时出错: {exc}")
            self.logger.debug(f"原始响应: {response_data}")
            return None

    def extract_tool_calls(self, response_data: Dict[str, Any]) -> List[ToolCall]:
        tool_calls: List[ToolCall] = []
        try:
            if "candidates" in response_data and len(response_data["candidates"]) > 0:
                candidate = response_data["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    for part in candidate["content"]["parts"]:
                        if "functionCall" in part:
                            func_call = part["functionCall"]
                            tool_calls.append(
                                ToolCall(
                                    id=f"call_{hash(func_call['name'])}",
                                    tool_name=func_call["name"],
                                    parameters=func_call.get("args", {}),
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
            if "candidates" in response_data and len(response_data["candidates"]) > 0:
                candidate = response_data["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    return any("functionCall" in part for part in candidate["content"]["parts"])
            return False
        except Exception:
            return False

    def extract_stream_content(self, chunk_data: Dict[str, Any]) -> Optional[str]:
        """Extract incremental text from Gemini streamGenerateContent SSE chunks."""
        try:
            if not isinstance(chunk_data, dict):
                return None

            candidates = chunk_data.get("candidates")
            if not candidates:
                return None

            candidate = candidates[0] if isinstance(candidates, list) else candidates
            if not isinstance(candidate, dict):
                return None

            content = candidate.get("content") or {}
            if not isinstance(content, dict):
                return None

            parts = content.get("parts") or []
            if not isinstance(parts, list):
                return None

            text_parts: List[str] = []
            for part in parts:
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if not isinstance(text, str) or not text:
                    continue
                if part.get("thought", False):
                    continue
                text_parts.append(text)

            if text_parts:
                return "\n".join(text_parts)
            return None
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(f"提取Gemini流式内容失败: {exc}")
            return None
