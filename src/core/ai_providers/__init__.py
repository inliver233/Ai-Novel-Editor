from __future__ import annotations

from .claude import ClaudeProvider
from .custom import CustomProvider
from .gemini import GeminiProvider
from .ollama import OllamaProvider
from .openai import OpenAIProvider


def get_provider_strategy(config, logger):
    provider = getattr(config, "provider", None)
    provider_value = provider.value if hasattr(provider, "value") else str(provider)

    if provider_value == "openai":
        return OpenAIProvider(config, logger)
    if provider_value == "claude":
        return ClaudeProvider(config, logger)
    if provider_value == "gemini":
        return GeminiProvider(config, logger)
    if provider_value == "ollama":
        return OllamaProvider(config, logger)
    return CustomProvider(config, logger)
