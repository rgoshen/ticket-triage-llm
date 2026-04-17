"""Prompt building and version selection — Phase 1."""

from ticket_triage_llm.prompts.triage_v1 import (
    SYSTEM_PROMPT as V1_SYSTEM_PROMPT,
)
from ticket_triage_llm.prompts.triage_v1 import (
    build_user_prompt as v1_build_user_prompt,
)


def get_prompt(version: str, ticket_subject: str, ticket_body: str) -> tuple[str, str]:
    if version == "v1":
        return (
            V1_SYSTEM_PROMPT,
            v1_build_user_prompt(ticket_subject, ticket_body),
        )
    if version == "__repair__":
        return (ticket_subject, ticket_body)
    raise ValueError(f"Unknown prompt version: {version!r}")
