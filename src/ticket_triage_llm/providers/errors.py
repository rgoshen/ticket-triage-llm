class ProviderError(Exception):
    """Raised when a provider cannot complete a request.

    Covers connection failures, timeouts, and unexpected API errors.
    The triage service maps this to TriageFailure(category='model_unreachable').
    """
