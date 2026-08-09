import re
from typing import Pattern


EMAIL_REGEX: Pattern = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)


def is_valid_email(email: str) -> bool:
    """Validate an email address using RFC 5322 compliant regex."""
    if not email or len(email) > 254:
        return False
    return bool(EMAIL_REGEX.match(email))


def validate_email(email: str) -> tuple[bool, str]:
    """Validate email and return (is_valid, error_message)."""
    if not email:
        return False, "Email cannot be empty"
    if len(email) > 254:
        return False, "Email exceeds 254 characters"
    if not EMAIL_REGEX.match(email):
        return False, "Invalid email format"
    return True, ""