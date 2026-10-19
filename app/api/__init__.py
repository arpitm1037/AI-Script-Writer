from fastapi import APIRouter

from app.api.routes import auth, creative_briefs

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(creative_briefs.router)