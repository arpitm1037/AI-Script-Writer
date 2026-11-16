"""Create the configured LLM provider on demand."""

from app.core.config import settings
from app.llm.base import LLMConfigurationError, LLMProvider
from app.llm.gemini import GeminiProvider


def get_llm_provider() -> LLMProvider:
    """Return the configured provider; future providers can be added here."""
    if settings.LLM_PROVIDER.lower() == "gemini":
        return GeminiProvider(
            api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_MODEL,
            timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
        )
    raise LLMConfigurationError("Configured LLM provider is unsupported")
