"""Gemini implementation of the provider-neutral LLM contract."""

from app.llm.base import (
    LLMConfigurationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)


class GeminiProvider:
    """Generate content with Gemini without exposing SDK errors to callers."""

    def __init__(self, *, api_key: str | None, model: str, timeout_seconds: int) -> None:
        if not api_key:
            raise LLMConfigurationError("Gemini is not configured")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds

    def generate(self, *, system_instructions: str, user_content: str) -> str:
        try:
            client, types = self._create_client()
            response = client.models.generate_content(
                model=self._model,
                contents=user_content,
                config=types.GenerateContentConfig(
                    system_instruction=system_instructions,
                ),
            )
        except LLMConfigurationError:
            raise
        except TimeoutError as exc:
            raise LLMTimeoutError("Gemini request timed out") from exc
        except Exception as exc:
            if _is_rate_limit_error(exc):
                raise LLMRateLimitError("Gemini rate limit reached") from exc
            raise LLMProviderError("Gemini request failed") from exc

        text = getattr(response, "text", None)
        if not text:
            raise LLMProviderError("Gemini returned an empty response")
        return text

    def _create_client(self):
        """Load the optional SDK lazily so prompt preview needs no SDK client."""
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise LLMConfigurationError("Gemini SDK is not installed") from exc

        return (
            genai.Client(
                api_key=self._api_key,
                http_options=types.HttpOptions(timeout=self._timeout_seconds * 1000),
            ),
            types,
        )


def _is_rate_limit_error(error: Exception) -> bool:
    """Recognize SDK and HTTP-style rate-limit errors without SDK coupling."""
    status_code = getattr(error, "status_code", None) or getattr(error, "code", None)
    return status_code == 429 or "RESOURCE_EXHAUSTED" in str(error).upper()
