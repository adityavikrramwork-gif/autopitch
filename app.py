"""
AutoPitch v3 — Streamlit UI Layer
All business logic lives in dedicated modules. This file is UI only.
"""

import time

import streamlit as st

from api import GroqAPIError, SerperAPIError
from config import cfg
from cv_parser import extract_pdf_text, generate_company_list, parse_cv_profile
from email_service import draft_personalized_email, send_email_smtp, validate_smtp_credentials
from logger import logger
from scraper import scrape_recruiter_email
from validators import (
    sanitize_sender_name,
    validate_linkedin_url,
    validate_num_companies,
    validate_pdf_upload,
)

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
# Sidebar — Credentials
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<p class="section-label">🔐 Credentials</p>', unsafe_allow_html=True)
    st.caption("Prefer .env or Streamlit secrets for production. Keys in this session are not persisted.")

    gmail_addr = st.text_input("Gmail Address", placeholder="you@gmail.com")
    app_password = st.text_input("Gmail App Password", type="password", placeholder="xxxx xxxx xxxx xxxx")
    groq_key = st.text_input("Groq API Key", type="password", placeholder="gsk_...")
    serper_key = st.text_input("Serper API Key", type="password", placeholder="a1b2c3...")

    # Allow env-var fallback if sidebar is empty
    if not groq_key and cfg.groq_api_key:
        groq_key = cfg.groq_api_key
    if not serper_key and cfg.serper_api_key:
        serper_key = cfg.serper_api_key
    if not gmail_addr and cfg.gmail_address:
        gmail_addr = cfg.gmail_address
    if not app_password and cfg.gmail_app_password:
        app_password = cfg.gmail_app_password

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
        "v3.1 · Prose emails · 4-pass scraping · BYOK"
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
        "Companies", min_value=cfg.min_companies, max_value=cfg.max_companies,
        value=cfg.default_companies, label_visibility="collapsed",
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
st.markdown('<div class="step-badge">Step 2 — AI Reads CV &amp; Generate Target List</div>', unsafe_allow_html=True)

analyse_btn = st.button(
    "🔍  Analyse CV & Generate Company List",
    type="primary",
    use_container_width=True,
)

if analyse_btn:
    # ── Validate inputs ──
    errors = []
    if not cv_file:
        errors.append("CV (PDF)")
    else:
        ok, msg = validate_pdf_upload(cv_file.name, cv_file.size)
        if not ok:
            errors.append(msg)
    if not sender_name:
        errors.append("Your Full Name")
    if not linkedin_url:
        errors.append("LinkedIn URL")
    else:
        ok, url_or_err = validate_linkedin_url(linkedin_url)
        if not ok:
            errors.append(url_or_err)
        else:
            linkedin_url = url_or_err
    if not groq_key:
        errors.append("Groq API Key")
    if errors:
        st.error(f"Please fix: **{'  ·  '.join(errors)}**")
        st.stop()

    pdf_bytes = cv_file.read()

    with st.spinner("📄 Parsing PDF…"):
        cv_text = extract_pdf_text(pdf_bytes)

    if not cv_text.strip():
        st.error("No text could be extracted. Make sure your CV is a text-based PDF, not a scanned image.")
        st.stop()

    st.success(f"✅ CV parsed — **{len(cv_text):,}** characters extracted.")

    with st.spinner("🧠 AI reading your CV…"):
        try:
            profile = parse_cv_profile(cv_text, groq_key)
        except GroqAPIError as exc:
            st.error(str(exc))
            st.stop()

    # ── Show extracted profile ──
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
        try:
            companies = generate_company_list(profile, groq_key, num=num_companies)
        except GroqAPIError as exc:
            st.error(str(exc))
            st.stop()

    if not companies:
        st.error("Failed to generate company list. Check your Groq API key.")
        st.stop()

    st.session_state.update({
        "profile": profile,
        "companies": companies,
        "cv_text": cv_text,
        "pdf_bytes": pdf_bytes,
        "pdf_name": cv_file.name,
        "sender_name": sanitize_sender_name(sender_name),
        "linkedin_url": linkedin_url,
        "safe_mode": safe_mode,
    })

    st.success(f"✅ Generated **{len(companies)}** target companies!")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Review & Edit Company List
