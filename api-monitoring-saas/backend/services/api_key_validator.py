"""API Key utilities — masking only. No validation or dummy checking."""

# ── Constants (used by monitoring_service) ───────────────────
VALID = "VALID"
INVALID = "INVALID"
LIMITED = "LIMITED"
RATE_LIMITED = "RATE_LIMITED"
ERROR = "ERROR"


def mask_api_key(key: str) -> str:
    """Mask API key for safe logging/responses.  sk-1234****abcd"""
    if not key:
        return ""
    if len(key) <= 8:
        return "****" + key[-4:] if len(key) > 4 else "********"
    return f"{key[:4]}{'*' * (len(key) - 8)}{key[-4:]}"
