"""Creative-brief, outline, script, revision, and evaluation API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.base import get_db
from app.db.models.creative_brief import CreativeBrief
from app.db.models.user import User
from app.schemas.creative_brief import (
    CreativeBriefCreate,
    CreativeBriefResponse,
    CreativeBriefUpdate,
)
from app.schemas.prompt import CreativeBriefPromptPreviewResponse
from app.schemas.outline import (
    OutlineGenerateRequest,
    OutlineResponse,
    OutlineUpdateRequest,
)
from app.schemas.script import ScriptGenerateRequest, ScriptResponse, ScriptUpdateRequest
from app.schemas.script_version import ScriptRevisionRequest, ScriptVersionResponse
from app.schemas.script_evaluation import ScriptEvaluationResponse
from app.llm.base import (
    LLMConfigurationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.llm.factory import get_llm_provider
from app.prompts.creative_brief_prompt import build_creative_brief_prompt
from app.services import creative_brief_service
from app.services import outline_service
from app.services import script_service
from app.services import script_evaluation_service
from app.services import script_version_service
from app.validators import creative_brief as brief_validator

router = APIRouter(prefix="/api/v1/creative-briefs", tags=["Creative Briefs"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreativeBriefResponse)
def create_brief(
    payload: CreativeBriefCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CreativeBrief:
    """Create a creative brief owned by the authenticated user."""
    data = brief_validator.validate_create(payload.model_dump())
    return creative_brief_service.create_creative_brief(db, current_user.id, data)


@router.get("", response_model=list[CreativeBriefResponse])
def list_briefs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CreativeBrief]:
    """List the authenticated user's creative briefs."""
    return creative_brief_service.list_user_briefs(db, current_user.id)


@router.post("/{brief_id}/prompt", response_model=CreativeBriefPromptPreviewResponse)
def preview_prompt(
    brief_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CreativeBriefPromptPreviewResponse:
    """Preview a provider-neutral prompt without calling an LLM."""
    brief = creative_brief_service.get_creative_brief(db, brief_id, current_user.id)
    prompt = build_creative_brief_prompt(brief)
    return CreativeBriefPromptPreviewResponse(
        brief_id=brief.id,
        system_instructions=prompt.system_instructions,
        user_content=prompt.user_content,
    )


@router.post(
    "/{brief_id}/outline",
    status_code=status.HTTP_201_CREATED,
    response_model=OutlineResponse,
)
def generate_outline(
    brief_id: int,
    payload: OutlineGenerateRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OutlineResponse:
    """Generate an outline, with explicit opt-in required for regeneration."""
    try:
        outline, created = outline_service.generate_outline(
            db,
            brief_id,
            current_user.id,
            get_llm_provider(),
            regenerate=payload.regenerate,
        )
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="LLM is unavailable") from exc
    except LLMTimeoutError as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="LLM request timed out") from exc
    except LLMRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="LLM rate limit reached") from exc
    except (LLMProviderError, outline_service.InvalidOutlineResponseError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="LLM returned no usable outline") from exc

    if not created:
        response.status_code = status.HTTP_200_OK
    return outline


