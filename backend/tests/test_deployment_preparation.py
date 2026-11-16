"""Regression tests for deployment settings, health checks, and migrations."""

import unittest
from unittest.mock import MagicMock, patch

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.db.base import Base
import app.db.models  # noqa: F401
from app.main import app


class ProductionSettingsTests(unittest.TestCase):
    def production_settings(self, **overrides):
        values = {
            "APP_ENV": "production",
            "DEBUG": False,
            "SECRET_KEY": "test-secret-value-" * 3,
            "DATABASE_URL": "postgresql+psycopg://user:test-password@db.example:5432/aiwriter",
            "GEMINI_API_KEY": "test-gemini-key-not-a-credential",
            "CORS_ALLOWED_ORIGINS": "https://frontend.example",
            "TRUSTED_HOSTS": "api.example",
            "_env_file": None,
        }
        values.update(overrides)
        return Settings(**values)

    def test_development_defaults_are_local_and_debug_enabled(self):
        settings = Settings(
            _env_file=None,
            APP_ENV="development",
            SECRET_KEY="local-test-secret",
            DATABASE_URL="postgresql+psycopg://localhost/aiwriter",
        )

        self.assertTrue(settings.debug_enabled)
        self.assertEqual(settings.cors_origins, [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ])
        self.assertIn("localhost", settings.trusted_hosts)

    def test_valid_production_configuration_is_accepted(self):
        settings = self.production_settings()

        self.assertFalse(settings.debug_enabled)
        self.assertEqual(settings.cors_origins, ["https://frontend.example"])
        self.assertEqual(settings.trusted_hosts, ["api.example"])

    def test_production_rejects_placeholder_secret_without_echoing_it(self):
        secret = "sensitive-production-key"

        with self.assertRaises(RuntimeError) as raised:
            self.production_settings(SECRET_KEY=secret)

        self.assertIn("SECRET_KEY", str(raised.exception))
        self.assertNotIn(secret, str(raised.exception))

    def test_production_requires_gemini_key(self):
        with self.assertRaises(RuntimeError) as raised:
            self.production_settings(GEMINI_API_KEY=None)

        self.assertIn("GEMINI_API_KEY", str(raised.exception))

    def test_production_requires_explicit_database_url(self):
        values = {
            "APP_ENV": "production",
            "DEBUG": False,
            "SECRET_KEY": "test-secret-value-" * 3,
            "GEMINI_API_KEY": "test-gemini-key-not-a-credential",
            "CORS_ALLOWED_ORIGINS": "https://frontend.example",
            "TRUSTED_HOSTS": "api.example",
            "_env_file": None,
        }

        with self.assertRaises(ValidationError) as raised:
            Settings(**values)

        self.assertIn("DATABASE_URL", str(raised.exception))

    def test_production_rejects_local_database_and_insecure_origins(self):
        with self.assertRaises(RuntimeError):
            self.production_settings(
                DATABASE_URL="postgresql+psycopg://user:password@localhost/aiwriter"
            )
        with self.assertRaises(RuntimeError):
            self.production_settings(CORS_ALLOWED_ORIGINS="http://frontend.example")
        with self.assertRaises(RuntimeError):
            self.production_settings(TRUSTED_HOSTS="*")
        with self.assertRaises(RuntimeError):
            self.production_settings(DEBUG=True)

    def test_missing_required_secret_is_a_configuration_error(self):
        with self.assertRaises(ValidationError) as raised:
            Settings(_env_file=None, APP_ENV="development")

        self.assertNotIn("sensitive-production-key", str(raised.exception))


class DeploymentRouteTests(unittest.TestCase):
    def test_liveness_and_legacy_health_do_not_require_database(self):
        with patch("app.main.engine.connect") as connect:
            with TestClient(app) as client:
                self.assertEqual(client.get("/health/live").json(), {"status": "alive"})
                self.assertEqual(client.get("/health").json(), {"status": "healthy"})

        connect.assert_not_called()

    def test_readiness_returns_ready_after_database_probe(self):
        connection = MagicMock()
        connection_manager = MagicMock()
        connection_manager.__enter__.return_value = connection

        with patch("app.main.engine.connect", return_value=connection_manager):
            with TestClient(app) as client:
                response = client.get("/health/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ready"})
        connection.execute.assert_called_once()

    def test_readiness_hides_database_failure_details(self):
        error = OperationalError(
            "SELECT 1",
            {},
            Exception("sensitive database credential"),
        )

        with patch("app.main.engine.connect", side_effect=error):
            with TestClient(app) as client:
                response = client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": "Database unavailable"})
        self.assertNotIn("sensitive database credential", response.text)

    def test_cors_allows_configured_development_origin(self):
        with TestClient(app) as client:
            response = client.options(
                "/",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "GET",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://localhost:5173",
        )

    def test_untrusted_host_is_rejected(self):
        with TestClient(app) as client:
            response = client.get("/", headers={"host": "attacker.example"})

        self.assertEqual(response.status_code, 400)


class MigrationRegistrationTests(unittest.TestCase):
    def test_all_phase_one_to_nine_models_are_registered(self):
        self.assertEqual(
            set(Base.metadata.tables),
            {
                "users",
                "creative_briefs",
                "outlines",
                "scripts",
                "script_versions",
                "script_evaluations",
            },
        )

    def test_initial_baseline_is_the_only_head_revision(self):
        revision = ScriptDirectory.from_config(Config("alembic.ini")).get_revision("head")

        self.assertIsNotNone(revision)
        self.assertIsNone(revision.down_revision)
        self.assertEqual(revision.revision, "6484a3681cc9")


if __name__ == "__main__":
    unittest.main()
