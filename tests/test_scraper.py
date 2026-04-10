"""
Tests for scraper module — email extraction and discovery.
"""

import pytest
from unittest.mock import patch, MagicMock

from scraper import pull_emails_from_data, pull_context, scrape_recruiter_email


class TestPullEmailsFromData:
    def test_extracts_valid_emails(self):
        data = {
            "organic": [
                {"snippet": "Contact john@goldman.com for internships", "link": ""}
            ]
        }
        result = pull_emails_from_data(data)
        assert "john@goldman.com" in result

    def test_excludes_noreply(self):
        data = {
            "organic": [
                {"snippet": "Email noreply@company.com", "link": ""}
            ]
        }
        result = pull_emails_from_data(data)
        assert len(result) == 0

    def test_deduplicates(self):
        data = {
            "organic": [
                {"snippet": "Reach jane@bank.com", "link": ""},
                {"snippet": "Also jane@bank.com here", "link": ""},
            ]
        }
        result = pull_emails_from_data(data)
        assert result.count("jane@bank.com") == 1

    def test_empty_data(self):
        assert pull_emails_from_data({}) == []

    def test_extracts_from_answer_box(self):
        data = {
            "organic": [],
            "answerBox": "Contact hr@firm.com for details"
        }
        result = pull_emails_from_data(data)
        assert "hr@firm.com" in result


class TestPullContext:
    def test_returns_snippet(self):
        data = {"organic": [{"snippet": "Goldman Sachs offers summer internships"}]}
        assert "Goldman Sachs" in pull_context(data)

    def test_empty_data(self):
        assert pull_context({}) == ""

    def test_truncates_long_snippet(self):
        data = {"organic": [{"snippet": "A" * 600}]}
        assert len(pull_context(data)) <= 500


class TestScrapeRecruiterEmail:
    @patch("scraper.serper_query")
    def test_finds_alumni_email(self, mock_query):
        mock_query.return_value = {
            "organic": [{"snippet": "Alumni john@goldman.com hiring", "link": ""}],
        }
        email, target, ctx = scrape_recruiter_email(
            "Goldman Sachs", "IIT Delhi", "investment banking", "fake-key"
        )
        assert email == "john@goldman.com"
        assert target == "Alumni"

    @patch("scraper.serper_query")
    def test_no_email_found(self, mock_query):
        mock_query.return_value = {"organic": [{"snippet": "No emails here", "link": ""}]}
        email, target, ctx = scrape_recruiter_email(
            "Unknown Corp", "Some College", "tech", "fake-key"
        )
        assert email is None
        assert target is None