"""
Tests for cv_parser module — PDF extraction and profile parsing.
"""

import pytest
from unittest.mock import patch, MagicMock

from cv_parser import extract_pdf_text, parse_cv_profile, generate_company_list, _parse_json_response


class TestExtractPdfText:
    @patch("cv_parser.pypdf.PdfReader")
    def test_extracts_text_from_pdf(self, mock_reader_cls):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "John Doe — Resume"
        mock_reader_cls.return_value.pages = [mock_page]

        result = extract_pdf_text(b"fake-pdf-bytes")
        assert "John Doe" in result

    @patch("cv_parser.pypdf.PdfReader")
    def test_handles_empty_pages(self, mock_reader_cls):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = None
        mock_reader_cls.return_value.pages = [mock_page]

        result = extract_pdf_text(b"fake-pdf-bytes")
        assert result == ""

    @patch("cv_parser.pypdf.PdfReader")
    def test_truncates_long_text(self, mock_reader_cls):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "A" * 20000
        mock_reader_cls.return_value.pages = [mock_page]

        result = extract_pdf_text(b"fake-pdf-bytes")
        assert len(result) <= 12000


class TestParseJsonResponse:
    def test_clean_json(self):
        result = _parse_json_response('{"name": "Test"}', {})
        assert result == {"name": "Test"}

    def test_json_with_fences(self):
        result = _parse_json_response('```json\n{"name": "Test"}\n```', {})
        assert result == {"name": "Test"}

    def test_json_with_backticks_only(self):
        result = _parse_json_response('```\n{"name": "Test"}\n```', {})
        assert result == {"name": "Test"}

    def test_invalid_json_returns_fallback(self):
        result = _parse_json_response("not json at all", {"fallback": True})
        assert result == {"fallback": True}

    def test_embedded_json_object(self):
        result = _parse_json_response('Here is the result: {"name": "Test"}', {})
        assert result == {"name": "Test"}

    def test_embedded_json_array(self):
        result = _parse_json_response('Result: [{"name": "A"}, {"name": "B"}]', [])
        assert len(result) == 2


class TestParseCvProfile:
    @patch("cv_parser.groq_call")
    def test_successful_parse(self, mock_groq):
        mock_groq.return_value = '{"name": "John", "college": "MIT", "degree": "BSc", "graduation_year": "2026", "domain": "Finance", "key_experiences": [], "top_skills": [], "certifications": [], "achievements": [], "target_role": "Intern"}'

        result = parse_cv_profile("fake cv text", "fake-key")
        assert result["name"] == "John"
        assert result["college"] == "MIT"

    @patch("cv_parser.groq_call")
    def test_api_error_returns_fallback(self, mock_groq):
        from api import GroqAPIError
        mock_groq.side_effect = GroqAPIError("API error")

        result = parse_cv_profile("fake cv text", "bad-key")
        assert result["name"] == "Student"  # fallback profile


class TestGenerateCompanyList:
    @patch("cv_parser.groq_call")
    def test_successful_generation(self, mock_groq):
        mock_groq.return_value = '[{"name": "Goldman Sachs", "domain": "investment banking", "why_fit": "good fit", "role": "Intern", "search_keyword": "Goldman Sachs HR"}]'

        result = generate_company_list({"college": "MIT", "domain": "Finance"}, "key", num=1)
        assert len(result) == 1
        assert result[0]["name"] == "Goldman Sachs"

    @patch("cv_parser.groq_call")
    def test_api_error_returns_empty(self, mock_groq):
        from api import GroqAPIError
        mock_groq.side_effect = GroqAPIError("API error")

        result = generate_company_list({"college": "MIT"}, "bad-key")
        assert result == []