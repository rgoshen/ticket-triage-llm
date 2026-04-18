"""Experiment result data structures — Phase 3."""

from dataclasses import asdict, dataclass


@dataclass
class ModelMetrics:
    model: str
    run_id: str
    category_accuracy: float
    severity_accuracy: float
    routing_accuracy: float
    escalation_accuracy: float
    json_valid_rate: float
    schema_pass_rate: float
    retry_rate: float
    retry_success_rate: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    avg_tokens_per_second: float | None
    avg_tokens_input: float
    avg_tokens_output: float
    avg_tokens_total: float
    total_tickets: int
    successful_tickets: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExperimentSummary:
    experiment_id: str
    experiment_name: str
    date: str
    dataset_size: int
    prompt_version: str
    model_metrics: list[ModelMetrics]

    def to_dict(self) -> dict:
        return asdict(self)
