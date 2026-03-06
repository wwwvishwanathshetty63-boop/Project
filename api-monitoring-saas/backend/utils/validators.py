import re
from urllib.parse import urlparse


def validate_email(email: str) -> bool:
    """Validate email format."""
    if not email or not isinstance(email, str):
        return False
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email.strip()))


def validate_password(password: str) -> tuple[bool, str]:
    """Validate password strength. Returns (is_valid, error_message)."""
    if not password or not isinstance(password, str):
        return False, "Password is required"
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r"[A-Za-z]", password):
        return False, "Password must contain at least one letter"
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one number"
    return True, ""


def validate_url(url: str) -> bool:
    """Validate URL format."""
    if not url or not isinstance(url, str):
        return False
    try:
        result = urlparse(url.strip())
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


def validate_name(name: str, min_len: int = 2, max_len: int = 100) -> bool:
    """Validate a name string."""
    if not name or not isinstance(name, str):
        return False
    name = name.strip()
    return min_len <= len(name) <= max_len


def validate_http_method(method: str) -> bool:
    """Validate HTTP method."""
    valid_methods = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
    return isinstance(method, str) and method.strip().upper() in valid_methods


def validate_interval(interval: int) -> bool:
    """Validate monitoring interval (in seconds). Min 30s, max 3600s."""
    try:
        interval = int(interval)
        return 30 <= interval <= 3600
    except (TypeError, ValueError):
        return False


def sanitize_string(value: str) -> str:
    """Basic string sanitization."""
    if not isinstance(value, str):
        return ""
    return value.strip()
