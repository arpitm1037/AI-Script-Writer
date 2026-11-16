"""Route tests for safe outline-generation error responses."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException, Response

from app.api.routes.creative_briefs import generate_outline
from app.llm.base import LLMProviderError, LLMTimeoutError
from app.schemas.outline import OutlineGenerateRequest
from app.services import outline_service


class OutlineRouteTests(unittest.TestCase):
    def test_timeout_is_returned_as_safe_gateway_timeout(self):
        with patch(
            "app.api.routes.creative_briefs.get_llm_provider",
            side_effect=LLMTimeoutError("internal details"),
        ):
            with self.assertRaises(HTTPException) as raised:
                generate_outline(
                    brief_id=1,
                    payload=OutlineGenerateRequest(),
                    response=Response(),
                    db=object(),
                    current_user=SimpleNamespace(id=1),
                )
        self.assertEqual(raised.exception.status_code, 504)
        self.assertEqual(raised.exception.detail, "LLM request timed out")

    def test_invalid_response_is_not_exposed_to_client(self):
        with patch("app.api.routes.creative_briefs.get_llm_provider", return_value=object()):
            with patch(
                "app.api.routes.creative_briefs.outline_service.generate_outline",
                side_effect=outline_service.InvalidOutlineResponseError("raw model output"),
            ):
                with self.assertRaises(HTTPException) as raised:
                    generate_outline(
                        brief_id=1,
                        payload=OutlineGenerateRequest(),
                        response=Response(),
                        db=object(),
                        current_user=SimpleNamespace(id=1),
                    )
        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(raised.exception.detail, "LLM returned no usable outline")

    def test_provider_failure_is_returned_as_safe_bad_gateway_response(self):
        with patch(
            "app.api.routes.creative_briefs.get_llm_provider",
            side_effect=LLMProviderError("provider internals"),
        ):
            with self.assertRaises(HTTPException) as raised:
                generate_outline(
                    brief_id=1,
                    payload=OutlineGenerateRequest(),
                    response=Response(),
                    db=object(),
                    current_user=SimpleNamespace(id=1),
                )
        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(raised.exception.detail, "LLM returned no usable outline")
