"""Regression tests for API route registration and authentication contracts."""

import unittest

from fastapi import HTTPException

from app.core.security import get_current_user
from app.main import app


class RouteContractTests(unittest.TestCase):
    def test_existing_routes_and_prompt_preview_are_registered(self):
        def iter_routes(routes):
            for route in routes:
                nested_router = getattr(route, "original_router", None)
                if nested_router is not None:
                    yield from iter_routes(nested_router.routes)
                else:
                    yield route

        routes = {
            (route.path, method)
            for route in iter_routes(app.routes)
            for method in getattr(route, "methods", set())
        }
        expected_routes = {
            ("/", "GET"),
            ("/health", "GET"),
            ("/api/v1/auth/signup", "POST"),
            ("/api/v1/auth/login", "POST"),
            ("/api/v1/auth/me", "GET"),
            ("/api/v1/creative-briefs", "POST"),
            ("/api/v1/creative-briefs", "GET"),
            ("/api/v1/creative-briefs/{brief_id}", "GET"),
            ("/api/v1/creative-briefs/{brief_id}", "PATCH"),
            ("/api/v1/creative-briefs/{brief_id}", "DELETE"),
            ("/api/v1/creative-briefs/{brief_id}/prompt", "POST"),
            ("/api/v1/creative-briefs/{brief_id}/outline", "POST"),
            ("/api/v1/creative-briefs/{brief_id}/outline", "GET"),
            ("/api/v1/creative-briefs/{brief_id}/outline", "PATCH"),
            ("/api/v1/creative-briefs/{brief_id}/outline/approve", "POST"),
            ("/api/v1/creative-briefs/{brief_id}/script", "POST"),
            ("/api/v1/creative-briefs/{brief_id}/script", "GET"),
            ("/api/v1/creative-briefs/{brief_id}/script", "PATCH"),
            ("/api/v1/creative-briefs/{brief_id}/script/revisions", "POST"),
            ("/api/v1/creative-briefs/{brief_id}/script/versions", "GET"),
            ("/api/v1/creative-briefs/{brief_id}/script/versions/{version_number}", "GET"),
            ("/api/v1/creative-briefs/{brief_id}/script/versions/{version_number}/evaluations", "POST"),
            ("/api/v1/creative-briefs/{brief_id}/script/versions/{version_number}/evaluations", "GET"),
            ("/api/v1/creative-briefs/{brief_id}/script/versions/{version_number}/evaluations/{evaluation_id}", "GET"),
            ("/api/v1/creative-briefs/{brief_id}/script/versions/{version_number}/restore", "POST"),
        }
        self.assertTrue(expected_routes.issubset(routes))

    def test_missing_credentials_remain_unauthorized(self):
        with self.assertRaises(HTTPException) as raised:
            get_current_user(credentials=None, db=object())
        self.assertEqual(raised.exception.status_code, 401)
