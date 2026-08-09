import re
from typing import Pattern


EMAIL_PATTERN: Pattern[str] = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)


def validate_email(email: str) -> bool:
    """Validate an email address using RFC 5322 compliant regex.

    Args:
        email: The email address to validate.

    Returns:
        True if the email is valid, False otherwise.
    """
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_PATTERN.match(email.strip()))


if __name__ == "__main__":
    test_emails = [
        "user@example.com",
        "user.name@domain.co.uk",
        "user+tag@example.org",
        "invalid.email@",
        "@no-local-part.com",
        "no-at-symbol.com",
        "user@.com",
        "user@domain",
        "",
        "user@domain.c",
    ]

    for email in test_emails:
        print(f"{email!r:30} -> {validate_email(email)}")