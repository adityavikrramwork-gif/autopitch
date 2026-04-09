"""
AutoPitch v3 — CV-Driven, Hyper-Personalized Internship Outreach
─────────────────────────────────────────────────────────────────
What's new in v3:
  • CV is parsed to extract your full profile automatically
  • AI auto-generates a company target list from your CV
  • Emails are written in proper professional prose — NOT bullet points
  • Targets in priority order: Alumni → VPs/Directors/Managers → HR
  • 4-pass email scraping per company (much harder to miss)
  • LinkedIn URL in signature instead of Gmail address
  • Editable company list before you fire
"""

import io
import json
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

SKIP_EMAILS = {
    "noreply", "no-reply", "donotreply", "example", "test",
    "privacy", "legal", "abuse", "webmaster", "admin",
    "press", "media", "news", "cookie", "gdpr", "security",
}

# ─────────────────────────────────────────────────────────────────────────────
# Page Config & CSS
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AutoPitch v3",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@400;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Syne', sans-serif; }
code, .stCode, textarea    { font-family: 'DM Mono', monospace !important; }

.ap-hero {
    background: linear-gradient(135deg, #0f0f11 0%, #1a1a2e 50%, #16213e 100%);
    border: 1px solid rgba(99,179,237,0.15);
    border-radius: 16px; padding: 2rem 2.5rem;
    margin-bottom: 1.5rem; position: relative; overflow: hidden;
}
.ap-hero::before {
    content: ''; position: absolute; top: -60px; right: -60px;
    width: 240px; height: 240px;
    background: radial-gradient(circle, rgba(99,179,237,0.12) 0%, transparent 70%);
    border-radius: 50%;
}
.ap-hero h1 {
    font-size:2.8rem; font-weight:800; letter-spacing:-0.03em;
    color:#e2e8f0; margin:0 0 0.25rem 0;
}
.ap-hero h1 span { color: #63b3ed; }
.ap-hero p  { color:#94a3b8; font-size:1rem; margin:0; }
.pill-row   { display:flex; gap:0.75rem; flex-wrap:wrap; margin-top:1rem; }
.pill {
    background: rgba(99,179,237,0.1); border: 1px solid rgba(99,179,237,0.2);
    color: #63b3ed; border-radius:999px; padding: 0.2rem 0.75rem;
    font-size:0.78rem; font-family:'DM Mono',monospace; font-weight:500;
}
.step-badge {
    display:inline-block; background: rgba(99,179,237,0.12);
    border: 1px solid rgba(99,179,237,0.25); color: #93c5fd;
    border-radius: 8px; padding: 0.2rem 0.7rem;
    font-size: 0.72rem; font-family: 'DM Mono', monospace;
    font-weight: 600; margin-bottom: 0.75rem; letter-spacing:0.05em;
    text-transform: uppercase;
}
.section-label {
    font-size:0.7rem; font-family:'DM Mono',monospace; font-weight:500;
    letter-spacing:0.12em; text-transform:uppercase;
    color:#63b3ed; margin-bottom:0.35rem;
}
.profile-card {
    background: #0a1628; border: 1px solid #1e3a5f; border-radius: 12px;
    padding: 1.25rem 1.5rem; font-size: 0.88rem; color: #94a3b8; line-height: 1.75;
}
.profile-card strong { color: #e2e8f0; }
.company-card {
    background:#0f172a; border:1px solid #1e293b; border-radius:12px;
    padding:1.25rem 1.5rem; margin:1rem 0; border-left:3px solid #63b3ed;
}
.company-card h3 { margin:0 0 0.25rem 0; color:#e2e8f0; font-size:1.1rem; }
.company-card .meta { font-family:'DM Mono',monospace; font-size:0.8rem; color:#64748b; }
.draft-box {
    background:#050d1a; border:1px solid #1e3a5f; border-radius:8px;
    padding:1.25rem 1.5rem; font-family:'Syne',sans-serif;
    font-size:0.88rem; line-height:1.8; color:#cbd5e1;
    white-space:pre-wrap; margin-top:0.5rem;
}
section[data-testid="stSidebar"] {
    background: #080c14 !important; border-right: 1px solid #1e293b;
}
div.stButton > button[kind="primary"] {
    background: linear-gradient(135deg,#1d4ed8,#2563eb) !important;
    color:white !important; border:none !important; border-radius:10px !important;
    font-family:'Syne',sans-serif !important; font-weight:700 !important;
    font-size:1rem !important; padding:0.65rem 1.5rem !important;
    letter-spacing:0.02em !important; transition: all 0.2s ease !important;
}
div.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg,#1e40af,#1d4ed8) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(37,99,235,0.35) !important;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Core Helpers
# ─────────────────────────────────────────────────────────────────────────────

def groq_call(prompt: str, groq_key: str, max_tokens: int = 900, temperature: float = 0.65) -> str:
    """Reusable Groq API call. Raises on error."""
    resp = requests.post(
        GROQ_ENDPOINT,
        json={
            "model"      : GROQ_MODEL,
            "messages"   : [{"role": "user", "content": prompt}],
            "max_tokens" : max_tokens,
            "temperature": temperature,
        },
        headers={
            "Authorization": f"Bearer {groq_key}",
            "Content-Type" : "application/json",
        },
        timeout=45,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    pages  = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()[:12000]


def parse_cv_profile(cv_text: str, groq_key: str) -> dict:
    """Extract structured student profile from raw CV text."""
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

    raw = groq_call(prompt, groq_key, max_tokens=700, temperature=0.2)
    raw = re.sub(r"```json|```", "", raw).strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        return {
            "name": "Student", "college": "University",
            "degree": "Bachelor's", "graduation_year": "2026",
            "domain": "Finance", "key_experiences": [],
            "top_skills": [], "certifications": [],
            "achievements": [], "target_role": "Internship",
        }


def generate_company_list(profile: dict, groq_key: str, num: int = 10) -> list:
    """AI generates a list of target companies based on the student's CV profile."""
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

    raw = groq_call(prompt, groq_key, max_tokens=1400, temperature=0.5)
    raw = re.sub(r"```json|```", "", raw).strip()

    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        return []


# ─────────────────────────────────────────────────────────────────────────────
# 4-Pass Email Scraping
# ─────────────────────────────────────────────────────────────────────────────

def is_valid_email(email: str) -> bool:
    lower = email.lower()
    if any(skip in lower for skip in SKIP_EMAILS):
        return False
    if not re.match(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", email):
        return False
    return True


def serper_query(query: str, serper_key: str, num: int = 5) -> dict:
    try:
        resp = requests.post(
            SERPER_ENDPOINT,
            json={"q": query, "num": num},
            headers={"X-API-KEY": serper_key, "Content-Type": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


def pull_emails_from_data(data: dict) -> list:
    """Extract all valid emails from a Serper response object."""
    pattern = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
    found   = []
    for result in data.get("organic", []):
        text = result.get("snippet", "") + " " + result.get("link", "")
        for e in pattern.findall(text):
            if is_valid_email(e) and e not in found:
                found.append(e)
    for key in ("answerBox", "knowledgeGraph", "peopleAlsoAsk"):
        for e in pattern.findall(str(data.get(key, ""))):
            if is_valid_email(e) and e not in found:
                found.append(e)
    return found


def pull_context(data: dict) -> str:
    """Get the first useful snippet from Serper results."""
    for result in data.get("organic", []):
        s = result.get("snippet", "")
        if s:
            return s[:500]
    return ""


def scrape_recruiter_email(
    company       : str,
    college       : str,
    search_keyword: str,
    serper_key    : str,
) -> tuple:
    """
    4-pass email hunt, in priority order:
      Pass 1 — Alumni from student's college at this company (warmest lead)
      Pass 2 — VP / Director / Manager / Partner at this company
      Pass 3 — HR / Talent Acquisition / Recruiting team
      Pass 4 — General internship / careers contact

    Returns (email_or_None, target_type_or_None, context_snippet)
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
            f'{company} internship application careers email {search_keyword}',
            "General / Careers",
        ),
    ]

    for query, target_type in passes:
        data = serper_query(query, serper_key, num=5)

        if not best_context:
            best_context = pull_context(data)

        emails = pull_emails_from_data(data)
        if emails:
            return emails[0], target_type, best_context

    # Final fallback: try the company's own domain directly
    domain_guess = company.lower().replace(" ", "").replace(".", "") + ".com"
    fallback_data = serper_query(
        f'site:{domain_guess} internship email OR "careers" OR "jobs"',
        serper_key, num=5,
    )
    if not best_context:
        best_context = pull_context(fallback_data)
    emails = pull_emails_from_data(fallback_data)
    if emails:
        return emails[0], "Company Website", best_context

    return None, None, best_context


# ─────────────────────────────────────────────────────────────────────────────
# Hyper-Personalized Email Drafting (Prose Format)
# ─────────────────────────────────────────────────────────────────────────────

def draft_personalized_email(
    profile      : dict,
    company      : dict,
    target_type  : str,
    context      : str,
    linkedin_url : str,
    groq_key     : str,
) -> str:
    """
    Writes a proper professional email — flowing paragraphs, no bullet points.
    Each email highlights different experiences based on what THIS company values.
    """
    company_name   = company["name"]
    company_domain = company.get("domain", "")
    why_fit        = company.get("why_fit", "")
    role           = company.get("role", "internship")
    context_text   = context or company_domain

    experiences = "\n".join(f"- {e}" for e in profile.get("key_experiences", []))
    achievements = "\n".join(f"- {a}" for a in profile.get("achievements", []))
    certs        = ", ".join(profile.get("certifications", [])) or "None listed"
    skills       = ", ".join(profile.get("top_skills", [])) or "See CV"

    prompt = f"""You are writing a cold internship outreach email for a university student.

STUDENT DETAILS:
Name: {profile.get('name')}
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

[Paragraph 1 — Introduction: "I am [name], a [degree] student at [college], seeking opportunities to build on my experience in [specific area most relevant to {company_name}]." Keep to 1-2 sentences. Do NOT say "I hope this email finds you well" or any filler.]

[Paragraph 2 — Current focus: Mention 1 certification or current project in 1 sentence. e.g. "I am currently preparing for the CFA Level 1 exam (August 2026 attempt), which is strengthening my understanding of [relevant area]."]

[Paragraph 3 — Most relevant experience: Describe the most relevant experience to {company_name} in 1-2 sentences. Name the organization, what the student did, and what impact it had. Be specific.]

[Paragraph 4 — Second supporting experience or achievement: Pick the experience or achievement from the list MOST relevant to {company_name}'s domain ({company_domain}). 1-2 sentences. Be specific.]

[Paragraph 5 (optional) — One more supporting point if strong, else skip: A job simulation, additional role, or key skill. 1 sentence only.]

[Closing — Company-specific hook + ask: "Given [mention something specific about {company_name} — their deal pipeline / product / growth / focus area from the context], I am genuinely keen to contribute to your team. Please find my CV attached for your reference." 2 sentences.]

Thank you for your time and consideration.

Best regards,
{profile.get('name')}
{linkedin_url}

STRICT RULES:
- Pure flowing paragraphs only. ZERO bullet points.
- Mention {company_name} by name at least once in the body.
- Every email must feel written specifically for {company_name}, not copy-pasted.
- Total word count: 160–230 words.
- Formal but warm tone.
- Output ONLY the email text. No subject line. No extra explanation."""

    return groq_call(prompt, groq_key, max_tokens=520, temperature=0.72)


# ─────────────────────────────────────────────────────────────────────────────
# Gmail SMTP Send
# ─────────────────────────────────────────────────────────────────────────────

def send_email_smtp(
    gmail_addr  : str,
    app_password: str,
    to_email    : str,
    body        : str,
    pdf_bytes   : bytes,
    pdf_filename: str,
    sender_name : str,
) -> None:
    msg            = MIMEMultipart()
    msg["From"]    = f"{sender_name} <{gmail_addr}>"
    msg["To"]      = to_email
    msg["Subject"] = EMAIL_SUBJECT
    msg.attach(MIMEText(body, "plain"))

    part = MIMEBase("application", "octet-stream")
    part.set_payload(pdf_bytes)
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{pdf_filename}"')
    msg.attach(part)

    ssl_ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl_ctx) as server:
        server.login(gmail_addr, app_password.replace(" ", ""))
        server.sendmail(gmail_addr, to_email, msg.as_string())


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<p class="section-label">🔐 Credentials</p>', unsafe_allow_html=True)
    st.caption("Keys live in your browser session only — never stored.")

    gmail_addr   = st.text_input("Gmail Address",      placeholder="you@gmail.com")
    app_password = st.text_input("Gmail App Password", type="password", placeholder="xxxx xxxx xxxx xxxx")
    groq_key     = st.text_input("Groq API Key",       type="password", placeholder="gsk_...")
    serper_key   = st.text_input("Serper API Key",     type="password", placeholder="a1b2c3...")

    st.divider()
    st.markdown('<p class="section-label">📚 Get Free Keys</p>', unsafe_allow_html=True)
    st.markdown(
        "- [Gmail App Password ↗](https://myaccount.google.com/apppasswords)\n"
        "- [Groq Console ↗](https://console.groq.com/keys)\n"
        "- [Serper Dashboard ↗](https://serper.dev/api-key)"
    )
    st.divider()
    st.markdown(
        '<p style="font-size:0.72rem;color:#475569;font-family:DM Mono,monospace;">'
        "v3.0 · Prose emails · 4-pass scraping · BYOK"
        "</p>", unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Hero
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="ap-hero">
  <h1>Auto<span>Pitch</span> v3 🚀</h1>
  <p>Upload CV → AI reads it → builds your target list → writes a unique email per company.</p>
  <div class="pill-row">
    <span class="pill">CV-driven targeting</span>
    <span class="pill">Prose emails — no templates</span>
    <span class="pill">Alumni → VP → HR priority</span>
    <span class="pill">4-pass email hunting</span>
    <span class="pill">LLaMA 3.3 · 70B</span>
  </div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Inputs
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="step-badge">Step 1 — Your Details</div>', unsafe_allow_html=True)

col_l, col_r = st.columns([1.1, 0.9], gap="large")

with col_l:
    st.markdown('<p class="section-label">📄 Your CV (PDF)</p>', unsafe_allow_html=True)
    cv_file = st.file_uploader("CV", type=["pdf"], label_visibility="collapsed")

    st.markdown('<p class="section-label" style="margin-top:1rem;">🔗 LinkedIn URL</p>', unsafe_allow_html=True)
    linkedin_url = st.text_input(
        "LinkedIn",
        placeholder="https://www.linkedin.com/in/yourname/",
        label_visibility="collapsed",
        help="Goes in the signature of every email instead of your Gmail address.",
    )

with col_r:
    st.markdown('<p class="section-label">✍️ Your Full Name</p>', unsafe_allow_html=True)
    sender_name = st.text_input(
        "Name", placeholder="Adityavikrram Sinha",
        label_visibility="collapsed",
    )

    st.markdown('<p class="section-label" style="margin-top:1rem;">🏢 How many companies?</p>', unsafe_allow_html=True)
    num_companies = st.slider(
        "Companies", min_value=3, max_value=20, value=10,
        label_visibility="collapsed",
    )

    st.markdown('<p class="section-label" style="margin-top:1rem;">⚙️ Mode</p>', unsafe_allow_html=True)
    safe_mode = st.toggle(
        "Safe Mode — Actually Send Emails", value=False,
        help="OFF = preview only. ON = real emails go out with 60s cooldown.",
    )
    if safe_mode:
        st.warning("**Safe Mode ON** — Real emails will be sent.")
    else:
        st.info("**Draft Mode** — Emails generated but NOT sent.")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Analyse CV
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown('<div class="step-badge">Step 2 — AI Reads CV &amp; Builds Target List</div>', unsafe_allow_html=True)

analyse_btn = st.button(
    "🔍  Analyse CV & Generate Company List",
    type="primary",
    use_container_width=True,
)

if analyse_btn:
    missing = []
    if not cv_file:      missing.append("CV (PDF)")
    if not sender_name:  missing.append("Your Full Name")
    if not linkedin_url: missing.append("LinkedIn URL")
    if not groq_key:     missing.append("Groq API Key")
    if missing:
        st.error(f"Please fill in: **{', '.join(missing)}**")
        st.stop()

    pdf_bytes = cv_file.read()

    with st.spinner("📄 Parsing PDF…"):
        cv_text = extract_pdf_text(pdf_bytes)

    if not cv_text.strip():
        st.error("No text could be extracted. Make sure your CV is a text-based PDF, not a scanned image.")
        st.stop()

    st.success(f"✅ CV parsed — **{len(cv_text):,}** characters extracted.")

    with st.spinner("🧠 AI reading your CV…"):
        profile = parse_cv_profile(cv_text, groq_key)

    # Show extracted profile card
    experiences_html = "".join(
        f"&nbsp;&nbsp;• {e}<br>" for e in profile.get("key_experiences", [])
    )
    achievements_html = "".join(
        f"&nbsp;&nbsp;• {a}<br>" for a in profile.get("achievements", [])
    )
    st.markdown('<p class="section-label">🪪 Extracted Profile</p>', unsafe_allow_html=True)
    st.markdown(f"""
<div class="profile-card">
<strong>Name:</strong> {profile.get('name', '—')}<br>
<strong>College:</strong> {profile.get('college', '—')}<br>
<strong>Degree:</strong> {profile.get('degree', '—')} &nbsp;·&nbsp; Graduating {profile.get('graduation_year', '—')}<br>
<strong>Domain:</strong> {profile.get('domain', '—')}<br>
<strong>Target Role:</strong> {profile.get('target_role', '—')}<br>
<strong>Skills:</strong> {', '.join(profile.get('top_skills', []))}<br>
<strong>Certifications:</strong> {', '.join(profile.get('certifications', [])) or '—'}<br>
<br><strong>Key Experiences:</strong><br>{experiences_html}
<br><strong>Achievements:</strong><br>{achievements_html}
</div>
""", unsafe_allow_html=True)

    with st.spinner(f"🏢 Generating {num_companies} target companies…"):
        companies = generate_company_list(profile, groq_key, num=num_companies)

    if not companies:
        st.error("Failed to generate company list. Check your Groq API key.")
        st.stop()

    # Persist everything to session state
    st.session_state.update({
        "profile"     : profile,
        "companies"   : companies,
        "cv_text"     : cv_text,
        "pdf_bytes"   : pdf_bytes,
        "pdf_name"    : cv_file.name,
        "sender_name" : sender_name,
        "linkedin_url": linkedin_url,
        "safe_mode"   : safe_mode,
    })

    st.success(f"✅ Generated **{len(companies)}** target companies!")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Review & Edit Company List
# ─────────────────────────────────────────────────────────────────────────────
if "companies" in st.session_state:
    st.markdown("---")
    st.markdown('<div class="step-badge">Step 3 — Review &amp; Edit Target List</div>', unsafe_allow_html=True)
    st.caption("Remove companies you don't want, or add your own below.")

    companies     = st.session_state["companies"]
    company_names = [c["name"] for c in companies]

    selected_names = st.multiselect(
        "Companies to pitch:",
        options=company_names,
        default=company_names,
    )

    manual_input = st.text_input(
        "➕ Add more companies (comma-separated):",
        placeholder="e.g. Zepto, Groww, Razorpay",
    )

    # Build final list
    final_companies = [c for c in companies if c["name"] in selected_names]
    if manual_input.strip():
        for name in [n.strip() for n in manual_input.split(",") if n.strip()]:
            if name not in [c["name"] for c in final_companies]:
                final_companies.append({
                    "name"          : name,
                    "domain"        : "technology company",
                    "why_fit"       : "manually added",
                    "role"          : st.session_state["profile"].get("target_role", "Internship"),
                    "search_keyword": name,
                })

    st.markdown(f"**{len(final_companies)} companies selected:**")
    for i, c in enumerate(final_companies, 1):
        st.markdown(
            f"`{i:02d}` **{c['name']}** — _{c.get('domain', '')}_ &nbsp;·&nbsp; "
            f"<span style='color:#93c5fd;font-size:0.82rem'>{c.get('role', '')}</span>",
            unsafe_allow_html=True,
        )

    # ── STEP 4 — Fire ────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="step-badge">Step 4 — Fire the Pipeline</div>', unsafe_allow_html=True)
    fire_btn = st.button(
        "⚡  Generate & Send Emails",
        type="primary",
        use_container_width=True,
    )

    if fire_btn:
        missing = []
        if not gmail_addr:   missing.append("Gmail Address (sidebar)")
        if not app_password: missing.append("Gmail App Password (sidebar)")
        if not groq_key:     missing.append("Groq API Key (sidebar)")
        if not serper_key:   missing.append("Serper API Key (sidebar)")
        if missing:
            st.error(f"Please fill in: **{', '.join(missing)}**")
            st.stop()

        profile      = st.session_state["profile"]
        pdf_bytes    = st.session_state["pdf_bytes"]
        pdf_name     = st.session_state["pdf_name"]
        sender_name  = st.session_state["sender_name"]
        linkedin     = st.session_state["linkedin_url"]
        safe_mode    = st.session_state["safe_mode"]
        college      = profile.get("college", "")

        run_log: list[dict] = []

        for idx, company in enumerate(final_companies):
            cname = company["name"]

            st.markdown(
                f'<div class="company-card">'
                f'<h3>[{idx+1}/{len(final_companies)}]&nbsp; {cname}</h3>'
                f'<span class="meta">{company.get("domain", "")} &nbsp;·&nbsp; {company.get("role", "")}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            status_slot = st.empty()
            log_entry   = {
                "Company"    : cname,
                "Target Type": "—",
                "Email Found": "—",
                "Status"     : "—",
            }

            # ── 4-Pass Scrape ─────────────────────────────────────────────
            status_slot.info("🔍 Running 4-pass email search (Alumni → VP → HR → General)…")
            scraped_email, target_type, context = None, None, ""

            try:
                scraped_email, target_type, context = scrape_recruiter_email(
                    company        = cname,
                    college        = college,
                    search_keyword = company.get("search_keyword", cname),
                    serper_key     = serper_key,
                )
            except Exception as exc:
                status_slot.warning(f"⚠️ Scrape error: {exc}")

            log_entry["Email Found"] = scraped_email or "Not found"
            log_entry["Target Type"] = target_type   or "—"

            if scraped_email:
                color_map = {
                    "Alumni"              : "#4ade80",
                    "VP / Director / Manager": "#f59e0b",
                    "HR / Talent Acquisition": "#60a5fa",
                }
                color = color_map.get(target_type, "#94a3b8")
                st.markdown(
                    f"📧 **Email:** `{scraped_email}` "
                    f"<span style='color:{color};font-size:0.8rem;font-family:DM Mono,monospace;'>"
                    f"[{target_type}]</span>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown("📭 No email found after 4-pass search — draft only.")

            # ── Draft ─────────────────────────────────────────────────────
            status_slot.info("✍️ Writing personalized email…")

            try:
                draft = draft_personalized_email(
                    profile      = profile,
                    company      = company,
                    target_type  = target_type,
                    context      = context,
                    linkedin_url = linkedin,
                    groq_key     = groq_key,
                )
            except Exception as exc:
                status_slot.error(f"❌ Draft failed: {exc}")
                log_entry["Status"] = "Draft error"
                run_log.append(log_entry)
                continue

            # Preview
            preview = f"Subject: {EMAIL_SUBJECT}\n{'─'*50}\n\n{draft}"
            st.markdown('<p class="section-label">📝 Email Preview</p>', unsafe_allow_html=True)
            st.markdown(f'<div class="draft-box">{preview}</div>', unsafe_allow_html=True)

            # ── Send ──────────────────────────────────────────────────────
            if not safe_mode:
                status_slot.success("✅ Draft ready — Safe Mode OFF, not sent.")
                log_entry["Status"] = "Draft only"

            elif not scraped_email:
                status_slot.warning("⚠️ No recipient address — skipping send.")
                log_entry["Status"] = "Skipped (no email)"

            else:
                status_slot.info(f"📤 Sending to `{scraped_email}`…")
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
                    status_slot.success(f"✅ Sent → `{scraped_email}` [{target_type}]")
                    log_entry["Status"] = "✅ Sent"

                except smtplib.SMTPAuthenticationError:
                    status_slot.error(
                        "❌ Gmail auth failed. Your App Password is wrong — "
                        "it is NOT your normal Gmail password. "
                        "Go to myaccount.google.com/apppasswords to generate one."
                    )
                    log_entry["Status"] = "Auth error"

                except smtplib.SMTPRecipientsRefused:
                    status_slot.error(f"❌ `{scraped_email}` was rejected by the mail server.")
                    log_entry["Status"] = "Recipient refused"

                except smtplib.SMTPException as exc:
                    status_slot.error(f"❌ SMTP error: {exc}")
                    log_entry["Status"] = "SMTP error"

                except Exception as exc:
                    status_slot.error(f"❌ Unexpected error: {exc}")
                    log_entry["Status"] = "Send error"

            run_log.append(log_entry)

            # ── Cooldown ──────────────────────────────────────────────────
            is_last = idx == len(final_companies) - 1
            if safe_mode and not is_last:
                cd = st.empty()
                for secs_left in range(COOLDOWN_SECS, 0, -1):
                    cd.warning(f"⏳ Anti-spam cooldown — next company in **{secs_left}s**…")
                    time.sleep(1)
                cd.empty()

        # ── Summary Table ─────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("## 📊 Run Summary")

        import pandas as pd
        st.dataframe(pd.DataFrame(run_log), use_container_width=True, hide_index=True)

        n_sent    = sum(1 for r in run_log if r["Status"] == "✅ Sent")
        n_drafted = sum(1 for r in run_log if r["Status"] == "Draft only")
        n_skip    = sum(1 for r in run_log if "Skipped" in str(r["Status"]))
        n_err     = len(run_log) - n_sent - n_drafted - n_skip

        st.success(
            f"🎉 Done! **{n_sent}** sent · **{n_drafted}** drafted · "
            f"**{n_skip}** skipped · **{n_err}** errors · "
            f"**{len(run_log)}** companies total."
        )
