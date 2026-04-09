# ─────────────────────────────────────────────────────────────────
#  InternHunter India v3.0 | Pro Search Edition (Serper API)
#  Stack: Streamlit + Groq + Gmail SMTP + BeautifulSoup + Serper
# ─────────────────────────────────────────────────────────────────

import streamlit as st
import pandas as pd
import smtplib
import time
import re
import io
import json
import os
import PyPDF2
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# ──────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="InternHunter India",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    [data-testid="stAppViewContainer"] { background: #0f0f1a; }
    [data-testid="stSidebar"] { background: #16162a; }
    .main-header {
        background: linear-gradient(135deg, #10b981 0%, #3b82f6 100%);
        padding: 20px 28px; border-radius: 14px; margin-bottom: 24px;
        color: white;
    }
    .tag {
        background: #2d2d4a; color: #a5b4fc;
        padding: 3px 10px; border-radius: 20px;
        font-size: 12px; margin: 2px; display: inline-block;
    }
    .stButton > button {
        background: linear-gradient(135deg, #10b981, #3b82f6) !important;
        color: white !important; border: none !important;
        border-radius: 8px !important; font-weight: 600 !important;
    }
    .stButton > button:hover { opacity: 0.9 !important; }
    div[data-testid="stExpander"] {
        background: #1a1a2e; border: 1px solid #252540; border-radius: 10px;
    }
    .stTextInput input, .stTextArea textarea {
        background: #1e1e30 !important; border-color: #2d2d4a !important;
        color: #e2e8f0 !important;
    }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────
# PERSISTENCE
# ──────────────────────────────────────────────────────────────────
DATA_FILE = "internhunter_data.json"

def save_data():
    try:
        with open(DATA_FILE, "w") as f:
            json.dump({
                "companies":   st.session_state.companies,
                "log":         st.session_state.log,
                "emails_sent": st.session_state.emails_sent,
            }, f, indent=2)
    except Exception:
        pass

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f:
                d = json.load(f)
                return d.get("companies", []), d.get("log", []), d.get("emails_sent", 0)
        except Exception:
            pass
    return [], [], 0

if "loaded" not in st.session_state:
    companies, log, emails_sent = load_data()
    st.session_state.companies    = companies
    st.session_state.log          = log
    st.session_state.emails_sent  = emails_sent
    st.session_state.cv_text      = ""
    st.session_state.cv_bytes     = None
    st.session_state.cv_filename  = "resume.pdf"
    st.session_state.loaded       = True

# ══════════════════════════════════════════════════════════════════
#  SCRAPER (SERPER API EDITION)
# ══════════════════════════════════════════════════════════════════
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

def search_web(query: str, num: int = 10) -> list:
    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query, "num": num, "gl": "in"})
    # Your Hardcoded Serper API Key
    headers = {
        'X-API-KEY': '22928b7db563d2dd46ceea79bc2d935f33fe987d',
        'Content-Type': 'application/json'
    }
    try:
        r = requests.post(url, headers=headers, data=payload, timeout=15)
        results = r.json().get('organic', [])
        return [
            {
                "title": res.get('title', ''),
                "url": res.get('link', ''),
                "snippet": res.get('snippet', '')
            }
            for res in results
        ]
    except Exception as e:
        st.error(f"Search API Error: {str(e)}")
        return []

def extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "").strip("/").lower()
    except Exception:
        return ""

SKIP_DOMAINS = {
    "linkedin.com","indeed.com","naukri.com","internshala.com","glassdoor.com",
    "youtube.com","twitter.com","facebook.com","instagram.com",
    "wikipedia.org","amazon.com","flipkart.com","startupindia.gov.in","ambitionbox.com",
}

def find_emails_on_website(base_url: str) -> list:
    EMAIL_RE   = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
    JUNK_DOMS  = {"example.com","sentry.io","wix.com","domain.com"}
    emails     = set()
    pages      = [
        base_url,
        base_url.rstrip("/") + "/contact",
        base_url.rstrip("/") + "/about",
    ]
    for page in pages:
        try:
            r = requests.get(page, headers=HEADERS, timeout=9, allow_redirects=True)
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.select("a[href^='mailto:']"):
                e = a["href"].replace("mailto:", "").split("?")[0].strip().lower()
                if "@" in e:
                    emails.add(e)
            for e in EMAIL_RE.findall(r.text):
                e = e.lower()
                dom = e.split("@")[-1]
                if (dom not in JUNK_DOMS and not e.endswith((".png",".jpg",".css",".js")) and len(e) < 80):
                    emails.add(e)
        except Exception:
            pass
    cleaned = [e for e in emails if not any(x in e for x in ["noreply","bounce","mailer"])]
    priority = ["founder","ceo","hr","career","intern","hello","contact"]
    def score(e):
        local = e.split("@")[0]
        for i, kw in enumerate(priority):
            if kw in local: return i
        return len(priority)
    return sorted(cleaned, key=score)

def guess_emails(domain: str) -> list:
    return [
        f"careers@{domain}", f"hr@{domain}", f"founder@{domain}", f"hello@{domain}"
    ]

def get_tech_stack(url: str) -> list:
    tech = set()
    try:
        r = requests.get(url, headers=HEADERS, timeout=9)
        html = r.text.lower()
        checks = {
            "React": ["reactdom"], "Next.js": ["_next/"], "Vue.js": ["vue.js"],
            "Django": ["csrfmiddlewaretoken"], "Laravel": ["laravel"],
            "Node.js": ["express"], "AWS": ["amazonaws"], "Stripe": ["js.stripe.com"],
            "Razorpay": ["razorpay"]
        }
        for name, sigs in checks.items():
            if any(sig in html for sig in sigs):
                tech.add(name)
    except Exception:
        pass
    return sorted(tech) if tech else ["Unknown"]

def detect_funding_stage(company_name: str, domain: str, snippet: str) -> str:
    text = (snippet + " " + company_name + " " + domain).lower()
    if any(k in text for k in ["series b","series c","unicorn","ipo"]): return "Series B+"
    if "series a" in text: return "Series A"
    if any(k in text for k in ["seed fund","seed round"]): return "Seed"
    if any(k in text for k in ["bootstrapped","profitable"]): return "Bootstrapped"
    return "Unknown"

# ══════════════════════════════════════════════════════════════════
#  AI EMAIL GENERATOR
# ══════════════════════════════════════════════════════════════════
def _groq_call(prompt: str, groq_key: str) -> str:
    hdrs    = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
    payload = {"model": "llama3-8b-8192", "messages": [{"role": "user", "content": prompt}], "temperature": 0.75}
    r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=hdrs, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()

def _parse_subject_body(content: str, fallback_subject: str) -> tuple:
    lines, subject, body_lines, in_body = content.split("\n"), "", [], False
    for line in lines:
        if line.lower().startswith("subject:"):
            subject = line[8:].strip()
            in_body = True
        elif in_body:
            body_lines.append(line)
    return (subject or fallback_subject), "\n".join(body_lines).strip()

def generate_email(company_name, domain, tech_stack, funding_stage, role_seeking, candidate_name, candidate_skills, cv_summary, groq_key, tone) -> tuple:
    tech_str = ", ".join(tech_stack) if tech_stack and tech_stack[0] != "Unknown" else "not detected"