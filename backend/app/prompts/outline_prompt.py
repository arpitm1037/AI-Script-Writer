"""Outline-specific instructions layered over the Creative Brief prompt."""

from app.db.models.creative_brief import CreativeBrief
from app.prompts.creative_brief_prompt import CreativeBriefPrompt, build_creative_brief_prompt


OUTLINE_INSTRUCTIONS = """
Create a concise, production-ready script outline from the creative brief.
Return JSON only, with this exact top-level structure:
{
  "title": "string",
  "logline": "string",
  "acts": [
    {"title": "string", "summary": "string", "beats": ["string"]}
  ]
}
Include three to five acts. Each act must have at least one beat. Do not add
Markdown fences, commentary, or fields outside this schema.
"""


def build_outline_prompt(brief: CreativeBrief) -> CreativeBriefPrompt:
    """Reuse Creative Brief data while adding only trusted outline instructions."""
    brief_prompt = build_creative_brief_prompt(brief)
    return CreativeBriefPrompt(
        system_instructions=f"{brief_prompt.system_instructions}\n{OUTLINE_INSTRUCTIONS}",
        user_content=brief_prompt.user_content,
    )
