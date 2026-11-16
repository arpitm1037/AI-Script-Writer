"""Service tests for append-only script revision and restoration behavior."""

import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import CreativeBrief, Outline, ScriptVersion, User
from app.llm.base import LLMProviderError
from app.services import script_service, script_version_service


ORIGINAL_SCRIPT = """INT. MUSEUM - NIGHT

AVA enters the gallery as BEN waits by the door. The alarm begins to chirp,
forcing them to abandon their careful plan and work together to escape.
"""
REVISED_SCRIPT = """INT. MUSEUM - NIGHT

AVA enters the silent gallery as BEN waits by the door. The alarm becomes a
slow, ominous pulse, and their escape turns into a suspenseful race through darkness.
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


class ScriptVersionServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.owner = User(name="Owner", email="version-owner@example.com", password_hash="hash")
        self.other = User(name="Other", email="version-other@example.com", password_hash="hash")
        self.db.add_all([self.owner, self.other])
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
            content={"title": "Museum", "logline": "A heist", "acts": []},
        )
        self.db.add(self.outline)
        self.db.commit()
        self.script, _ = script_service.generate_script(
            self.db, self.brief.id, self.owner.id, FakeProvider(ORIGINAL_SCRIPT), regenerate=False
        )

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_revision_appends_versions_in_sequential_order(self):
        first = script_version_service.get_version(self.db, self.brief.id, self.owner.id, 1)
        second = script_version_service.revise_script(
            self.db,
            self.brief.id,
            self.owner.id,
            FakeProvider(REVISED_SCRIPT),
            "Make the ending more suspenseful.",
        )
        third = script_version_service.revise_script(
            self.db,
            self.brief.id,
            self.owner.id,
            FakeProvider(f"{REVISED_SCRIPT}\nAVA and BEN escape at dawn."),
            "Add a hopeful ending.",
        )
        versions = script_version_service.list_versions(self.db, self.brief.id, self.owner.id)

        self.assertEqual([version.version_number for version in versions], [1, 2, 3])
        self.assertEqual(first.content, ORIGINAL_SCRIPT.strip())
        self.assertEqual(second.revision_instructions, "Make the ending more suspenseful.")
        self.assertEqual(third.version_number, 3)
        self.assertEqual(versions[0].content, ORIGINAL_SCRIPT.strip())
        self.assertEqual(versions[1].content, REVISED_SCRIPT.strip())
        self.assertIsNotNone(versions[0].created_at)
        self.assertEqual(
            script_service.get_script(self.db, self.brief.id, self.owner.id).content,
            third.content,
        )

    def test_restore_appends_a_new_version_without_deleting_history(self):
        script_version_service.revise_script(
            self.db, self.brief.id, self.owner.id, FakeProvider(REVISED_SCRIPT), "More suspense."
        )
        third_content = f"{REVISED_SCRIPT}\nAVA and BEN escape at dawn."
        script_version_service.revise_script(
            self.db,
            self.brief.id,
            self.owner.id,
            FakeProvider(third_content),
            "Add a hopeful ending.",
        )
        restored = script_version_service.restore_version(self.db, self.brief.id, self.owner.id, 1)
        versions = script_version_service.list_versions(self.db, self.brief.id, self.owner.id)

        self.assertEqual(restored.version_number, 4)
        self.assertEqual(restored.content, ORIGINAL_SCRIPT.strip())
        self.assertEqual(restored.revision_instructions, "Restored version 1")
        self.assertEqual([version.version_number for version in versions], [1, 2, 3, 4])
        self.assertEqual(versions[0].content, ORIGINAL_SCRIPT.strip())
        self.assertEqual(versions[1].content, REVISED_SCRIPT.strip())
        self.assertEqual(versions[2].content, third_content.strip())
        self.assertEqual(versions[3].content, ORIGINAL_SCRIPT.strip())
        self.assertEqual(script_service.get_script(self.db, self.brief.id, self.owner.id).content, ORIGINAL_SCRIPT.strip())

    def test_failed_revision_does_not_append_a_new_version(self):
        with self.assertRaises(LLMProviderError):
            script_version_service.revise_script(
                self.db,
                self.brief.id,
                self.owner.id,
                FakeProvider(LLMProviderError("provider failure")),
                "Improve dialogue.",
            )
        versions = script_version_service.list_versions(self.db, self.brief.id, self.owner.id)
        self.assertEqual([version.version_number for version in versions], [1])

    def test_failed_revision_does_not_backfill_a_legacy_version(self):
        self.db.execute(delete(ScriptVersion).where(ScriptVersion.script_id == self.script.id))
        self.db.commit()

        with self.assertRaises(LLMProviderError):
            script_version_service.revise_script(
                self.db,
                self.brief.id,
                self.owner.id,
                FakeProvider(LLMProviderError("provider failure")),
                "Improve dialogue.",
            )

        version_count = self.db.scalar(
            select(func.count()).select_from(ScriptVersion).where(
                ScriptVersion.script_id == self.script.id
            )
        )
        self.assertEqual(version_count, 0)

    def test_invalid_revision_response_does_not_append_a_version(self):
        with self.assertRaises(script_service.InvalidScriptResponseError):
            script_version_service.revise_script(
                self.db,
                self.brief.id,
                self.owner.id,
                FakeProvider("too short"),
                "Improve dialogue.",
            )

        versions = script_version_service.list_versions(self.db, self.brief.id, self.owner.id)
        self.assertEqual([version.version_number for version in versions], [1])

    def test_cross_user_access_is_hidden(self):
        with self.assertRaises(HTTPException) as listed:
            script_version_service.list_versions(self.db, self.brief.id, self.other.id)
        self.assertEqual(listed.exception.status_code, 404)
        with self.assertRaises(HTTPException) as retrieved:
            script_version_service.get_version(self.db, self.brief.id, self.other.id, 1)
        self.assertEqual(retrieved.exception.status_code, 404)

    def test_cross_user_revision_and_restore_are_hidden(self):
        provider = FakeProvider(REVISED_SCRIPT)
        with self.assertRaises(HTTPException) as revised:
            script_version_service.revise_script(
                self.db, self.brief.id, self.other.id, provider, "Improve dialogue."
            )
        self.assertEqual(revised.exception.status_code, 404)
        self.assertEqual(provider.calls, [])

        with self.assertRaises(HTTPException) as restored:
            script_version_service.restore_version(self.db, self.brief.id, self.other.id, 1)
        self.assertEqual(restored.exception.status_code, 404)

    def test_stale_concurrent_revision_is_rejected_without_new_version(self):
        service = script_version_service
        db = self.db
        brief_id = self.brief.id
        user_id = self.owner.id

        class ConcurrentProvider:
            def generate(self, *, system_instructions: str, user_content: str) -> str:
                script_service.update_script(db, brief_id, user_id, REVISED_SCRIPT)
                return REVISED_SCRIPT

        with self.assertRaises(HTTPException) as stale:
            service.revise_script(db, brief_id, user_id, ConcurrentProvider(), "Make it tense.")
        self.assertEqual(stale.exception.status_code, 409)
        versions = service.list_versions(db, brief_id, user_id)
        self.assertEqual([version.version_number for version in versions], [1, 2])
        self.assertEqual(
            script_service.get_script(db, brief_id, user_id).content,
            REVISED_SCRIPT.strip(),
        )
