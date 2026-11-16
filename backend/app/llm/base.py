"""Small provider contract and normalized LLM errors."""

from typing import Protocol


class LLMError(Exception):
    """Base class for errors safe to translate at the API boundary."""


class LLMConfigurationError(LLMError):
    """Raised when required LLM configuration is absent or invalid."""


class LLMTimeoutError(LLMError):
    """Raised when an LLM request exceeds its configured timeout."""


class LLMRateLimitError(LLMError):
    """Raised when the provider rejects a request because of rate limits."""


class LLMProviderError(LLMError):
    """Raised for other provider failures without exposing provider details."""


class LLMProvider(Protocol):
    """Minimal contract used by future generation workflows."""

    def generate(self, *, system_instructions: str, user_content: str) -> str:
        """Generate content from separately supplied instruction and user data."""
