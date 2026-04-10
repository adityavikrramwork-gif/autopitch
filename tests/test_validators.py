"""
Tests for validators module — input validation & sanitization.
"""

import pytest
from validators import (
    is_valid_email,
    sanitize_email,
    sanitize_sender_name,
    sanitize_header,
    validate_linkedin_url,
    validate_pdf_upload,
    validate_num_companies,
)


# ── is_valid_email ──────────────────────────────────────────────────────────────

class TestIsValidEmail:
    def test_valid_email(self):
        assert is_valid_email("john@company.com") is True

    def test_valid_email_with_dots(self):
        assert is_valid_email("first.last@company.co.in") is True

    def test_valid_email_with_plus(self):
        assert is_valid_email("user+tag@domain.org") is True

    def test_invalid_no_at(self):
        assert is_valid_email("nodomain") is False

    def test_invalid_empty(self):
        assert is_valid_email("") is False

    def test_invalid_none(self):
        assert is_valid_email(None) is False

    def test_skip_pattern_noreply(self):
        assert is_valid_email("noreply@company.com") is False

    def test_skip_pattern_privacy(self):
        assert is_valid_email("privacy@company.com") is False

    def test_skip_pattern_admin(self):
        assert is_valid_email("admin@company.com") is False

    def test_skip_pattern_case_insensitive(self):
        assert is_valid_email("NoReply@Company.COM") is False


# ── sanitize_email ─────────────────────────────────────────────────────────────

class TestSanitizeEmail:
    def test_strips_whitespace(self):
        assert sanitize_email("  user@example.com  ") == "user@example.com"

    def test_removes_newlines(self):
        assert sanitize_email("user\n@example.com") == "user@example.com"

    def test_removes_carriage_returns(self):
        assert sanitize_email("user\r@example.com") == "user@example.com"

    def test_empty_string(self):
        assert sanitize_email("") == ""

    def test_none_returns_empty(self):
        assert sanitize_email(None) == ""


# ── sanitize_sender_name ──────────────────────────────────────────────────────

class TestSanitizeSenderName:
    def test_normal_name(self):
        assert sanitize_sender_name("Adityavikrram Sinha") == "Adityavikrram Sinha"

    def test_removes_newlines(self):
        assert sanitize_sender_name("John\nDoe") == "JohnDoe"

    def test_removes_control_chars(self):
        assert sanitize_sender_name("Name\x00With\x01Control") == "NameWithControl"

    def test_truncates_long_name(self):
        long_name = "A" * 200
        assert len(sanitize_sender_name(long_name)) == 120

    def test_empty_string(self):
        assert sanitize_sender_name("") == ""


# ── sanitize_header ─────────────────────────────────────────────────────────────

class TestSanitizeHeader:
    def test_normal_value(self):
        assert sanitize_header("Internship Inquiry") == "Internship Inquiry"

    def test_removes_crlf(self):
        assert sanitize_header("Subject\r\nBcc: evil@hack.com") == "SubjectBcc: evil@hack.com"

    def test_empty(self):
        assert sanitize_header("") == ""


# ── validate_linkedin_url ──────────────────────────────────────────────────────

class TestValidateLinkedinUrl:
    def test_valid_url(self):
        ok, url = validate_linkedin_url("https://www.linkedin.com/in/johndoe/")
        assert ok is True
        assert "linkedin.com/in/johndoe" in url

    def test_valid_url_without_www(self):
        ok, url = validate_linkedin_url("https://linkedin.com/in/janedoe")
        assert ok is True

    def test_adds_https(self):
        ok, url = validate_linkedin_url("www.linkedin.com/in/test-user/")
        assert ok is True
        assert url.startswith("https://")

    def test_invalid_url(self):
        ok, msg = validate_linkedin_url("https://facebook.com/profile")
        assert ok is False

    def test_empty_url(self):
        ok, msg = validate_linkedin_url("")
        assert ok is False


# ── validate_pdf_upload ────────────────────────────────────────────────────────

class TestValidatePdfUpload:
    def test_valid_pdf(self):
        ok, msg = validate_pdf_upload("resume.pdf", 1000)
        assert ok is True

    def test_non_pdf_file(self):
        ok, msg = validate_pdf_upload("resume.docx", 1000)
        assert ok is False
        assert ".docx" in msg

    def test_oversized_file(self):
        # 15 MB file
        ok, msg = validate_pdf_upload("big.pdf", 15 * 1024 * 1024)
        assert ok is False
        assert "too large" in msg.lower()

    def test_empty_filename(self):
        ok, msg = validate_pdf_upload("", 100)
        assert ok is False


# ── validate_num_companies ──────────────────────────────────────────────────────

class TestValidateNumCompanies:
    def test_valid_number(self):
        ok, msg = validate_num_companies(10)
        assert ok is True

    def test_too_low(self):
        ok, msg = validate_num_companies(0)
        assert ok is False

    def test_too_high(self):
        ok, msg = validate_num_companies(50)
        assert ok is False