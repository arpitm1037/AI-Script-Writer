"""Route tests for safe script-revision error responses."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.api.routes.creative_briefs import revise_script
from app.llm.base import LLMProviderError, LLMTimeoutError
from app.schemas.script_version import ScriptRevisionRequest
from app.services import script_service, script_version_service


class ScriptVersionRouteTests(unittest.TestCase):
    def test_revision_timeout_is_safe(self):
        with patch(
            "app.api.routes.creative_briefs.get_llm_provider",
            side_effect=LLMTimeoutError("provider details"),
        ):
            with self.assertRaises(HTTPException) as raised:
                revise_script(
                    brief_id=1,
                    payload=ScriptRevisionRequest(revision_instructions="Improve dialogue."),
                    db=object(),
                    current_user=SimpleNamespace(id=1),
                )
        self.assertEqual(raised.exception.status_code, 504)

    def test_invalid_revision_result_is_safe(self):
        with patch("app.api.routes.creative_briefs.get_llm_provider", return_value=object()):
            with patch(
                "app.api.routes.creative_briefs.script_version_service.revise_script",
                side_effect=script_service.InvalidScriptResponseError("raw provider content"),
            ):
                with self.assertRaises(HTTPException) as raised:
                    revise_script(
                        brief_id=1,
                        payload=ScriptRevisionRequest(revision_instructions="Improve dialogue."),
                        db=object(),
                        current_user=SimpleNamespace(id=1),
                    )
        self.assertEqual(raised.exception.status_code, 502)

    def test_provider_failure_is_safe(self):
        with patch(
            "app.api.routes.creative_briefs.get_llm_provider",
            side_effect=LLMProviderError("provider details"),
        ):
            with self.assertRaises(HTTPException) as raised:
                revise_script(
                    brief_id=1,
                    payload=ScriptRevisionRequest(revision_instructions="Improve dialogue."),
                    db=object(),
                    current_user=SimpleNamespace(id=1),
                )
        self.assertEqual(raised.exception.status_code, 502)
