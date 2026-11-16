"""Response model for provider-neutral prompt previews."""

from pydantic import BaseModel


class CreativeBriefPromptPreviewResponse(BaseModel):
    """Provider-neutral preview of the prompt derived from one brief."""

    brief_id: int
    system_instructions: str
    user_content: str
