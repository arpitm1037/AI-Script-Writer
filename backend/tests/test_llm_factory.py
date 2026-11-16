"""Unit tests for configured language-model provider selection."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.llm.base import LLMConfigurationError
from app.llm.factory import get_llm_provider
from app.llm.gemini import GeminiProvider


class LLMFactoryTests(unittest.TestCase):
    def test_creates_configured_gemini_provider(self):
        settings = SimpleNamespace(
            LLM_PROVIDER="gemini",
            GEMINI_API_KEY="test-key",
            GEMINI_MODEL="test-model",
            LLM_TIMEOUT_SECONDS=10,
        )
        with patch("app.llm.factory.settings", settings):
            provider = get_llm_provider()

        self.assertIsInstance(provider, GeminiProvider)

    def test_rejects_unsupported_provider(self):
        settings = SimpleNamespace(LLM_PROVIDER="unknown")
        with patch("app.llm.factory.settings", settings):
            with self.assertRaises(LLMConfigurationError):
                get_llm_provider()
