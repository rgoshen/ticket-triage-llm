# Architecture Decision Records

This directory contains the Architecture Decision Records (ADRs) for `ticket-triage-llm`.

## What goes in an ADR

ADRs capture **architectural** decisions — choices about the structure, components, technologies, patterns, and interfaces of the system. If a decision is about *how the system is built*, it belongs here.

Decisions about *what the project is, isn't, or why* (scope, framing, priorities, things considered and rejected) belong in the [decision log](../decisions/decision-log.md) instead, not in an ADR.

## Format

ADRs follow the standard format used by [`adr-tools`](https://github.com/npryce/adr-tools): numbered, zero-padded to four digits, one decision per file, with sections for Status, Context, Options Considered, Decision, Rationale, Tradeoffs, Consequences, and Alternatives Not Chosen.

## Index

| Number | Title | Status |
|---|---|---|
| [0001](0001-language-and-stack.md) | Language and stack choice | Accepted |
| [0002](0002-validator-first-pipeline-with-bounded-retry.md) | Validator-first pipeline with bounded retry | Accepted |

## Status definitions

- **Proposed** — under discussion, not yet acted on
- **Accepted** — decided and in effect
- **Superseded** — replaced by a later ADR (link to the replacement)
- **Deprecated** — no longer in effect, not replaced
