"""
AutoPitch v3 — Email Scraper
4-pass email discovery with priority: Alumni → VP → HR → General → Domain fallback.
"""

import re
from typing import Optional

from api import serper_query, SerperAPIError
from config import cfg
from logger import logger
from validators import is_valid_email


def pull_emails_from_data(data: dict) -> list[str]:
    """Extract all valid emails from a Serper search response."""
    pattern = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
    found: list[str] = []

    for result in data.get("organic", []):
        text = result.get("snippet", "") + " " + result.get("link", "")
        for email in pattern.findall(text):
            if is_valid_email(email) and email not in found:
                found.append(email)

    for key in ("answerBox", "knowledgeGraph", "peopleAlsoAsk"):
        for email in pattern.findall(str(data.get(key, ""))):
            if is_valid_email(email) and email not in found:
                found.append(email)

    return found


def pull_context(data: dict) -> str:
    """Get the first useful snippet from Serper results."""
    for result in data.get("organic", []):
        snippet = result.get("snippet", "")
        if snippet:
            return snippet[:500]
    return ""


def scrape_recruiter_email(
    company: str,
    college: str,
    search_keyword: str,
    serper_key: str,
) -> tuple[Optional[str], Optional[str], str]:
    """
    4-pass email hunt in priority order:
      1. Alumni from student's college at this company
      2. VP / Director / Manager / Partner
      3. HR / Talent Acquisition / Recruiting
      4. General internship / careers
      5. Domain-guess fallback

    Returns (email_or_None, target_type_or_None, context_snippet).
    """
    best_context = ""

    passes = [
        (
            f'"{company}" "{college}" alumni email contact hiring internship',
            "Alumni",
        ),
        (
            f'"{company}" "Vice President" OR "Director" OR "Manager" OR "Partner" email hiring internship contact',
            "VP / Director / Manager",
        ),
        (
            f'"{company}" "talent acquisition" OR "HR" OR "recruiter" internship email contact',
            "HR / Talent Acquisition",
        ),
        (
            f"{company} internship application careers email {search_keyword}",
            "General / Careers",
        ),
    ]

    for query, target_type in passes:
        try:
            data = serper_query(query, serper_key, num=5)
        except SerperAPIError:
            logger.warning("Serper query failed for pass: %s", target_type)
            continue

        if not best_context:
            best_context = pull_context(data)

        emails = pull_emails_from_data(data)
        if emails:
            logger.info(
                "Found email for %s via %s pass: %s",
                company, target_type, emails[0],
            )
            return emails[0], target_type, best_context

    # Domain-guess fallback
    domain_guess = company.lower().replace(" ", "").replace(".", "") + ".com"
    try:
        fallback_data = serper_query(
            f"site:{domain_guess} internship email OR careers OR jobs",
            serper_key, num=5,
        )
    except SerperAPIError:
        fallback_data = {}

    if not best_context:
        best_context = pull_context(fallback_data)

    emails = pull_emails_from_data(fallback_data)
    if emails:
        logger.info("Found email for %s via domain fallback: %s", company, emails[0])
        return emails[0], "Company Website", best_context

    logger.info("No email found for %s after all passes", company)
    return None, None, best_context