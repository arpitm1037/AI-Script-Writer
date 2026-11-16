"""Unit tests for Gemini response handling and normalized provider errors."""

import unittest
from unittest.mock import MagicMock, patch

from app.llm.base import (
    LLMConfigurationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.llm.gemini import GeminiProvider


class GeminiProviderTests(unittest.TestCase):
    def test_requires_api_key(self):
        with self.assertRaises(LLMConfigurationError):
            GeminiProvider(api_key=None, model="test-model", timeout_seconds=10)


    def test_returns_text_from_mocked_sdk(self):
        provider = GeminiProvider(api_key="test-key", model="test-model", timeout_seconds=10)
        response = MagicMock(text="Generated text")
        client = MagicMock()
        client.models.generate_content.return_value = response
        types = MagicMock()

        with patch.object(provider, "_create_client", return_value=(client, types)):
            result = provider.generate(system_instructions="system", user_content="data")

        self.assertEqual(result, "Generated text")
        client.models.generate_content.assert_called_once()


    def test_maps_timeout(self):
        provider = GeminiProvider(api_key="test-key", model="test-model", timeout_seconds=10)
        with patch.object(provider, "_create_client", side_effect=TimeoutError):
            with self.assertRaises(LLMTimeoutError):
                provider.generate(system_instructions="system", user_content="data")


    def test_maps_rate_limit(self):
        provider = GeminiProvider(api_key="test-key", model="test-model", timeout_seconds=10)
        rate_limited_client = MagicMock()
        rate_limited_client.models.generate_content.side_effect = Exception("RESOURCE_EXHAUSTED")

        with patch.object(provider, "_create_client", return_value=(rate_limited_client, MagicMock())):
            with self.assertRaises(LLMRateLimitError):
                provider.generate(system_instructions="system", user_content="data")

    def test_maps_generic_provider_failure_without_exposing_sdk_error(self):
        provider = GeminiProvider(api_key="test-key", model="test-model", timeout_seconds=10)
        failing_client = MagicMock()
        failing_client.models.generate_content.side_effect = Exception("provider internals")

        with patch.object(provider, "_create_client", return_value=(failing_client, MagicMock())):
            with self.assertRaises(LLMProviderError) as raised:
                provider.generate(system_instructions="system", user_content="data")

        self.assertNotIn("provider internals", str(raised.exception))
