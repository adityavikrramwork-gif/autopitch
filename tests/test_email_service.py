"""
Tests for email_service module — email drafting and sending.
"""

import pytest
from unittest.mock import patch, MagicMock

from email_service import send_email_smtp, validate_smtp_credentials, draft_personalized_email


class TestSendEmailSmtp:
    @patch("email_service.smtplib.SMTP_SSL")
    def test_successful_send(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        send_email_smtp(
            gmail_addr="test@gmail.com",
            app_password="abcd efgh ijkl mnop",
            to_email="recruiter@company.com",
            body="Hello, I am applying...",
            pdf_bytes=b"%PDF-1.4 fake content",
            pdf_filename="resume.pdf",
            sender_name="Test User",
        )

        mock_server.login.assert_called_once_with("test@gmail.com", "abcdefghijklmnop")
        mock_server.sendmail.assert_called_once()

    @patch("email_service.smtplib.SMTP_SSL")
    def test_strips_spaces_from_app_password(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        send_email_smtp(
            gmail_addr="test@gmail.com",
            app_password="abcd efgh ijkl mnop",
            to_email="hr@company.com",
            body="Test body",
            pdf_bytes=b"fake pdf",
            pdf_filename="cv.pdf",
            sender_name="John Doe",
        )

        # Verify spaces were stripped from app password
        mock_server.login.assert_called_once_with("test@gmail.com", "abcdefghijklmnop")

    @patch("email_service.smtplib.SMTP_SSL")
    def test_sanitizes_sender_name(self, mock_smtp_cls):
        """Verify header injection is prevented."""
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        # This should NOT inject a Bcc header
        send_email_smtp(
            gmail_addr="test@gmail.com",
            app_password="password",
            to_email="hr@company.com",
            body="Test body",
            pdf_bytes=b"fake pdf",
            pdf_filename="cv.pdf",
            sender_name="John\nBcc: evil@hack.com",
        )

        # The From header should have newlines stripped
        call_args = mock_server.sendmail.call_args
        sent_message = call_args[0][2]  # Third arg to sendmail is the message string
        assert "\nBcc:" not in sent_message or "Bcc: evil" not in sent_message


class TestValidateSmtpCredentials:
    @patch("email_service.smtplib.SMTP_SSL")
    def test_valid_credentials(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        ok, msg = validate_smtp_credentials("test@gmail.com", "valid-password")
        assert ok is True

    @patch("email_service.smtplib.SMTP_SSL")
    def test_invalid_credentials(self, mock_smtp_cls):
        import smtplib
        mock_smtp_cls.return_value.__enter__ = MagicMock(
            side_effect=smtplib.SMTPAuthenticationError(535, b"Auth error")
        )
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        ok, msg = validate_smtp_credentials("test@gmail.com", "wrong-password")
        assert ok is False
        assert "App Password" in msg or "auth" in msg.lower()


class TestDraftPersonalizedEmail:
    @patch("email_service.groq_call")
    def test_successful_draft(self, mock_groq):
        mock_groq.return_value = "Dear Company Team,\n\nI am writing..."
        profile = {"name": "Test", "college": "Uni", "degree": "BSc", "domain": "Finance"}
        company = {"name": "TestCorp", "domain": "finance", "why_fit": "good fit", "role": "Intern"}

        result = draft_personalized_email(profile, company, "Alumni", "context", "https://linkedin.com/in/test", "key")
        assert result is not None
        assert "TestCorp" in mock_groq.call_args[0][0]

    @patch("email_service.groq_call")
    def test_api_failure_returns_none(self, mock_groq):
        from api import GroqAPIError
        mock_groq.side_effect = GroqAPIError("API error")

        profile = {"name": "Test"}
        company = {"name": "Corp", "domain": "tech", "why_fit": "fit", "role": "Intern"}

        result = draft_personalized_email(profile, company, "HR", "ctx", "https://linkedin.com/in/t", "key")
        assert result is None