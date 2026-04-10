"""
AutoPitch v3 — Email Service
Drafting personalized emails and sending via Gmail SMTP.
"""

import smtplib
import ssl
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from api import groq_call, GroqAPIError
from config import cfg
from logger import logger
from validators import sanitize_email, sanitize_header, sanitize_sender_name


def draft_personalized_email(
    profile: dict,
    company: dict,
    target_type: Optional[str],
    context: str,
    linkedin_url: str,
    groq_key: str,
) -> Optional[str]:
    """Generate a personalized internship outreach email via Groq LLM."""

    company_name = company["name"]
    company_domain = company.get("domain", "")
    why_fit = company.get("why_fit", "")
    role = company.get("role", "internship")
    context_text = context or company_domain

    experiences = "\n".join(f"- {e}" for e in profile.get("key_experiences", []))
    achievements = "\n".join(f"- {a}" for a in profile.get("achievements", []))
    certs = ", ".join(profile.get("certifications", [])) or "None listed"
    skills = ", ".join(profile.get("top_skills", [])) or "See CV"
    name = profile.get("name", "Student")

    prompt = f"""You are writing a cold internship outreach email for a university student.

STUDENT DETAILS:
Name: {name}
Degree: {profile.get('degree')}
College: {profile.get('college')}
Domain: {profile.get('domain')}
Certifications: {certs}
Skills: {skills}
Key Experiences:
{experiences}
Achievements:
{achievements}
Target role: {role}

TARGET COMPANY: {company_name}
What they do: {company_domain}
Why this student fits: {why_fit}
Company context (from web): {context_text}
Who is being contacted: {target_type or "the team"}

WRITE THE EMAIL EXACTLY IN THIS STRUCTURE:

Dear {company_name} Team,

[Paragraph 1 — Introduction: "I am {name}, a {profile.get('degree')} student at {profile.get('college')}, seeking opportunities to build on my experience in [specific area most relevant to {company_name}]." Keep to 1-2 sentences. Do NOT say "I hope this email finds you well" or any filler.]

[Paragraph 2 — Current focus: Mention 1 certification or current project in 1 sentence. e.g. "I am currently preparing for the CFA Level 1 exam (August 2026 attempt), which is strengthening my understanding of [relevant area]."]

[Paragraph 3 — Most relevant experience: Describe the most relevant experience to {company_name} in 1-2 sentences. Name the organization, what the student did, and what impact it had. Be specific.]

[Paragraph 4 — Second supporting experience or achievement: Pick the experience or achievement from the list MOST relevant to {company_name}'s domain ({company_domain}). 1-2 sentences. Be specific.]

[Paragraph 5 (optional) — One more supporting point if strong, else skip: A job simulation, additional role, or key skill. 1 sentence only.]

[Closing — Company-specific hook + ask: "Given [mention something specific about {company_name} — their deal pipeline / product / growth / focus area from the context], I am genuinely keen to contribute to your team. Please find my CV attached for your reference." 2 sentences.]

Thank you for your time and consideration.

Best regards,
{name}
{linkedin_url}

STRICT RULES:
- Pure flowing paragraphs only. ZERO bullet points.
- Mention {company_name} by name at least once in the body.
- Every email must feel written specifically for {company_name}, not copy-pasted.
- Total word count: 160–230 words.
- Formal but warm tone.
- Output ONLY the email text. No subject line. No extra explanation."""

    try:
        return groq_call(prompt, groq_key, max_tokens=520, temperature=0.72)
    except GroqAPIError:
        logger.error("Groq API error drafting email for %s", company_name)
        return None


def send_email_smtp(
    gmail_addr: str,
    app_password: str,
    to_email: str,
    body: str,
    pdf_bytes: bytes,
    pdf_filename: str,
    sender_name: str,
) -> None:
    """Send an email via Gmail SMTP with PDF attachment. Raises on failure."""

    # ── Sanitize all header values to prevent injection ──
    safe_from_name = sanitize_sender_name(sender_name)
    safe_from = sanitize_email(gmail_addr)
    safe_to = sanitize_email(to_email)
    safe_subject = sanitize_header(cfg.email_subject)
    safe_filename = sanitize_header(pdf_filename)

    msg = MIMEMultipart()
    msg["From"] = f"{safe_from_name} <{safe_from}>"
    msg["To"] = safe_to
    msg["Subject"] = safe_subject
    msg.attach(MIMEText(body, "plain"))

    # PDF attachment
    part = MIMEBase("application", "octet-stream")
    part.set_payload(pdf_bytes)
    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition", f'attachment; filename="{safe_filename}"'
    )
    msg.attach(part)

    # Send via SMTP_SSL
    ssl_ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, context=ssl_ctx) as server:
        server.login(safe_from, app_password.replace(" ", ""))
        server.sendmail(safe_from, safe_to, msg.as_string())

    logger.info("Email sent successfully to %s", safe_to)


def validate_smtp_credentials(gmail_addr: str, app_password: str) -> tuple[bool, str]:
    """Test Gmail SMTP credentials without sending an email. Returns (success, message)."""
    try:
        ssl_ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, context=ssl_ctx) as server:
            server.login(gmail_addr, app_password.replace(" ", ""))
        return True, "Gmail authentication successful."
    except smtplib.SMTPAuthenticationError:
        return False, (
            "Gmail auth failed. Your App Password is wrong — "
            "it is NOT your normal Gmail password. "
            "Go to myaccount.google.com/apppasswords to generate one."
        )
    except Exception as exc:
        logger.error("SMTP credential check failed: %s", exc)
        return False, f"Could not connect to Gmail SMTP: {exc}"