"""Service tests for evaluation validation, persistence, and history access."""

import json
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
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
from app.llm.base import LLMProviderError
from app.schemas.script_evaluation import ScriptEvaluationResponse
from app.services import script_evaluation_service


def valid_evaluation(
    *,
    relevance_score: int = 5,
    dialogue_explanation: str = "The dialogue is clear and character-specific.",
) -> str:
    return json.dumps(
        {
            "criteria": {
                "relevance_to_brief": {
                    "score": relevance_score,
                    "explanation": "The story follows the requested premise.",
                },
                "outline_alignment": {
                    "score": 4,
                    "explanation": "Most approved outline beats are present.",
                },
                "story_structure_and_coherence": {
                    "score": 3,
                    "explanation": "The middle section could be clearer.",
                },
                "character_consistency": {
                    "score": 4,
                    "explanation": "The leads retain distinct motivations.",
                },
                "dialogue_quality": {
                    "score": 2,
                    "explanation": dialogue_explanation,
                },
                "genre_and_format_compliance": {
                    "score": 5,
                    "explanation": "The screenplay format suits the requested genre.",
                },
            },
            "summary": "A coherent draft with room to sharpen the middle.",
            "strengths": ["Clear premise", "Distinct lead characters"],
            "improvement_suggestions": ["Clarify the central turning point"],
        }
    )


