"""Route tests for owner-scoped, provider-neutral prompt previews."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.api.routes.creative_briefs import preview_prompt


class PromptPreviewRouteTests(unittest.TestCase):
    def test_preview_uses_owner_scoped_brief_and_never_calls_provider(self):
        brief = SimpleNamespace(
            id=7,
            topic="A heist",
            genre="Comedy",
            output_format="Short Film / Screenplay",
            language="English",
            tone="Playful",
            target_audience="Adults",
            duration="10 minutes",
            characters="Ava and Ben",
            setting="Museum",
            key_points="The plan goes wrong",
            detail_level="Standard",
            special_instructions="No violence",
        )
        user = SimpleNamespace(id=42)

        with patch(
            "app.api.routes.creative_briefs.creative_brief_service.get_creative_brief",
            return_value=brief,
        ) as get_brief:
            response = preview_prompt(brief_id=7, db=object(), current_user=user)

        get_brief.assert_called_once_with(unittest.mock.ANY, 7, 42)
        self.assertEqual(response.brief_id, 7)
        self.assertIn("<topic>A heist</topic>", response.user_content)
