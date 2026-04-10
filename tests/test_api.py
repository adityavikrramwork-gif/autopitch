"""
Tests for API module — Groq & Serper clients with retry logic.
"""

import pytest
from unittest.mock import patch, MagicMock

from api import groq_call, serper_query, GroqAPIError, SerperAPIError


# ── groq_call ──────────────────────────────────────────────────────────────────

class TestGroqCall:
    @patch("api.requests.post")
    def test_successful_call(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Hello world"}}]
        }
        mock_post.return_value = mock_resp

        result = groq_call("test prompt", "fake-key")
        assert result == "Hello world"

    @patch("api.requests.post")
    def test_auth_error(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.raise_for_status.side_effect = Exception("401")
        mock_resp.json.return_value = {}
        mock_post.return_value = mock_resp

        # Mock raise_for_status to raise HTTPError
        import requests
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_resp)
        mock_post.return_value = mock_resp

        with pytest.raises(GroqAPIError, match="Invalid Groq API key"):
            groq_call("test", "bad-key")


# ── serper_query ───────────────────────────────────────────────────────────────

class TestSerperQuery:
    @patch("api.requests.post")
    def test_successful_query(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "organic": [{"title": "Test", "snippet": "Result"}]
        }
        mock_post.return_value = mock_resp

        result = serper_query("test query", "fake-key")
        assert "organic" in result

    @patch("api.requests.post")
    def test_timeout_returns_empty(self, mock_post):
        mock_post.side_effect = __import__("requests").exceptions.Timeout()
        # After retries, this should return {}
        result = serper_query("test", "fake-key")
        assert result == {}