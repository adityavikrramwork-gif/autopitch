"""
AutoPitch v3 — CV Parser
PDF text extraction and AI-powered profile parsing.
"""

import io
import json
import re
from typing import Any

import pypdf

from api import groq_call, GroqAPIError
from config import cfg
from logger import logger


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from a PDF, capped at cfg.max_pdf_chars."""
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages).strip()
    logger.info("Extracted %d chars from %d-page PDF", len(text), len(reader.pages))
    return text[: cfg.max_pdf_chars]


def parse_cv_profile(cv_text: str, groq_key: str) -> dict[str, Any]:
    """Extract structured student profile from raw CV text via Groq LLM."""

    prompt = f"""Extract structured information from this student CV precisely. Use exact text from the CV.

CV TEXT:
{cv_text}

Return ONLY valid JSON with exactly these keys — no extras, no markdown fences:
{{
  "name": "full name as written in CV",
  "college": "full name of college or university",
  "degree": "full degree name e.g. B.Sc. Economics (Hons.)",
  "graduation_year": "expected year of graduation",
  "domain": "primary domain e.g. Finance, Software Engineering, Data Science",
  "key_experiences": [
    "Role at Org — what they did and the result (1 sentence, be specific)",
    "Role at Org — what they did and the result",
    "Role at Org — what they did and the result"
  ],
  "top_skills": ["skill1", "skill2", "skill3", "skill4"],
  "certifications": ["e.g. CFA Level I", "e.g. Bloomberg Market Concepts"],
  "achievements": [
    "Specific achievement with detail e.g. Won Entropia 2024 case competition at national level",
    "Another specific achievement"
  ],
  "target_role": "best internship role for this student e.g. Investment Banking Intern"
}}"""

    try:
        raw = groq_call(prompt, groq_key, max_tokens=700, temperature=0.2)
        return _parse_json_response(raw, _fallback_profile())
    except GroqAPIError:
        logger.error("Groq API error during CV parsing — using fallback profile")
        return _fallback_profile()


def generate_company_list(profile: dict, groq_key: str, num: int = 10) -> list[dict]:
    """AI-generate a list of target companies based on the student profile."""

    prompt = f"""You are a career advisor for Indian university students.

STUDENT PROFILE:
- College: {profile.get('college')}
- Degree: {profile.get('degree')}
- Domain: {profile.get('domain')}
- Experiences: {json.dumps(profile.get('key_experiences', []))}
- Skills: {json.dumps(profile.get('top_skills', []))}
- Target role: {profile.get('target_role')}

Generate exactly {num} companies this student should target for internships.
Include a mix of Indian firms and global firms with India offices.
Prioritize companies that are known to take interns actively in this student's domain.

Return ONLY a valid JSON array — no markdown, no explanation:
[
  {{
    "name": "Company Name",
    "domain": "what the company does in 6 words max",
    "why_fit": "1 specific sentence tying student's actual background to this company",
    "role": "exact internship role title",
    "search_keyword": "2-3 word keyword for finding this company recruiter email"
  }}
]"""

    try:
        raw = groq_call(prompt, groq_key, max_tokens=1400, temperature=0.5)
        result = _parse_json_response(raw, [])
        return result if isinstance(result, list) else []
    except GroqAPIError:
        logger.error("Groq API error during company generation")
        return []


# ── Helpers ──────────────────────────────────────────────────────────────────────

def _parse_json_response(raw: str, fallback: Any) -> Any:
    """Parse a JSON response from Groq, stripping markdown fences if present."""
    cleaned = re.sub(r"```json|```", "", raw).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"[\[{].*[\]}]", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        logger.warning("Failed to parse JSON response — using fallback")
        return fallback


def _fallback_profile() -> dict[str, Any]:
    return {
        "name": "Student",
        "college": "University",
        "degree": "Bachelor's",
        "graduation_year": "2026",
        "domain": "Finance",
        "key_experiences": [],
        "top_skills": [],
        "certifications": [],
        "achievements": [],
        "target_role": "Internship",
    }