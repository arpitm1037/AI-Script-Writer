"""Service tests for outline generation, ownership, approval, and validation."""

import json
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import CreativeBrief, User
from app.llm.base import LLMProviderError
from app.schemas.outline import OutlineContent
from app.services import outline_service


def valid_outline_json() -> str:
    return json.dumps(
        {
            "title": "Museum Mix-Up",
            "logline": "Two rivals attempt a museum heist that becomes a comedy.",
            "acts": [
                {"title": "Setup", "summary": "The rivals meet.", "beats": ["A plan forms."]},
                {"title": "Conflict", "summary": "The plan fails.", "beats": ["Alarms ring."]},
                {"title": "Resolution", "summary": "They cooperate.", "beats": ["They escape."]},
            ],
        }
    )


class FakeProvider:
    def __init__(self, response: str | Exception):
        self.response = response
        self.calls = []

    def generate(self, *, system_instructions: str, user_content: str) -> str:
        self.calls.append((system_instructions, user_content))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class OutlineServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.owner = User(name="Owner", email="owner@example.com", password_hash="hash")
        self.other_user = User(name="Other", email="other@example.com", password_hash="hash")
        self.db.add_all([self.owner, self.other_user])
        self.db.flush()
        self.brief = CreativeBrief(
            user_id=self.owner.id,
            topic="Museum heist",
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
            special_instructions=None,
        )
        self.db.add(self.brief)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_generates_and_persists_structured_outline(self):
        provider = FakeProvider(valid_outline_json())

        outline, created = outline_service.generate_outline(
            self.db, self.brief.id, self.owner.id, provider, regenerate=False
        )

        self.assertTrue(created)
        self.assertEqual(outline.content["title"], "Museum Mix-Up")
        self.assertFalse(outline.is_approved)
        self.assertEqual(len(provider.calls), 1)
        self.assertIn("<creative_brief>", provider.calls[0][1])
        self.assertIn("Return JSON only", provider.calls[0][0])

    def test_rejects_invalid_llm_response_without_persisting_outline(self):
        with self.assertRaises(outline_service.InvalidOutlineResponseError):
            outline_service.generate_outline(
                self.db, self.brief.id, self.owner.id, FakeProvider("not json"), regenerate=False
            )

        with self.assertRaises(HTTPException) as raised:
            outline_service.get_outline(self.db, self.brief.id, self.owner.id)
        self.assertEqual(raised.exception.status_code, 404)

    def test_rejects_incomplete_llm_response(self):
        incomplete = json.dumps({"title": "Only a title", "logline": "Missing acts"})
        with self.assertRaises(outline_service.InvalidOutlineResponseError):
            outline_service.generate_outline(
                self.db, self.brief.id, self.owner.id, FakeProvider(incomplete), regenerate=False
            )

    def test_edits_and_approves_outline_then_locks_it(self):
        outline, _ = outline_service.generate_outline(
            self.db, self.brief.id, self.owner.id, FakeProvider(valid_outline_json()), regenerate=False
        )
        edited = OutlineContent.model_validate({**outline.content, "title": "Edited title"})
        updated = outline_service.update_outline(self.db, self.brief.id, self.owner.id, edited)
        approved = outline_service.approve_outline(self.db, self.brief.id, self.owner.id)

        self.assertEqual(updated.content["title"], "Edited title")
        self.assertTrue(approved.is_approved)
        with self.assertRaises(HTTPException) as edit_error:
            outline_service.update_outline(self.db, self.brief.id, self.owner.id, edited)
        self.assertEqual(edit_error.exception.status_code, 409)
        with self.assertRaises(HTTPException) as regenerate_error:
            outline_service.generate_outline(
                self.db, self.brief.id, self.owner.id, FakeProvider(valid_outline_json()), regenerate=True
            )
        self.assertEqual(regenerate_error.exception.status_code, 409)

    def test_requires_explicit_regeneration_and_enforces_owner(self):
        outline_service.generate_outline(
            self.db, self.brief.id, self.owner.id, FakeProvider(valid_outline_json()), regenerate=False
        )
        with self.assertRaises(HTTPException) as conflict:
            outline_service.generate_outline(
                self.db, self.brief.id, self.owner.id, FakeProvider(valid_outline_json()), regenerate=False
            )
        self.assertEqual(conflict.exception.status_code, 409)

        with self.assertRaises(HTTPException) as access_error:
            outline_service.get_outline(self.db, self.brief.id, self.other_user.id)
        self.assertEqual(access_error.exception.status_code, 404)
