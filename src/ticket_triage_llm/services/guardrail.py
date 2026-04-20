"""Pre-LLM input screening — Phase 2.

Heuristic-only guardrail per ADR 0008. Pattern matching for known injection
phrases, structural markers, length checks, and basic PII. No LLM-based
classification — baseline numbers from this guardrail are a Phase 4 deliverable.
"""

import re
from dataclasses import dataclass, field
from typing import Literal

_INJECTION_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "injection:ignore_previous",
        re.compile(r"ignore\b.{0,30}\binstructions\b", re.IGNORECASE),
    ),
    (
        "injection:disregard",
        re.compile(r"disregard\s+(above|previous|all)", re.IGNORECASE),
    ),
    ("injection:pretend_you_are", re.compile(r"pretend\s+you\s+are\b", re.IGNORECASE)),
    ("injection:system_prompt", re.compile(r"system\s+prompt\s*:", re.IGNORECASE)),
    (
        "injection:new_instructions",
        re.compile(r"new\s+instructions\s*:", re.IGNORECASE),
    ),
]

# FP-prone injection rules demoted to warn — "act as" matches "act as a liaison",
# "you are now" matches "you are now on the escalation list". Phase 4 will measure.
_INJECTION_WARN_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("injection:you_are_now", re.compile(r"you\s+are\s+now\b", re.IGNORECASE)),
    ("injection:act_as", re.compile(r"\bact\s+as\b", re.IGNORECASE)),
]

_STRUCTURAL_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("structural:system_tag", re.compile(r"</?system>", re.IGNORECASE)),
    ("structural:inst_tag", re.compile(r"\[/?INST\]", re.IGNORECASE)),
    ("structural:sys_delimiter", re.compile(r"<<<?\s*SYS\s*>>>?", re.IGNORECASE)),
]

_PII_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("pii:ssn_pattern", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    (
        "pii:credit_card_pattern",
        re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{1,7}\b"),
    ),
]


@dataclass
class GuardrailResult:
    decision: Literal["pass", "warn", "block"]
    matched_rules: list[str] = field(default_factory=list)


def check_guardrail(ticket_body: str, max_length: int = 10_000) -> GuardrailResult:
    matched: list[str] = []
    has_block = False
    has_warn = False

    for rule_name, pattern in _INJECTION_RULES:
        if pattern.search(ticket_body):
            matched.append(rule_name)
            has_block = True

    for rule_name, pattern in _STRUCTURAL_RULES:
        if pattern.search(ticket_body):
            matched.append(rule_name)
            has_block = True

    for rule_name, pattern in _INJECTION_WARN_RULES:
        if pattern.search(ticket_body):
            matched.append(rule_name)
            has_warn = True

    if len(ticket_body) > max_length:
        matched.append("length:exceeded")
        has_warn = True

    for rule_name, pattern in _PII_RULES:
        if pattern.search(ticket_body):
            matched.append(rule_name)
            has_warn = True

    if has_block:
        return GuardrailResult(decision="block", matched_rules=matched)
    if has_warn:
        return GuardrailResult(decision="warn", matched_rules=matched)
    return GuardrailResult(decision="pass", matched_rules=matched)
