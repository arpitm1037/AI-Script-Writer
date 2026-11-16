"""Database and ORM tests for cascading deletes across the script workflow."""

import unittest

from sqlalchemy import create_engine, delete, event, func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    CreativeBrief,
    Outline,
    Script,
    ScriptEvaluation,
    ScriptVersion,
    User,
)


class ModelCascadeTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")

        @event.listens_for(self.engine, "connect")
        def enable_sqlite_foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user, self.brief, self.outline, self.script, self.version, self.evaluation = (
            self._create_workflow()
        )

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _create_workflow(self):
        user = User(name="Cascade Test", email="cascade@example.com", password_hash="hash")
        brief = CreativeBrief(
            user=user,
            topic="A test story",
            genre="Drama",
            output_format="Short Film / Screenplay",
            language="English",
            tone="Reflective",
            target_audience="Adults",
            duration="10 minutes",
            characters="Alex",
            setting="A quiet town",
            key_points="A difficult choice",
            detail_level="Standard",
        )
        outline = Outline(
            creative_brief=brief,
            content={"title": "A Test Story", "logline": "A difficult choice.", "acts": []},
        )
        script = Script(
            creative_brief=brief,
            outline=outline,
            content="The story begins and follows Alex through a difficult choice.",
        )
        version = ScriptVersion(
            script=script,
            version_number=1,
            content=script.content,
        )
        evaluation = ScriptEvaluation(
            script_version=version,
            criteria={},
            overall_score=4.0,
            summary="A clear test evaluation.",
            strengths=["Clear premise"],
            improvement_suggestions=["Add detail"],
        )
        self.db.add(user)
        self.db.commit()
        return user, brief, outline, script, version, evaluation

    def _assert_counts(self, expected):
        models = {
            "users": User,
            "creative_briefs": CreativeBrief,
            "outlines": Outline,
            "scripts": Script,
            "script_versions": ScriptVersion,
            "script_evaluations": ScriptEvaluation,
        }
        for table, model in models.items():
            with self.subTest(table=table):
                count = self.db.scalar(select(func.count()).select_from(model))
                self.assertEqual(count, expected.get(table, 0))

    def _assert_database_delete_cascades(self, model, record_id, expected):
        self.db.execute(delete(model).where(model.id == record_id))
        self.db.commit()
        self._assert_counts(expected)

    def test_database_delete_user_cascades_through_entire_workflow(self):
        self._assert_database_delete_cascades(User, self.user.id, {})

    def test_database_delete_brief_cascades_to_outline_and_script_history(self):
        self._assert_database_delete_cascades(
            CreativeBrief,
            self.brief.id,
            {"users": 1},
        )

    def test_database_delete_script_cascades_to_versions_and_evaluations(self):
        self._assert_database_delete_cascades(
            Script,
            self.script.id,
            {"users": 1, "creative_briefs": 1, "outlines": 1},
        )

    def test_database_delete_version_cascades_to_evaluations(self):
        self._assert_database_delete_cascades(
            ScriptVersion,
            self.version.id,
            {
                "users": 1,
                "creative_briefs": 1,
                "outlines": 1,
                "scripts": 1,
            },
        )

    def test_orm_delete_user_cascades_through_entire_workflow(self):
        self.db.delete(self.user)
        self.db.commit()
        self._assert_counts({})

    def test_orm_delete_brief_cascades_to_outline_and_script_history(self):
        self.db.delete(self.brief)
        self.db.commit()
        self._assert_counts({"users": 1})

    def test_orm_delete_script_cascades_to_versions_and_evaluations(self):
        self.db.delete(self.script)
        self.db.commit()
        self._assert_counts(
            {"users": 1, "creative_briefs": 1, "outlines": 1}
        )

    def test_orm_delete_version_cascades_to_evaluations(self):
        self.db.delete(self.version)
        self.db.commit()
        self._assert_counts(
            {
                "users": 1,
                "creative_briefs": 1,
                "outlines": 1,
                "scripts": 1,
            }
        )


if __name__ == "__main__":
    unittest.main()
