# 0004. Provider abstraction via Python Protocol

## Status

Accepted

## Context

The triage pipeline needs to call an LLM to produce structured triage output. Today, the only concrete provider is Ollama running locally with Qwen 3.5 models. However, the project's design anticipates the possibility of adding a cloud-hosted Qwen provider in a future iteration (documented in the decision log, OD-2), and the evaluation harness needs to run the same benchmark suite across multiple model sizes (2B, 4B, 9B) without changing pipeline code.

This creates two requirements:

1. The pipeline should not know or care whether it's talking to a local Ollama instance or a remote API. Infrastructure concerns should be isolated from business logic.
2. Swapping between models and providers should be a configuration change, not a code change. The eval runner needs to iterate over providers programmatically, and the Triage tab's model selector dropdown needs to switch providers at runtime.

The question is how to define the boundary between the pipeline and the LLM provider — what abstraction to use, how strict the contract is, and whether it should use inheritance or structural typing.

## Options Considered

### Option A: Python Protocol (structural typing)

Define an `LlmProvider` Protocol with a `name` attribute and a `generate_structured_ticket()` method. Any class that implements this shape satisfies the protocol without needing to explicitly inherit from it. The pipeline type-hints its provider dependency as `LlmProvider` and the type checker verifies conformance at static analysis time.

### Option B: Abstract base class (ABC)

Define an `LlmProvider` ABC with `@abstractmethod` decorators. Concrete providers inherit from it explicitly. The runtime raises `TypeError` if a subclass fails to implement the required methods.

### Option C: No abstraction, direct Ollama calls

Call the Ollama client directly from the pipeline code. To support a second provider later, add conditional branching (`if provider == "ollama": ... elif provider == "cloud": ...`).

### Option D: Dependency injection via callable

Define the provider as a plain callable `(str, str) -> ModelResult` — a function rather than an object. The pipeline accepts the callable as a parameter. No class hierarchy, no protocol.

## Decision

We chose **Option A: Python Protocol**.

```python
from typing import Protocol
from .schemas import ModelResult

class LlmProvider(Protocol):
    name: str

    def generate_structured_ticket(
        self,
        ticket_body: str,
        prompt_version: str,
    ) -> ModelResult:
        ...
```

Concrete implementations:

- `OllamaQwenProvider` — calls Ollama's OpenAI-compatible endpoint at `http://localhost:11434/v1` via the `openai` Python client. Accepts a `model` parameter at construction time (e.g., `qwen3.5:9b`) so the same class serves all local model sizes.
- `CloudQwenProvider` — placeholder for future cloud integration. The file exists in the codebase with a `NotImplementedError` body, so that the provider abstraction is demonstrably real and a cloud provider can be added without refactoring the pipeline or the eval runner.

The `provider_router` service maintains a registry of available providers and selects the active one based on UI input or eval runner configuration.

## Rationale

1. **Protocol is the idiomatic Python approach for this pattern.** Protocols were introduced in PEP 544 specifically for structural subtyping — defining an interface by shape rather than by inheritance. They're checked by mypy and pyright at static analysis time, which gives the same safety as an ABC without requiring explicit subclassing. For a project that uses `ruff` and type hints throughout, this is the natural fit.

2. **Structural typing is more flexible than inheritance for a provider pattern.** With an ABC, every provider must explicitly `class MyProvider(LlmProvider)`. With a Protocol, any class that happens to have the right `name` attribute and `generate_structured_ticket()` method satisfies the contract. This makes it trivially easy to write test doubles (a `FakeProvider` that returns canned responses) or to wrap third-party client libraries without shoehorning them into an inheritance hierarchy.

3. **An abstraction boundary exists even with one concrete provider today.** The eval runner needs to iterate over `[OllamaQwenProvider("qwen3.5:2b"), OllamaQwenProvider("qwen3.5:4b"), OllamaQwenProvider("qwen3.5:9b")]` and treat them interchangeably. The Triage tab needs to switch between them via a dropdown. Even without a cloud provider, the abstraction is doing real work on day one — it's not speculative.

4. **Direct Ollama calls (Option C) would couple infrastructure to business logic.** If the pipeline calls `openai.ChatCompletion.create(base_url="http://localhost:11434/v1", model="qwen3.5:9b", ...)` directly, then every test of the pipeline requires a running Ollama instance. With the provider abstraction, the pipeline accepts an `LlmProvider` and tests can inject a `FakeProvider` that returns canned or randomized responses. This is the difference between integration-testable and unit-testable.

5. **A callable (Option D) is too thin for what the provider needs to carry.** Providers have identity (`name`), configuration (model name, endpoint URL, API keys), and potentially lifecycle (connection pooling, token tracking). A bare function `(str, str) -> ModelResult` doesn't have a natural place for any of that. A Protocol-typed class does.

## Tradeoffs