# ─────────────────────────────────────────────────────────────────────────────
if "companies" in st.session_state:
    st.markdown("---")
    st.markdown('<div class="step-badge">Step 3 — Review &amp; Edit Target List</div>', unsafe_allow_html=True)
    st.caption("Remove companies you don't want, or add your own below.")

    companies = st.session_state["companies"]
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

    final_companies = [c for c in companies if c["name"] in selected_names]
    if manual_input.strip():
        for name in [n.strip() for n in manual_input.split(",") if n.strip()]:
            if name not in [c["name"] for c in final_companies]:
                final_companies.append({
                    "name": name,
                    "domain": "technology company",
                    "why_fit": "manually added",
                    "role": st.session_state["profile"].get("target_role", "Internship"),
                    "search_keyword": name,
                })

    st.markdown(f"**{len(final_companies)} companies selected:**")
    for i, c in enumerate(final_companies, 1):
        st.markdown(
            f"`{i:02d}` **{c['name']}** — _{c.get('domain', '')}_ &nbsp;·&nbsp; "
            f"<span style='color:#93c5fd;font-size:0.82rem'>{c.get('role', '')}</span>",
            unsafe_allow_html=True,
        )

    # ── STEP 4 — Fire ──────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="step-badge">Step 4 — Fire the Pipeline</div>', unsafe_allow_html=True)
    fire_btn = st.button(
        "⚡  Generate & Send Emails",
        type="primary",
        use_container_width=True,
    )

    if fire_btn:
        # ── Validate credentials ──
        missing = []
        if not gmail_addr:
            missing.append("Gmail Address (sidebar)")
        if not app_password:
            missing.append("Gmail App Password (sidebar)")
        if not groq_key:
            missing.append("Groq API Key (sidebar)")
        if not serper_key:
            missing.append("Serper API Key (sidebar)")
        if missing:
            st.error(f"Please fill in: **{', '.join(missing)}**")
            st.stop()

        # ── Optional: verify Gmail credentials before starting ──
        if safe_mode:
            with st.spinner("🔐 Verifying Gmail credentials…"):
                ok, msg = validate_smtp_credentials(gmail_addr, app_password)
                if not ok:
                    st.error(msg)
                    logger.warning("Gmail auth failed for %s", gmail_addr)
                    st.stop()
                st.success("✅ Gmail credentials verified.")

        profile = st.session_state["profile"]
        pdf_bytes = st.session_state["pdf_bytes"]
        pdf_name = st.session_state["pdf_name"]
        sender_name = st.session_state["sender_name"]
        linkedin = st.session_state["linkedin_url"]
        safe_mode_flag = st.session_state["safe_mode"]
        college = profile.get("college", "")

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
            log_entry = {
                "Company": cname,
                "Target Type": "—",
                "Email Found": "—",
                "Status": "—",
            }

            # ── 4-Pass Scrape ──
            status_slot.info("🔍 Running 4-pass email search (Alumni → VP → HR → General)…")
            scraped_email, target_type, context = None, None, ""

            try:
                scraped_email, target_type, context = scrape_recruiter_email(
                    company=cname,
                    college=college,
                    search_keyword=company.get("search_keyword", cname),
                    serper_key=serper_key,
                )
            except SerperAPIError as exc:
                status_slot.warning(f"⚠️ Search error: {exc}")
                logger.warning("Serper error for %s: %s", cname, exc)

            log_entry["Email Found"] = scraped_email or "Not found"
            log_entry["Target Type"] = target_type or "—"

            if scraped_email:
                color_map = {
                    "Alumni": "#4ade80",
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

            # ── Draft ──
            status_slot.info("✍️ Writing personalized email…")

            draft = draft_personalized_email(
                profile=profile,
                company=company,
                target_type=target_type,
                context=context,
                linkedin_url=linkedin,
                groq_key=groq_key,
            )

            if draft is None:
                status_slot.error("❌ Draft generation failed. Check your Groq API key.")
                log_entry["Status"] = "Draft error"
                run_log.append(log_entry)
                continue

            # ── Preview ──
            preview = f"Subject: {cfg.email_subject}\n{'─'*50}\n\n{draft}"
            st.markdown('<p class="section-label">📝 Email Preview</p>', unsafe_allow_html=True)
            st.markdown(f'<div class="draft-box">{preview}</div>', unsafe_allow_html=True)

            # ── Send ──
            if not safe_mode_flag:
                status_slot.success("✅ Draft ready — Safe Mode OFF, not sent.")
                log_entry["Status"] = "Draft only"

            elif not scraped_email:
                status_slot.warning("⚠️ No recipient address — skipping send.")
                log_entry["Status"] = "Skipped (no email)"

            else:
                status_slot.info(f"📤 Sending to `{scraped_email}`…")
                try:
                    send_email_smtp(
                        gmail_addr=gmail_addr,
                        app_password=app_password,
                        to_email=scraped_email,
                        body=draft,
                        pdf_bytes=pdf_bytes,
                        pdf_filename=pdf_name,
                        sender_name=sender_name,
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
                    status_slot.error(f"❌ SMTP error — please try again later.")
                    logger.error("SMTP error sending to %s: %s", scraped_email, exc)
                    log_entry["Status"] = "SMTP error"

                except Exception as exc:
                    status_slot.error("❌ Unexpected error — please try again.")
                    logger.exception("Unexpected error sending email to %s", scraped_email)
                    log_entry["Status"] = "Send error"

            run_log.append(log_entry)

            # ── Cooldown ──
            is_last = idx == len(final_companies) - 1
            if safe_mode_flag and not is_last:
                cd = st.empty()
                for secs_left in range(cfg.cooldown_seconds, 0, -1):
                    cd.warning(f"⏳ Anti-spam cooldown — next company in **{secs_left}s**…")
                    time.sleep(1)
                cd.empty()

        # ── Summary Table ──
        st.markdown("---")
        st.markdown("## 📊 Run Summary")

        import pandas as pd
        st.dataframe(pd.DataFrame(run_log), use_container_width=True, hide_index=True)

        n_sent = sum(1 for r in run_log if r["Status"] == "✅ Sent")
        n_drafted = sum(1 for r in run_log if r["Status"] == "Draft only")
        n_skip = sum(1 for r in run_log if "Skipped" in str(r["Status"]))
        n_err = len(run_log) - n_sent - n_drafted - n_skip

        st.success(
            f"🎉 Done! **{n_sent}** sent · **{n_drafted}** drafted · "
            f"**{n_skip}** skipped · **{n_err}** errors · "
            f"**{len(run_log)}** companies total."
        )