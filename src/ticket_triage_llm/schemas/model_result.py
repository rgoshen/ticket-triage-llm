from pydantic import BaseModel


class ModelResult(BaseModel):
    raw_output: str
    model: str
    latency_ms: float
    tokens_input: int
    tokens_output: int
    tokens_total: int
    tokens_per_second: float | None = None