- **Upside:** Clean separation between pipeline logic and infrastructure. Trivially testable via fake providers. Supports runtime switching (UI dropdown, eval runner iteration) without code changes. Idiomatic Python. Type-checked at static analysis time.

- **Downside:** Protocols are less explicit than ABCs — a developer reading a concrete provider class doesn't see `class OllamaQwenProvider(LlmProvider)` and might not immediately realize it's implementing a protocol. The connection between the protocol and its implementations is implicit rather than declared.

- **Why we accept the downside:** The protocol definition is small (one attribute, one method), lives in a single file (`providers/base.py`), and is documented in this ADR. The implicitness is a minor readability cost that is outweighed by the flexibility of structural typing. For a project with a small number of providers (2–3 at most), the risk of a developer accidentally breaking protocol conformance without noticing is low, and static analysis catches it if they do.

## Consequences

- The pipeline's `triage_service.run_triage()` accepts an `LlmProvider` as a parameter (injected by the `provider_router` service or by the eval runner). It never imports or references a concrete provider class.

- The eval runner iterates over a list of `LlmProvider` instances and runs the same benchmark suite against each. Adding a new model size or a new provider is a one-line change to the list, not a code change to the runner.

- The Triage tab's model/provider dropdown is populated from the `provider_router`'s registry. Selecting a different entry changes which `LlmProvider` instance is passed to `run_triage()`. No page reload, no restart.

- `OllamaQwenProvider` is parameterized by model name at construction time. There is one class, not one class per model size. `OllamaQwenProvider("qwen3.5:9b")` and `OllamaQwenProvider("qwen3.5:4b")` are two instances of the same class with different configurations.

- `CloudQwenProvider` exists as a file with a `NotImplementedError` body. Its presence in the codebase demonstrates that the abstraction is real and a second provider can be integrated without refactoring. Its `NotImplementedError` prevents accidental use before the implementation exists.

- Test doubles (`FakeProvider`, `SlowProvider`, `FailingProvider`) can be written in test code and injected into the pipeline without modifying production code. This supports targeted testing of retry logic (inject `FailingProvider`), latency behavior (inject `SlowProvider`), and happy-path logic (inject `FakeProvider` with canned responses).

## Alternatives Not Chosen

- **Option B (ABC):** rejected because explicit inheritance is unnecessary for a two-method interface and adds rigidity without adding safety. ABCs enforce conformance at instantiation time, which catches errors later than static analysis does. Protocols catch them at `ruff` / `mypy` time.

- **Option C (direct Ollama calls):** rejected because it couples infrastructure to business logic, makes the pipeline impossible to unit-test without a running Ollama instance, and makes adding a second provider a refactoring exercise rather than a configuration change.

- **Option D (callable):** rejected because providers carry identity and configuration beyond what a bare function signature can express. A callable works for trivial cases but doesn't scale to providers that need a `name` for trace logging, an endpoint URL, or an API key.

## Addendum: Cloud models via Ollama passthrough (no new provider class needed) (2026-04-19)

**Date:** 2026-04-19

**Status:** The Decision above stands. The `CloudQwenProvider` stub in `src/ticket_triage_llm/providers/cloud_qwen.py` remains a `NotImplementedError` placeholder — **and it should stay that way** unless the project needs a non-Ollama cloud path.

Ollama itself provides a cloud-model passthrough. When a user signs into `ollama.com` from their local Ollama server (`ollama signin`), certain cloud models appear in `ollama list` with a `:cloud` suffix (e.g., `qwen3.5:397b-cloud`). The local `:11434` endpoint transparently proxies requests for those models to `ollama.com:443`. From the perspective of the app's existing `OllamaQwenProvider`, a `:cloud`-suffixed model is just another model name. No code changes are required to use it — the user adds the name to `OLLAMA_MODELS` and the existing provider class handles it.

This means **the cloud path works today via configuration**, not via a new provider class. The `CloudQwenProvider` stub exists for the *different* case: a direct integration with a non-Ollama cloud API (Alibaba DashScope, Anthropic, OpenAI, etc.) that does not route through an Ollama server. That direct-integration case is deferred to `docs/future-improvements.md` and is not needed for the Ollama-proxied cloud path.

The Protocol-based abstraction is doing exactly what this ADR predicted: the decision about which endpoint serves a model name is a configuration concern, not a code concern. Proving this out with the cloud passthrough is why the `OllamaQwenProvider` remains model-agnostic (no branching on model name, no hardcoded list of supported models) — see `CLAUDE.md` § "Hardware & model constraints."

Documented in `README.md` § "Managing models — Using cloud models via Ollama's passthrough" with a caveat: sampling-parameter honoring by the cloud backend (`num_ctx`, `think=false`, `temperature`, etc.) is unverified, and cloud runs should not be directly compared against the Phase 3/4 benchmark numbers until a smoke test confirms the parameters round-trip.

No code changes in this addendum.
