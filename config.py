"""
AutoPitch v3 — Centralized Configuration
Loads secrets from environment variables first, then .env file,
then falls back to Streamlit secrets (for Streamlit Cloud deployment).
"""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _get_secret(key: str, default: str = "") -> str:
    """Resolve a secret from env vars → .env → Streamlit secrets."""
    value = os.environ.get(key, "")
    if value:
        return value
    try:
        import streamlit as st
        value = st.secrets.get(key, "")
    except Exception:
        pass
    return value or default


@dataclass(frozen=True)
class Config:
    """Immutable application configuration."""

    # ── API Endpoints ──
    groq_model: str = "llama-3.3-70b-versatile"
    groq_endpoint: str = "https://api.groq.com/openai/v1/chat/completions"
    serper_endpoint: str = "https://google.serper.dev/search"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465

    # ── Behaviour ──
    email_subject: str = "Internship Inquiry - Student Application"
    cooldown_seconds: int = 60
    max_pdf_chars: int = 12_000
    max_companies: int = 20
    min_companies: int = 3
    default_companies: int = 10

    # ── Retry ──
    api_max_retries: int = 3
    api_retry_backoff: float = 1.0
    groq_timeout: int = 45
    serper_timeout: int = 15

    # ── Email Skip Set ──
    skip_email_patterns: frozenset = field(default_factory=lambda: frozenset({
        "noreply", "no-reply", "donotreply", "example", "test",
        "privacy", "legal", "abuse", "webmaster", "admin",
        "press", "media", "news", "cookie", "gdpr", "security",
    }))

    # ── Secrets (resolved at access time) ──
    @property
    def gmail_address(self) -> str:
        return _get_secret("GMAIL_ADDRESS")

    @property
    def gmail_app_password(self) -> str:
        return _get_secret("GMAIL_APP_PASSWORD")

    @property
    def groq_api_key(self) -> str:
        return _get_secret("GROQ_API_KEY")

    @property
    def serper_api_key(self) -> str:
        return _get_secret("SERPER_API_KEY")


cfg = Config()