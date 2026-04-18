"""Repair prompt for bounded retry — Phase 2.

Used by the retry service when the first LLM attempt produces invalid output.
Includes the failed output and the specific error so the model can self-correct.
This prompt is NOT dispatched through get_prompt() — it is called directly by
the retry service.
"""

REPAIR_SYSTEM_PROMPT = """\
You previously produced invalid output when asked to classify a support ticket. \
Your output could not be parsed or did not match the required schema.

You must respond with ONLY a valid JSON object. No markdown fences, no \
explanation, no preamble, no postamble — just the JSON object.

The JSON object must contain exactly these fields:

{
  "category": string,
  "severity": string,
  "routingTeam": string,
  "summary": string,
  "businessImpact": string,
  "draftReply": string,
  "confidence": number,
  "escalation": boolean
}

Field specifications:

- "category" — one of: "billing", "outage", "account_access", "bug", \
"feature_request", "other"
- "severity" — one of: "low", "medium", "high", "critical"
- "routingTeam" — one of: "support", "billing", "infra", "product", "security"
- "summary" — a 1–2 sentence summary of what the ticket is about
- "businessImpact" — a brief description of how this issue affects the \
customer's business
- "draftReply" — a professional, empathetic first-response draft addressed \
to the customer
- "confidence" — a float between 0.0 and 1.0 indicating your confidence \
in the classification
- "escalation" — true if the ticket requires immediate human attention, \
false otherwise\
"""


def build_repair_user_prompt(raw_output: str, error_message: str) -> str:
    return (
        "Your previous output was:\n\n"
        f"<failed_output>\n{raw_output}\n</failed_output>\n\n"
        f"The error was: {error_message}\n\n"
        "Please produce the corrected JSON object now."
    )
