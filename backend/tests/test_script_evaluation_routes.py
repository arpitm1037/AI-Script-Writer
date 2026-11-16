"""Route tests for script-evaluation authorization and provider errors."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.api.routes.creative_briefs import (
    evaluate_script_version,
    get_script_version_evaluation,
    list_script_version_evaluations,
)
from app.llm.base import (
    LLMConfigurationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.services import script_evaluation_service


class ScriptEvaluationRouteTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(id=42)
        self.db = object()

    def _call_evaluate(self):
        return evaluate_script_version(
            brief_id=7,
            version_number=2,
            db=self.db,
            current_user=self.user,
        )

    def test_revision_resource_is_authorized_before_provider_creation(self):
        with patch(
            "app.api.routes.creative_briefs.script_evaluation_service.get_owned_script_version",
            side_effect=HTTPException(status_code=404, detail="Not found"),
        ):
            with patch(
                "app.api.routes.creative_briefs.get_llm_provider"
            ) as get_provider:
                with self.assertRaises(HTTPException) as raised:
                    self._call_evaluate()

        self.assertEqual(raised.exception.status_code, 404)
        get_provider.assert_not_called()

    def test_provider_errors_map_to_safe_http_responses(self):
        cases = (
            (LLMConfigurationError("secret details"), 503, "LLM is unavailable"),
            (LLMTimeoutError("secret details"), 504, "LLM request timed out"),
            (LLMRateLimitError("secret details"), 429, "LLM rate limit reached"),
            (LLMProviderError("secret details"), 502, "LLM returned no usable evaluation"),
            (
                script_evaluation_service.InvalidEvaluationResponseError("raw output"),
                502,
                "LLM returned no usable evaluation",
            ),
        )
        for error, expected_status, expected_detail in cases:
            with self.subTest(error=type(error).__name__):
                with patch(
                    "app.api.routes.creative_briefs.script_evaluation_service.get_owned_script_version"
                ):
                    with patch(
                        "app.api.routes.creative_briefs.get_llm_provider",
                        side_effect=error,
                    ):
                        with self.assertRaises(HTTPException) as raised:
                            self._call_evaluate()
                self.assertEqual(raised.exception.status_code, expected_status)
                self.assertEqual(raised.exception.detail, expected_detail)
                self.assertNotIn("secret", raised.exception.detail)
                self.assertNotIn("raw output", raised.exception.detail)

    def test_malformed_provider_response_is_safely_mapped(self):
        with patch(
            "app.api.routes.creative_briefs.script_evaluation_service.get_owned_script_version"
        ):
            with patch(
                "app.api.routes.creative_briefs.get_llm_provider",
                return_value=object(),
            ):
                with patch(
                    "app.api.routes.creative_briefs.script_evaluation_service.evaluate_script_version",
                    side_effect=script_evaluation_service.InvalidEvaluationResponseError(
                        "raw Gemini response"
                    ),
                ):
                    with self.assertRaises(HTTPException) as raised:
                        self._call_evaluate()

        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(raised.exception.detail, "LLM returned no usable evaluation")

    def test_provider_failure_during_generation_is_safely_mapped(self):
        errors = (
            (LLMTimeoutError("provider internals"), 504),
            (LLMRateLimitError("provider internals"), 429),
            (LLMProviderError("provider internals"), 502),
        )
        for error, expected_status in errors:
            with self.subTest(error=type(error).__name__):
                with patch(
                    "app.api.routes.creative_briefs.script_evaluation_service.get_owned_script_version"
                ):
                    with patch(
                        "app.api.routes.creative_briefs.get_llm_provider",
                        return_value=object(),
                    ):
                        with patch(
                            "app.api.routes.creative_briefs.script_evaluation_service.evaluate_script_version",
                            side_effect=error,
                        ):
                            with self.assertRaises(HTTPException) as raised:
                                self._call_evaluate()
                self.assertEqual(raised.exception.status_code, expected_status)
                self.assertNotIn("provider internals", raised.exception.detail)

    def test_list_and_retrieve_forward_authenticated_user_and_path_ids(self):
        with patch(
            "app.api.routes.creative_briefs.script_evaluation_service.list_version_evaluations",
            return_value=[],
        ) as list_evaluations:
            response = list_script_version_evaluations(
                brief_id=7,
                version_number=2,
                db=self.db,
                current_user=self.user,
            )
        self.assertEqual(response, [])
        list_evaluations.assert_called_once_with(self.db, 7, 2, 42)

        evaluation = SimpleNamespace(id=9)
        with patch(
            "app.api.routes.creative_briefs.script_evaluation_service.get_version_evaluation",
            return_value=evaluation,
        ) as get_evaluation:
            response = get_script_version_evaluation(
                brief_id=7,
                version_number=2,
                evaluation_id=9,
                db=self.db,
                current_user=self.user,
            )
        self.assertIs(response, evaluation)
        get_evaluation.assert_called_once_with(self.db, 7, 2, 9, 42)
