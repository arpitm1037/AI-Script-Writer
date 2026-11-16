"""Create the FastAPI application and expose health-check endpoints."""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api import api_router
from app.core.config import settings
from app.db.base import engine

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting environment=%s", settings.APP_ENV)
    yield
    engine.dispose()


app = FastAPI(
    title="AI Script Writer API",
    description="Backend API for the AI Script Writer project",
    version="1.0.0",
    debug=settings.debug_enabled,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)


@app.middleware("http")
async def log_request_summary(request: Request, call_next):
    started_at = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    logger.info(
        "request method=%s path=%s status=%s duration_ms=%.1f",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled request error type=%s method=%s path=%s",
        type(exc).__name__,
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


app.include_router(api_router)


@app.get("/")
def root():
    """Root endpoint — confirms the API is running."""
    return {"message": "AI Script Writer API is running"}


@app.get("/health")
def health():
    """Backward-compatible application liveness endpoint."""
    return {"status": "healthy"}


@app.get("/health/live")
def liveness():
    """Report that the application process can respond."""
    return {"status": "alive"}


@app.get("/health/ready")
def readiness():
    """Report readiness only when the configured database is reachable."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.warning("database readiness check failed")
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable"},
        )
    return {"status": "ready"}