class FakeProvider:
    def __init__(self, response: str | Exception):
        self.response = response
        self.calls: list[tuple[str, str]] = []

    def generate(self, *, system_instructions: str, user_content: str) -> str:
        self.calls.append((system_instructions, user_content))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class ScriptEvaluationServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.owner = User(
            name="Evaluation Owner",
            email="evaluation-owner@example.com",
            password_hash="hash",
        )
        self.other_user = User(
            name="Other User",
            email="evaluation-other@example.com",
            password_hash="hash",
        )
        self.db.add_all([self.owner, self.other_user])
        self.db.flush()
        self.brief = CreativeBrief(
            user_id=self.owner.id,
            topic="A museum heist goes wrong",
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
                "logline": "Two rivals try to complete a museum heist.",
                "acts": [
                    {"title": "Setup", "summary": "They plan.", "beats": ["The plan begins."]},
                    {"title": "Conflict", "summary": "It fails.", "beats": ["An alarm sounds."]},
                    {"title": "Resolution", "summary": "They cooperate.", "beats": ["They escape."]},
                ],
            },
        )
        self.db.add(self.outline)
        self.db.flush()
        self.script = Script(
            creative_brief_id=self.brief.id,
            outline_id=self.outline.id,
            content="Current script content.",
        )
        self.db.add(self.script)
        self.db.flush()
        self.version = ScriptVersion(
            script_id=self.script.id,
            version_number=1,
            content="Selected version content: Ava and Ben trigger the museum alarm.",
        )
        self.second_version = ScriptVersion(
            script_id=self.script.id,
            version_number=2,
            content="Different version content: Ava and Ben escape at dawn.",
        )
        self.db.add_all([self.version, self.second_version])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _count_evaluations(self) -> int:
        return self.db.scalar(select(func.count()).select_from(ScriptEvaluation))

    def test_valid_evaluation_persists_python_calculated_average_and_context(self):
        provider = FakeProvider(valid_evaluation())

        evaluation = script_evaluation_service.evaluate_script_version(
            self.db,
            self.brief.id,
            self.version.version_number,
            self.owner.id,
            provider,
        )

        self.assertEqual(evaluation.overall_score, 3.83)
        self.assertEqual(evaluation.script_version_id, self.version.id)
        self.assertEqual(evaluation.criteria["dialogue_quality"]["score"], 2)
        response = ScriptEvaluationResponse.model_validate(evaluation)
        self.assertEqual(response.criteria.dialogue_quality.score, 2)
        self.assertEqual(len(provider.calls), 1)
        self.assertIn(self.version.content, provider.calls[0][1])
        self.assertNotIn(self.second_version.content, provider.calls[0][1])
        self.assertIn(self.brief.topic, provider.calls[0][1])
        self.assertIn(self.outline.content["title"], provider.calls[0][1])
        self.assertIn("Do not include an overall score", provider.calls[0][0])

    def test_fenced_json_is_accepted(self):
        response = f"```json\n{valid_evaluation()}\n```"
        parsed = script_evaluation_service.parse_evaluation_response(response)
        self.assertEqual(parsed.criteria.relevance_to_brief.score, 5)

    def test_invalid_score_malformed_json_and_missing_criteria_are_rejected(self):
        invalid_responses = (
            valid_evaluation(relevance_score=6),
            "{not json",
            json.dumps(
                {
                    "criteria": {
                        "relevance_to_brief": {
                            "score": 4,
                            "explanation": "Relevant",
                        }
                    },
                    "summary": "Incomplete",
                    "strengths": ["Good premise"],
                    "improvement_suggestions": ["Improve pacing"],
                }
            ),
            valid_evaluation(relevance_score=True),
        )
        for response in invalid_responses:
            with self.subTest(response=response[:40]):
                provider = FakeProvider(response)
                with self.assertRaises(
                    script_evaluation_service.InvalidEvaluationResponseError
                ):
                    script_evaluation_service.evaluate_script_version(
                        self.db,
                        self.brief.id,
                        self.version.version_number,
                        self.owner.id,
                        provider,
                    )
                self.assertEqual(self._count_evaluations(), 0)

    def test_provider_failure_does_not_persist_evaluation(self):
        with self.assertRaises(LLMProviderError):
            script_evaluation_service.evaluate_script_version(
                self.db,
                self.brief.id,
                self.version.version_number,
                self.owner.id,
                FakeProvider(LLMProviderError("provider internals")),
            )
        self.assertEqual(self._count_evaluations(), 0)

    def test_repeated_evaluations_are_preserved_and_listed_newest_first(self):
        first = script_evaluation_service.evaluate_script_version(
            self.db,
            self.brief.id,
            self.version.version_number,
            self.owner.id,
            FakeProvider(valid_evaluation()),
        )
        second = script_evaluation_service.evaluate_script_version(
            self.db,
            self.brief.id,
            self.version.version_number,
            self.owner.id,
            FakeProvider(
                valid_evaluation(
                    relevance_score=3,
                    dialogue_explanation="The dialogue could be more distinctive.",
                )
            ),
        )

        evaluations = script_evaluation_service.list_version_evaluations(
            self.db, self.brief.id, self.version.version_number, self.owner.id
        )
        self.assertEqual([item.id for item in evaluations], [second.id, first.id])
        self.assertEqual(len(evaluations), 2)
        self.assertEqual(evaluations[0].criteria["relevance_to_brief"]["score"], 3)

    def test_retrieval_requires_matching_version_and_evaluation(self):
        evaluation = script_evaluation_service.evaluate_script_version(
            self.db,
            self.brief.id,
            self.version.version_number,
            self.owner.id,
            FakeProvider(valid_evaluation()),
        )

        retrieved = script_evaluation_service.get_version_evaluation(
            self.db,
            self.brief.id,
            self.version.version_number,
            evaluation.id,
            self.owner.id,
        )
        self.assertEqual(retrieved.id, evaluation.id)

        with self.assertRaises(HTTPException) as wrong_version:
            script_evaluation_service.get_version_evaluation(
                self.db,
                self.brief.id,
                self.second_version.version_number,
                evaluation.id,
                self.owner.id,
            )
        self.assertEqual(wrong_version.exception.status_code, 404)

    def test_cross_user_and_nonexistent_version_are_hidden(self):
        provider = FakeProvider(valid_evaluation())
        with self.assertRaises(HTTPException) as cross_user:
            script_evaluation_service.evaluate_script_version(
                self.db,
                self.brief.id,
                self.version.version_number,
                self.other_user.id,
                provider,
            )
        self.assertEqual(cross_user.exception.status_code, 404)
        self.assertEqual(provider.calls, [])
        self.assertEqual(self._count_evaluations(), 0)

        with self.assertRaises(HTTPException) as missing_version:
            script_evaluation_service.list_version_evaluations(
                self.db, self.brief.id, 999, self.owner.id
            )
        self.assertEqual(missing_version.exception.status_code, 404)

    def test_cross_user_evaluation_history_and_retrieval_are_hidden(self):
        evaluation = script_evaluation_service.evaluate_script_version(
            self.db,
            self.brief.id,
            self.version.version_number,
            self.owner.id,
            FakeProvider(valid_evaluation()),
        )
        with self.assertRaises(HTTPException) as listed:
            script_evaluation_service.list_version_evaluations(
                self.db, self.brief.id, self.version.version_number, self.other_user.id
            )
        self.assertEqual(listed.exception.status_code, 404)

        with self.assertRaises(HTTPException) as retrieved:
            script_evaluation_service.get_version_evaluation(
                self.db,
                self.brief.id,
                self.version.version_number,
                evaluation.id,
                self.other_user.id,
            )
        self.assertEqual(retrieved.exception.status_code, 404)

    def test_evaluation_requires_approved_outline(self):
        self.outline.is_approved = False
        self.db.commit()
        provider = FakeProvider(valid_evaluation())
        with self.assertRaises(HTTPException) as not_approved:
            script_evaluation_service.evaluate_script_version(
                self.db,
                self.brief.id,
                self.version.version_number,
                self.owner.id,
                provider,
            )
        self.assertEqual(not_approved.exception.status_code, 409)
        self.assertEqual(provider.calls, [])
        self.assertEqual(self._count_evaluations(), 0)
