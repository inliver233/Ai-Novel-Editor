from __future__ import annotations

from typing import Any, Dict, Optional

from .openai import OpenAIProvider
from ..multimodal_types import MultimodalMessage


class CustomProvider(OpenAIProvider):
    def get_headers(self) -> Dict[str, str]:
        headers = self._base_headers()
        headers["Authorization"] = f"Bearer {self.config.api_key}"
        if "inliver" in str(self.config.endpoint_url).lower():
            headers["X-API-Key"] = self.config.api_key
        return headers

    def get_endpoint_url(self) -> str:
        if not self.config.endpoint_url:
            raise ValueError("未配置端点URL: custom")
        return super().get_endpoint_url()

    def format_multimodal_message(self, message: MultimodalMessage) -> Optional[Dict[str, Any]]:
        if "gemini" in str(self.config.endpoint_url).lower():
            return message.to_gemini_format()
        return message.to_openai_format()
