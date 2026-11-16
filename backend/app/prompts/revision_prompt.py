"""Revision-specific prompt construction using an existing script as data."""

from html import escape

from app.db.models.creative_brief import CreativeBrief
from app.db.models.outline import Outline
from app.db.models.script import Script
from app.prompts.creative_brief_prompt import CreativeBriefPrompt
from app.prompts.script_prompt import build_script_prompt


def build_revision_prompt(
    brief: CreativeBrief, outline: Outline, script: Script, instructions: str
) -> CreativeBriefPrompt:
    """Build trusted revision instructions without treating script text as commands."""
    script_prompt = build_script_prompt(brief, outline)
    system_instructions = f"""{script_prompt.system_instructions}
Revise the current script according to the revision request while preserving
useful material unless the request requires a change. Return the complete
revised script, not a diff, explanation, or partial excerpt.
"""
    user_content = (
        f"{script_prompt.user_content}\n"
        f"<current_script>{escape(script.content)}</current_script>\n"
        f"<revision_instructions>{escape(instructions)}</revision_instructions>"
    )
    return CreativeBriefPrompt(
        system_instructions=system_instructions,
        user_content=user_content,
    )
