from __future__ import annotations

from typing import AsyncGenerator, Optional, Protocol


class LLMProvider(Protocol):
    def complete(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Optional[str]:
        ...

    def complete_stream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> AsyncGenerator[str, None]:
        ...

    def supports_tools(self) -> bool:
        ...
