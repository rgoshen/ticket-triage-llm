from pydantic import BaseModel, field_validator


class TriageInput(BaseModel):
    ticket_body: str
    ticket_subject: str = ""
    model: str | None = None
    prompt_version: str = "v1"

    @field_validator("ticket_body")
    @classmethod
    def body_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("ticket_body must not be empty or whitespace-only")
        return v
