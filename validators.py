"""
AutoPitch v3 — Input Validation & Sanitization
Prevents header injection, validates URLs, emails, and file uploads.
"""

import re
from pathlib import Path

from config import cfg


# ── Email ──────────────────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def is_valid_email(email: str) -> bool:
    """Check email format and reject known no-reply patterns."""
    if not email or not isinstance(email, str):
        return False
    lower = email.lower().strip()
    if any(skip in lower for skip in cfg.skip_email_patterns):
        return False
    return bool(_EMAIL_RE.match(lower))


def sanitize_email(email: str) -> str:
    """Strip whitespace and newline characters from email to prevent header injection."""
    if not email:
        return ""
    return re.sub(r"[\r\n]", "", email.strip())


# ── Name / Header ──────────────────────────────────────────────────────────────

def sanitize_sender_name(name: str) -> str:
    """Remove newlines and control chars from sender name to prevent SMTP header injection."""
    if not name:
        return ""
    # Remove CR, LF, and any control characters
    cleaned = re.sub(r"[\r\n\x00-\x1f\x7f]", "", name.strip())
    # Limit length
    return cleaned[:120]


def sanitize_header(value: str) -> str:
    """General-purpose header value sanitization."""
    if not value:
        return ""
    return re.sub(r"[\r\n]", "", value.strip())


# ── URL ────────────────────────────────────────────────────────────────────────

_LINKEDIN_RE = re.compile(
    r"^https?://(www\.)?linkedin\.com/in/[a-zA-Z0-9\-_%/]+/?$"
)


def validate_linkedin_url(url: str) -> tuple[bool, str]:
    """Validate a LinkedIn profile URL. Returns (is_valid, cleaned_url_or_error)."""
    if not url:
        return False, "LinkedIn URL is required."
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    if _LINKEDIN_RE.match(url):
        return True, url
    # Allow slightly looser URLs — just check it's linkedin.com
    if "linkedin.com/in/" in url:
        return True, url
    return False, (
        "Please enter a valid LinkedIn profile URL "
        "(e.g. https://www.linkedin.com/in/yourname/)."
    )


# ── File Upload ────────────────────────────────────────────────────────────────

MAX_PDF_SIZE_MB = 10
ALLOWED_PDF_EXTENSIONS = {".pdf"}


def validate_pdf_upload(filename: str, file_size: int) -> tuple[bool, str]:
    """Validate PDF file name and size. Returns (is_valid, error_message)."""
    if not filename:
        return False, "No file selected."

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_PDF_EXTENSIONS:
        return False, f"Only PDF files are accepted. You uploaded a {ext} file."

    max_bytes = MAX_PDF_SIZE_MB * 1024 * 1024
    if file_size > max_bytes:
        return False, (
            f"File too large ({file_size / 1024 / 1024:.1f} MB). "
            f"Maximum size is {MAX_PDF_SIZE_MB} MB."
        )

    return True, ""


def validate_num_companies(num: int) -> tuple[bool, str]:
    """Validate the number of companies slider value."""
    if cfg.min_companies <= num <= cfg.max_companies:
        return True, ""
    return False, (
        f"Number of companies must be between {cfg.min_companies} "
        f"and {cfg.max_companies}."
    )