"""Public error taxonomy without echoing private inputs or provider outputs."""


class LabelerError(Exception):
    code = "labeler_error"
    status_code = 500
    public_message = "Label generation failed"


class InputLimitError(LabelerError):
    code = "input_limit_exceeded"
    status_code = 413
    public_message = "Input exceeds configured limits"


class RequestValueError(LabelerError):
    code = "invalid_request"
    status_code = 422
    public_message = "Request violates configured constraints"


class ProviderUnavailable(LabelerError):
    code = "provider_unavailable"
    status_code = 503
    public_message = "AI provider is not configured or is unavailable"


class ProviderTimeout(LabelerError):
    code = "provider_timeout"
    status_code = 504
    public_message = "AI provider timed out"


class ProviderFailure(LabelerError):
    code = "provider_failure"
    status_code = 502
    public_message = "AI provider returned an error or invalid response"
