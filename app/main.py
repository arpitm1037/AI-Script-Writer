from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import api_router
from app.db.base import Base, engine
from app.db import models  # noqa: F401  (registers models with Base.metadata)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables that don't yet exist (phase-appropriate; Alembic comes later).
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="AI Script Writer API",
    description="Backend API for the AI Script Writer project",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(api_router)


@app.get("/")
def root():
    """Root endpoint — confirms the API is running."""
    return {"message": "AI Script Writer API is running"}


@app.get("/health")
def health():
    """Health check — reports the status of the service."""
    return {"status": "healthy"}