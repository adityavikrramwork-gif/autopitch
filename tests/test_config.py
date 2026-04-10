"""
Tests for config module — configuration loading.
"""

import pytest
import os
from config import Config, cfg


class TestConfig:
    def test_default_values(self):
        c = Config()
        assert c.groq_model == "llama-3.3-70b-versatile"
        assert c.smtp_port == 465
        assert c.cooldown_seconds == 60
        assert c.max_pdf_chars == 12_000

    def test_skip_email_patterns_is_frozen(self):
        c = Config()
        assert "noreply" in c.skip_email_patterns
        assert "admin" in c.skip_email_patterns

    def test_global_config_exists(self):
        assert cfg is not None
        assert cfg.groq_model == "llama-3.3-70b-versatile"

    def test_secrets_from_env(self, monkeypatch):
        """Secrets should be read from environment variables."""
        monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
        c = Config()
        assert c.groq_api_key == "test-groq-key"

    def test_secrets_fallback_empty(self, monkeypatch):
        """If no env var or Streamlit secrets, should return empty string."""
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        c = Config()
        assert c.groq_api_key == ""