@router.get("/{brief_id}/outline", response_model=OutlineResponse)
def get_outline(
    brief_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OutlineResponse:
    """Retrieve the current outline for an owned creative brief."""
    return outline_service.get_outline(db, brief_id, current_user.id)


@router.patch("/{brief_id}/outline", response_model=OutlineResponse)
def update_outline(
    brief_id: int,
    payload: OutlineUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OutlineResponse:
    """Edit an unapproved outline using the same structured schema."""
    return outline_service.update_outline(db, brief_id, current_user.id, payload.content)


@router.post("/{brief_id}/outline/approve", response_model=OutlineResponse)
def approve_outline(
    brief_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OutlineResponse:
    """Persist approval and lock the outline against later changes."""
    return outline_service.approve_outline(db, brief_id, current_user.id)


@router.post(
    "/{brief_id}/script",
    status_code=status.HTTP_201_CREATED,
    response_model=ScriptResponse,
)
def generate_script(
    brief_id: int,
    payload: ScriptGenerateRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScriptResponse:
    """Generate a script only from an approved, owned outline."""
    try:
        script, created = script_service.generate_script(
            db,
            brief_id,
            current_user.id,
            get_llm_provider(),
            regenerate=payload.regenerate,
        )
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="LLM is unavailable") from exc
    except LLMTimeoutError as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="LLM request timed out") from exc
    except LLMRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="LLM rate limit reached") from exc
    except (LLMProviderError, script_service.InvalidScriptResponseError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="LLM returned no usable script") from exc

    if not created:
        response.status_code = status.HTTP_200_OK
    return script


@router.get("/{brief_id}/script", response_model=ScriptResponse)
def get_script(
    brief_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScriptResponse:
    """Retrieve a script belonging to the authenticated brief owner."""
    return script_service.get_script(db, brief_id, current_user.id)


@router.patch("/{brief_id}/script", response_model=ScriptResponse)
def update_script(
    brief_id: int,
    payload: ScriptUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScriptResponse:
    """Apply a basic correction to an existing owned script."""
    return script_service.update_script(db, brief_id, current_user.id, payload.content)


@router.post("/{brief_id}/script/revisions", status_code=status.HTTP_201_CREATED, response_model=ScriptVersionResponse)
def revise_script(
    brief_id: int,
    payload: ScriptRevisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScriptVersionResponse:
    """Generate a new immutable script version from revision instructions."""
    try:
        return script_version_service.revise_script(
            db,
            brief_id,
            current_user.id,
            get_llm_provider(),
            payload.revision_instructions,
        )
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="LLM is unavailable") from exc
    except LLMTimeoutError as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="LLM request timed out") from exc
    except LLMRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="LLM rate limit reached") from exc
    except (LLMProviderError, script_service.InvalidScriptResponseError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="LLM returned no usable script") from exc


@router.get("/{brief_id}/script/versions", response_model=list[ScriptVersionResponse])
def list_script_versions(
    brief_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ScriptVersionResponse]:
    """List immutable versions, oldest first."""
    return script_version_service.list_versions(db, brief_id, current_user.id)


@router.get("/{brief_id}/script/versions/{version_number}", response_model=ScriptVersionResponse)
def get_script_version(
    brief_id: int,
    version_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScriptVersionResponse:
    """Retrieve one version belonging to the authenticated user."""
    return script_version_service.get_version(db, brief_id, current_user.id, version_number)


@router.post(
    "/{brief_id}/script/versions/{version_number}/evaluations",
    status_code=status.HTTP_201_CREATED,
    response_model=ScriptEvaluationResponse,
)
def evaluate_script_version(
    brief_id: int,
    version_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScriptEvaluationResponse:
    """Evaluate an owned, approved script version and preserve the result."""
    script_evaluation_service.get_owned_script_version(
        db, brief_id, version_number, current_user.id
    )
    try:
        return script_evaluation_service.evaluate_script_version(
            db,
            brief_id,
            version_number,
            current_user.id,
            get_llm_provider(),
        )
    except LLMConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM is unavailable",
        ) from exc
    except LLMTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="LLM request timed out",
        ) from exc
    except LLMRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="LLM rate limit reached",
        ) from exc
    except (
        LLMProviderError,
        script_evaluation_service.InvalidEvaluationResponseError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM returned no usable evaluation",
        ) from exc


@router.get(
    "/{brief_id}/script/versions/{version_number}/evaluations",
    response_model=list[ScriptEvaluationResponse],
)
def list_script_version_evaluations(
    brief_id: int,
    version_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ScriptEvaluationResponse]:
    """List evaluations for one owned script version, newest first."""
    return script_evaluation_service.list_version_evaluations(
        db, brief_id, version_number, current_user.id
    )


@router.get(
    "/{brief_id}/script/versions/{version_number}/evaluations/{evaluation_id}",
    response_model=ScriptEvaluationResponse,
)
def get_script_version_evaluation(
    brief_id: int,
    version_number: int,
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScriptEvaluationResponse:
    """Retrieve an evaluation only through its owned script version."""
    return script_evaluation_service.get_version_evaluation(
        db, brief_id, version_number, evaluation_id, current_user.id
    )


@router.post(
    "/{brief_id}/script/versions/{version_number}/restore",
    status_code=status.HTTP_201_CREATED,
    response_model=ScriptVersionResponse,
)
def restore_script_version(
    brief_id: int,
    version_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScriptVersionResponse:
    """Restore by appending a new version; no historical row is modified."""
    return script_version_service.restore_version(db, brief_id, current_user.id, version_number)


@router.get("/{brief_id}", response_model=CreativeBriefResponse)
def get_brief(
    brief_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CreativeBrief:
    """Get one of the authenticated user's creative briefs."""
    return creative_brief_service.get_creative_brief(db, brief_id, current_user.id)


@router.patch("/{brief_id}", response_model=CreativeBriefResponse)
def update_brief(
    brief_id: int,
    payload: CreativeBriefUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CreativeBrief:
    """Update one of the authenticated user's creative briefs."""
    data = brief_validator.validate_update(
        payload.model_dump(exclude_unset=True, exclude_none=True)
    )
    return creative_brief_service.update_creative_brief(db, brief_id, current_user.id, data)


@router.delete("/{brief_id}")
def delete_brief(
    brief_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Delete one of the authenticated user's creative briefs."""
    creative_brief_service.delete_creative_brief(db, brief_id, current_user.id)
    return {"message": "Creative brief deleted"}
