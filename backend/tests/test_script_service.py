"""Service tests for script generation, editing, validation, and ownership."""

import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import CreativeBrief, Outline, User
from app.llm.base import LLMProviderError
from app.services import script_service


VALID_SCRIPT = """INT. MUSEUM - NIGHT

AVA slips past the display cases as BEN watches the door.

AVA
This plan was supposed to be simple.

The alarm chirps. They exchange a worried look, then improvise together.
"""


class FakeProvider:
    def __init__(self, response: str | Exception):
        self.response = response
        self.calls = []

    def generate(self, *, system_instructions: str, user_content: str) -> str:
        self.calls.append((system_instructions, user_content))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class ScriptServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.owner = User(name="Owner", email="script-owner@example.com", password_hash="hash")
        self.other_user = User(name="Other", email="script-other@example.com", password_hash="hash")
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
        self.db.flush()
        self.outline = Outline(
            creative_brief_id=self.brief.id,
            is_approved=True,
            content={
                "title": "Museum Mix-Up",
                "logline": "Two rivals attempt a heist.",
                "acts": [
                    {"title": "Setup", "summary": "Meet", "beats": ["Plan"]},
                    {"title": "Conflict", "summary": "Fail", "beats": ["Alarm"]},
                    {"title": "Resolution", "summary": "Escape", "beats": ["Leave"]},
                ],
            },
        )
        self.db.add(self.outline)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_generates_persists_and_retrieves_script(self):
        provider = FakeProvider(VALID_SCRIPT)
        script, created = script_service.generate_script(
            self.db, self.brief.id, self.owner.id, provider, regenerate=False
        )

        self.assertTrue(created)
        self.assertEqual(script.outline_id, self.outline.id)
        self.assertEqual(script_service.get_script(self.db, self.brief.id, self.owner.id).id, script.id)
        self.assertIn("Short Film / Screenplay", provider.calls[0][0])
        self.assertIn("approved_outline", provider.calls[0][1])

    def test_blocks_unapproved_outline_and_missing_outline(self):
        self.outline.is_approved = False
        self.db.commit()
        with self.assertRaises(HTTPException) as unapproved:
            script_service.generate_script(
                self.db, self.brief.id, self.owner.id, FakeProvider(VALID_SCRIPT), regenerate=False
            )
        self.assertEqual(unapproved.exception.status_code, 409)

        without_outline = CreativeBrief(
            user_id=self.owner.id,
            topic="Another idea",
            genre="Drama",
            output_format="YouTube / Long-form",
            language="English",
            tone="Calm",
            target_audience="Adults",
            duration="5 minutes",
            characters="Host",
            setting="Studio",
            key_points="Explain concept",
            detail_level="Standard",
            special_instructions=None,
        )
        self.db.add(without_outline)
        self.db.commit()
        with self.assertRaises(HTTPException) as missing:
            script_service.generate_script(
                self.db, without_outline.id, self.owner.id, FakeProvider(VALID_SCRIPT), regenerate=False
            )
        self.assertEqual(missing.exception.status_code, 404)

        with self.assertRaises(HTTPException) as missing_brief:
            script_service.generate_script(
                self.db, 99999, self.owner.id, FakeProvider(VALID_SCRIPT), regenerate=False
            )
        self.assertEqual(missing_brief.exception.status_code, 404)

    def test_rejects_empty_or_invalid_provider_content_without_persisting(self):
        with self.assertRaises(script_service.InvalidScriptResponseError):
            script_service.generate_script(
                self.db, self.brief.id, self.owner.id, FakeProvider("   "), regenerate=False
            )
        with self.assertRaises(HTTPException) as missing:
            script_service.get_script(self.db, self.brief.id, self.owner.id)
        self.assertEqual(missing.exception.status_code, 404)

        with self.assertRaises(LLMProviderError):
            script_service.generate_script(
                self.db,
                self.brief.id,
                self.owner.id,
                FakeProvider(LLMProviderError("provider failure")),
                regenerate=False,
            )

    def test_requires_explicit_regeneration_and_allows_basic_editing(self):
        script, _ = script_service.generate_script(
            self.db, self.brief.id, self.owner.id, FakeProvider(VALID_SCRIPT), regenerate=False
        )
        with self.assertRaises(HTTPException) as duplicate:
            script_service.generate_script(
                self.db, self.brief.id, self.owner.id, FakeProvider(VALID_SCRIPT), regenerate=False
            )
        self.assertEqual(duplicate.exception.status_code, 409)

        regenerated, created = script_service.generate_script(
            self.db,
            self.brief.id,
            self.owner.id,
            FakeProvider(f"{VALID_SCRIPT}\nA revised ending."),
            regenerate=True,
        )
        self.assertFalse(created)
        self.assertEqual(regenerated.id, script.id)
        updated = script_service.update_script(
            self.db, self.brief.id, self.owner.id, f"  {VALID_SCRIPT}  "
        )
        self.assertEqual(updated.content, VALID_SCRIPT.strip())

    def test_hides_scripts_from_other_users(self):
        script_service.generate_script(
            self.db, self.brief.id, self.owner.id, FakeProvider(VALID_SCRIPT), regenerate=False
        )
        with self.assertRaises(HTTPException) as access_error:
            script_service.get_script(self.db, self.brief.id, self.other_user.id)
        self.assertEqual(access_error.exception.status_code, 404)
