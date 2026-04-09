"""
AutoPitch — Autonomous Cold-Email Pipeline for University Internship Hunters
Author  : Built with Claude (Anthropic)
Stack   : Streamlit · Groq (LLaMA-3.3-70B) · Serper · Gmail SMTP
Security: BYOK — no keys are persisted anywhere, ever.
"""

import io
import re
import smtplib
import ssl
import time
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pypdf
import requests
import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
EMAIL_SUBJECT   = "Internship Inquiry - Student Application"
GROQ_MODEL      = "llama-3.3-70b-versatile"
GROQ_ENDPOINT   = "https://api.groq.com/openai/v1/chat/completions"
SERPER_ENDPOINT = "https://google.serper.dev/search"
COOLDOWN_SECS   = 60

SKIP_EMAILS = {"noreply", "no-reply", "example", "test", "donotreply",
               "privacy", "legal", "abuse", "webmaster", "admin"}

# ─────────────────────────────────────────────────────────────────────────────
# Page Config & Custom CSS
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AutoPitch",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
/* ── Global ── */
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@400;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Syne', sans-serif;
}
code, .stCode, .stTextArea textarea {
    font-family: 'DM Mono', monospace !important;
}

/* ── Hero header ── */
.ap-hero {
    background: linear-gradient(135deg, #0f0f11 0%, #1a1a2e 50%, #16213e 100%);
    border: 1px solid rgba(99, 179, 237, 0.15);
    border-radius: 16px;
    padding: 2rem 2.5rem;
    margin-bottom: 1.5rem;
    position: relative;
    overflow: hidden;
}
.ap-hero::before {
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 240px; height: 240px;
    background: radial-gradient(circle, rgba(99,179,237,0.12) 0%, transparent 70%);
    border-radius: 50%;
}
.ap-hero h1 {
    font-size: 2.8rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    color: #e2e8f0;
    margin: 0 0 0.25rem 0;
}
.ap-hero h1 span { color: #63b3ed; }
.ap-hero p {
    color: #94a3b8;
    font-size: 1rem;
    margin: 0;
    font-weight: 400;
}

/* ── Stat pills ── */
.pill-row { display: flex; gap: 0.75rem; flex-wrap: wrap; margin-top: 1rem; }
.pill {
    background: rgba(99,179,237,0.1);
    border: 1px solid rgba(99,179,237,0.2);
    color: #63b3ed;
    border-radius: 999px;
    padding: 0.2rem 0.75rem;
    font-size: 0.78rem;
    font-family: 'DM Mono', monospace;
    font-weight: 500;
}

/* ── Section labels ── */
.section-label {
    font-size: 0.7rem;
    font-family: 'DM Mono', monospace;
    font-weight: 500;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #63b3ed;
    margin-bottom: 0.35rem;
}

/* ── Company card ── */
.company-card {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin: 1rem 0;
    border-left: 3px solid #63b3ed;
}
.company-card h3 { margin: 0 0 0.25rem 0; color: #e2e8f0; font-size: 1.1rem; }
.company-card .meta { font-family: 'DM Mono', monospace; font-size: 0.8rem; color: #64748b; }

/* ── Draft box ── */
.draft-box {
    background: #050d1a;
    border: 1px solid #1e3a5f;
    border-radius: 8px;
    padding: 1rem 1.25rem;
    font-family: 'DM Mono', monospace;
    font-size: 0.82rem;
    line-height: 1.65;
    color: #94a3b8;
    white-space: pre-wrap;
    margin-top: 0.5rem;
}

/* ── Status badges ── */
.badge-sent    { color: #4ade80; font-weight: 600; }
.badge-draft   { color: #60a5fa; font-weight: 600; }
.badge-skip    { color: #f59e0b; font-weight: 600; }
.badge-error   { color: #f87171; font-weight: 600; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: #080c14 !important;
    border-right: 1px solid #1e293b;
}

/* ── Buttons ── */
div.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #1d4ed8, #2563eb) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    padding: 0.65rem 1.5rem !important;
    letter-spacing: 0.02em !important;
    transition: all 0.2s ease !important;
}
div.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #1e40af, #1d4ed8) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(37, 99, 235, 0.35) !important;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Core Pipeline Functions
# ─────────────────────────────────────────────────────────────────────────────

def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract and return all text from a PDF file."""
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    pages  = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()


def scrape_email_and_context(company: str, serper_key: str) -> tuple[str | None, str]:
    """
    Query Serper for recruiter email addresses and company context.
    Returns (email_or_None, context_snippet).
    """
    query = f"{company} HR Talent Acquisition global recruiter email contact"
    resp  = requests.post(
        SERPER_ENDPOINT,
        json    = {"q": query, "num": 5},
        headers = {"X-API-KEY": serper_key, "Content-Type": "application/json"},
        timeout = 15,
    )
    resp.raise_for_status()
    data = resp.json()

    pattern     = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
    found_email = None
    context     = ""

    # Primary scan: organic results
    for result in data.get("organic", []):
        snippet = result.get("snippet", "")
        link    = result.get("link", "")

        if not context and snippet:
            context = snippet[:400]

        for candidate in pattern.findall(f"{snippet} {link}"):
            parts = candidate.lower()
            if not any(skip in parts for skip in SKIP_EMAILS):
                found_email = candidate
                break

        if found_email:
            break

    # Fallback: structured SERP features
    if not found_email:
        for key in ("answerBox", "knowledgeGraph"):
            blob    = str(data.get(key, {}))
            matches = pattern.findall(blob)
            if matches:
                found_email = matches[0]
                break

    return found_email, context


def draft_email(cv_text: str, company: str, context: str, groq_key: str) -> str:
    """Call Groq (LLaMA-3.3-70B) to generate a targeted cold email body."""
    fallback_ctx = context or "a fast-growing, innovative technology company."
    prompt = f"""You are a world-class career coach helping a university student land an internship.

COMPANY: {company}
COMPANY CONTEXT (use this for the opening hook): {fallback_ctx}

STUDENT CV:
{cv_text[:3500]}

Write a cold email body under 130 words. Follow ALL rules exactly:
1. FIRST LINE: One punchy, specific hook sentence that references the Company Context.
2. EXACTLY 3 bullet points using the • character. Each bullet is under 20 words. Highlight the student's top 3 measurable or specific achievements pulled directly from the CV.
3. LAST LINE: Ask for a 10-minute exploratory call. Nothing more.

Hard rules:
- NO subject line.
- NO salutation ("Dear…", "Hi…", "Hello…").
- NO sign-off, signature, or closing ("Best regards", "Sincerely", etc.).
- NO filler phrases ("I hope this finds you well", "I am writing to…").
- Be direct, confident, and specific.

Output ONLY the email body text. No preamble, no explanation."""

    resp = requests.post(
        GROQ_ENDPOINT,
        json    = {
            "model"      : GROQ_MODEL,
            "messages"   : [{"role": "user", "content": prompt}],
            "max_tokens" : 380,
            "temperature": 0.72,
        },
        headers = {
            "Authorization": f"Bearer {groq_key}",
            "Content-Type" : "application/json",
        },
        timeout = 35,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def send_email_smtp(
    gmail_addr  : str,
    app_password: str,
    to_email    : str,
    body        : str,
    pdf_bytes   : bytes,
    pdf_filename: str,
    sender_name : str,
) -> None:
    """Send the drafted email via Gmail SMTP with the CV as an attachment."""
    msg            = MIMEMultipart()
    msg["From"]    = f"{sender_name} <{gmail_addr}>"
    msg["To"]      = to_email
    msg["Subject"] = EMAIL_SUBJECT

    full_body = f"{body}\n\nBest regards,\n{sender_name}\n{gmail_addr}"
    msg.attach(MIMEText(full_body, "plain"))

    part = MIMEBase("application", "octet-stream")
    part.set_payload(pdf_bytes)
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{pdf_filename}"')
    msg.attach(part)

    # Strip spaces from App Password (Google shows it grouped as "xxxx xxxx xxxx xxxx")
    clean_password = app_password.replace(" ", "")

    # Explicit SSL context prevents certificate errors on some networks/servers
    ssl_ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl_ctx) as server:
        server.login(gmail_addr, clean_password)
        server.sendmail(gmail_addr, to_email, msg.as_string())


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — Credentials
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<p class="section-label">🔐 Credentials</p>', unsafe_allow_html=True)
    st.caption("Keys live in your browser session only — never logged, stored, or shared.")

    gmail_addr   = st.text_input("Gmail Address", placeholder="you@gmail.com")
    app_password = st.text_input(
        "Gmail App Password",
        type="password",
        placeholder="xxxx xxxx xxxx xxxx",
        help="16-digit app password — NOT your regular Gmail password.",
    )
    groq_key = st.text_input(
        "Groq API Key",
        type="password",
        placeholder="gsk_...",
    )
    serper_key = st.text_input(
        "Serper API Key",
        type="password",
        placeholder="a1b2c3...",
    )

    st.divider()
    st.markdown('<p class="section-label">📚 Get Your Keys</p>', unsafe_allow_html=True)
    st.markdown(
        "- [Gmail App Password ↗](https://myaccount.google.com/apppasswords)\n"
        "- [Groq Console ↗](https://console.groq.com/keys)\n"
        "- [Serper Dashboard ↗](https://serper.dev/api-key)"
    )
    st.divider()
    st.markdown(
        '<p style="font-size:0.72rem;color:#475569;font-family:DM Mono,monospace;">'
        "v1.0 · Free stack · BYOK · No data stored"
        "</p>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Hero Header
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="ap-hero">
  <h1>Auto<span>Pitch</span> 🚀</h1>
  <p>Autonomous cold-email pipeline — built for university students hunting internships.</p>
  <div class="pill-row">
    <span class="pill">LLaMA 3.3 · 70B</span>
    <span class="pill">Gmail SMTP</span>
    <span class="pill">Serper Search</span>
    <span class="pill">BYOK · Zero cost</span>
    <span class="pill">60 s cooldown</span>
  </div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Main Inputs
# ─────────────────────────────────────────────────────────────────────────────
col_left, col_right = st.columns([1.1, 0.9], gap="large")

with col_left:
    st.markdown('<p class="section-label">📄 Your CV</p>', unsafe_allow_html=True)
    cv_file = st.file_uploader(
        "Upload your CV (PDF)",
        type  = ["pdf"],
        label_visibility="collapsed",
        help  = "Attached automatically to every email sent.",
    )

    st.markdown('<p class="section-label" style="margin-top:1.2rem;">🏢 Target Companies</p>', unsafe_allow_html=True)
    companies_raw = st.text_area(
        "Companies",
        placeholder = "Notion, Stripe, Zepto, Razorpay, CRED, Postman, Meesho",
        height      = 110,
        label_visibility="collapsed",
        help="Comma-separated. The pipeline processes each one in order.",
    )

with col_right:
    st.markdown('<p class="section-label">✍️ Your Name</p>', unsafe_allow_html=True)
    sender_name = st.text_input(
        "Name",
        placeholder      = "Aditya Sharma",
        label_visibility = "collapsed",
        help             = "Appears in the email signature.",
    )

    st.markdown('<p class="section-label" style="margin-top:1.2rem;">⚙️ Mode</p>', unsafe_allow_html=True)
    safe_mode = st.toggle(
        "Safe Mode — Actually Send Emails",
        value = False,
        help  = "OFF = draft only (safe to test). ON = real emails are dispatched.",
    )

    if safe_mode:
        st.warning(
            "**Safe Mode ON** — Real emails will be sent. "
            "A mandatory 60-second cooldown is enforced between sends."
        )
    else:
        st.info(
            "**Draft Mode** — The pipeline will generate emails but **not** send them. "
            "Toggle Safe Mode when you're ready to fire."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Launch Button
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
run = st.button("⚡  Start AutoPitch", type="primary", use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline Execution
# ─────────────────────────────────────────────────────────────────────────────
if run:

    # ── Input Validation ──────────────────────────────────────────────────────
    missing = []
    if not gmail_addr:         missing.append("Gmail Address")
    if not app_password:       missing.append("Gmail App Password")
    if not groq_key:           missing.append("Groq API Key")
    if not serper_key:         missing.append("Serper API Key")
    if not cv_file:            missing.append("CV (PDF)")
    if not companies_raw.strip(): missing.append("Target Companies")
    if not sender_name.strip():   missing.append("Your Full Name")

    if missing:
        st.error(f"Please fill in: **{', '.join(missing)}**")
        st.stop()

    companies  = [c.strip() for c in companies_raw.split(",") if c.strip()]
    pdf_bytes  = cv_file.read()
    pdf_name   = cv_file.name

    # ── Parse CV ─────────────────────────────────────────────────────────────
    with st.spinner("Parsing CV…"):
        try:
            cv_text = extract_pdf_text(pdf_bytes)
        except Exception as exc:
            st.error(f"Could not parse the PDF: {exc}")
            st.stop()

    if not cv_text:
        st.error("The PDF appears to be empty or image-only. Please upload a text-layer PDF.")
        st.stop()

    st.success(f"✅ CV parsed — **{len(cv_text):,}** characters extracted from **{cv_file.name}**")

    # ── Summary Tracker ───────────────────────────────────────────────────────
    run_log: list[dict] = []

    # ── Per-Company Loop ──────────────────────────────────────────────────────
    for idx, company in enumerate(companies):

        st.markdown(
            f'<div class="company-card">'
            f'<h3>[ {idx+1} / {len(companies)} ]  {company}</h3>'
            f'<span class="meta">Processing…</span></div>',
            unsafe_allow_html=True,
        )

        status_slot = st.empty()
        log_entry   = {"Company": company, "Email Found": "—", "Status": "—"}

        # ── Step B · Scrape ───────────────────────────────────────────────────
        status_slot.info("🔍  Searching for recruiter contact…")
        scraped_email, context = None, ""

        try:
            scraped_email, context = scrape_email_and_context(company, serper_key)
        except requests.HTTPError as exc:
            status_slot.warning(f"⚠️ Serper request failed ({exc}). Proceeding with draft only.")
        except Exception as exc:
            status_slot.warning(f"⚠️ Scrape error: {exc}. Proceeding with draft only.")

        log_entry["Email Found"] = scraped_email or "Not found"

        if scraped_email:
            st.markdown(f"📧 **Scraped email:** `{scraped_email}`")
        else:
            st.markdown("📭 No email address found in search results — generating draft only.")

        if context:
            with st.expander("🔎 Company context snippet"):
                st.markdown(f"_{context}_")

        # ── Step C · Draft ────────────────────────────────────────────────────
        status_slot.info("✍️  Drafting email with LLaMA 3.3 70B…")

        try:
            draft = draft_email(cv_text, company, context, groq_key)
        except requests.HTTPError as exc:
            status_slot.error(f"❌ Groq API error ({exc.response.status_code}). Skipping.")
            log_entry["Status"] = f"Groq error: {exc.response.status_code}"
            run_log.append(log_entry)
            continue
        except Exception as exc:
            status_slot.error(f"❌ Draft failed: {exc}")
            log_entry["Status"] = f"Draft error: {exc}"
            run_log.append(log_entry)
            continue

        # Show full preview (subject + body + signature)
        preview = (
            f"Subject: {EMAIL_SUBJECT}\n"
            f"{'─'*48}\n\n"
            f"{draft}\n\n"
            f"Best regards,\n{sender_name}\n{gmail_addr}"
        )
        st.markdown('<p class="section-label">📝 Generated Draft</p>', unsafe_allow_html=True)
        st.markdown(f'<div class="draft-box">{preview}</div>', unsafe_allow_html=True)

        # ── Step D · Send ────────────────────────────────────────────────────
        if not safe_mode:
            status_slot.success("✅ Draft ready — Safe Mode is OFF, email not sent.")
            log_entry["Status"] = "Draft only"

        elif not scraped_email:
            status_slot.warning("⚠️ No recipient address found — skipping send.")
            log_entry["Status"] = "Skipped (no email)"

        else:
            status_slot.info(f"📤  Sending to `{scraped_email}`…")
            try:
                send_email_smtp(
                    gmail_addr   = gmail_addr,
                    app_password = app_password,
                    to_email     = scraped_email,
                    body         = draft,
                    pdf_bytes    = pdf_bytes,
                    pdf_filename = pdf_name,
                    sender_name  = sender_name,
                )
                status_slot.success(f"✅ Email sent → `{scraped_email}`")
                log_entry["Status"] = "✅ Sent"

            except smtplib.SMTPAuthenticationError:
                status_slot.error(
                    "❌ Gmail authentication failed. "
                    "Double-check your App Password (not your regular Gmail password). "
                    "Also confirm 2-Step Verification is enabled on your account."
                )
                log_entry["Status"] = "Auth error"

            except smtplib.SMTPRecipientsRefused:
                status_slot.error(f"❌ Recipient `{scraped_email}` was rejected by the server.")
                log_entry["Status"] = "Recipient refused"

            except smtplib.SMTPException as exc:
                status_slot.error(f"❌ SMTP error: {exc}")
                log_entry["Status"] = f"SMTP error: {exc}"

            except Exception as exc:
                status_slot.error(f"❌ Unexpected send error: {exc}")
                log_entry["Status"] = f"Error: {exc}"

        run_log.append(log_entry)

        # ── Step E · Cooldown ────────────────────────────────────────────────
        # Apply whenever Safe Mode is ON and there are more companies to process.
        # This prevents rapid retries even if a send failed, protecting your sender reputation.
        is_last = idx == len(companies) - 1

        if safe_mode and not is_last:
            cooldown_slot = st.empty()
            for secs_left in range(COOLDOWN_SECS, 0, -1):
                cooldown_slot.warning(
                    f"⏳  Anti-spam cooldown — next company in **{secs_left}s** …"
                )
                time.sleep(1)
            cooldown_slot.empty()


    # ─────────────────────────────────────────────────────────────────────────
    # Run Summary
    # ─────────────────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("## 📊 Run Summary")

    import pandas as pd
    df = pd.DataFrame(run_log)
    st.dataframe(df, use_container_width=True, hide_index=True)

    n_sent    = sum(1 for r in run_log if r["Status"] == "✅ Sent")
    n_drafted = sum(1 for r in run_log if r["Status"] == "Draft only")
    n_skip    = sum(1 for r in run_log if "Skipped" in r["Status"])
    n_err     = len(run_log) - n_sent - n_drafted - n_skip

    st.success(
        f"🎉 Pipeline complete! "
        f"**{n_sent}** sent · **{n_drafted}** drafted · "
        f"**{n_skip}** skipped · **{n_err}** errors · "
        f"**{len(run_log)}** companies processed."
    )
