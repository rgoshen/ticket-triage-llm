"""Prompt building and version selection — Phase 1."""

from ticket_triage_llm.prompts.triage_v1 import (
    SYSTEM_PROMPT as V1_SYSTEM_PROMPT,
)
from ticket_triage_llm.prompts.triage_v1 import (
    build_user_prompt as v1_build_user_prompt,
)


def get_prompt(version: str, ticket_subject: str, ticket_body: str) -> tuple[str, str]:
    """
    Get system and user prompts for the specified version.

    Args:
        version: Prompt version identifier (e.g., "v1")
        ticket_subject: Ticket subject line
        ticket_body: Ticket body content

    Returns:
        Tuple of (system_prompt, user_prompt)

    Raises:
        ValueError: If version is not recognized
    """
    if version == "v1":
        return (
            V1_SYSTEM_PROMPT,
            v1_build_user_prompt(ticket_subject, ticket_body),
        )
    raise ValueError(f"Unknown prompt version: {version!r}")
