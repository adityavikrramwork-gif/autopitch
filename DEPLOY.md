# AutoPitch v3 — Deployment Guide

## Prerequisites

- Python 3.10+
- Gmail account with App Password (not your regular password)
- Groq API key (free at https://console.groq.com/keys)
- Serper API key (free at https://serper.dev/api-key)

---

## Option 1 — Local Development (Fastest)

```bash
# 1. Clone and enter the project
cd autopitch

# 2. Create a virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create your .env file (copy the example)
cp .env.example .env
# Then edit .env and fill in your real keys:
#   GMAIL_ADDRESS=you@gmail.com
#   GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
#   GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
#   SERPER_API_KEY=xxxxxxxxxxxxxxxxxxxx

# 5. Run the app
streamlit run app.py
```

The app opens at **http://localhost:8501**. Your keys from `.env` are picked up automatically — you can also enter them in the sidebar.

---

## Option 2 — Streamlit Community Cloud (Free Hosting)

Streamlit Cloud is the easiest way to deploy for free. Your app gets a public URL.

### Step-by-step:

```bash
# 1. Push your code to GitHub
git init
git add .
git commit -m "AutoPitch v3.1 - production ready"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/autopitch.git
git push -u origin main
```

```bash
# 2. Go to https://streamlit.io/cloud and sign in with GitHub

# 3. Click "New app" → select your repo

# 4. Set secrets (do NOT put these in .env or code):
#    In the Streamlit Cloud dashboard, go to Settings → Secrets
#    Add each secret:
#    GMAIL_ADDRESS = "you@gmail.com"
#    GMAIL_APP_PASSWORD = "xxxx xxxx xxxx xxxx"
#    GROQ_API_KEY = "gsk_xxxxxxxxxxxxxxxxxxxx"
#    SERPER_API_KEY = "xxxxxxxxxxxxxxxxxxxx"

# 5. Click "Deploy"
```

Your app will be live at `https://YOUR_USERNAME-autopitch-app-xxxx.streamlit.app`

### Important for Streamlit Cloud:
- The `.env` file is for **local development only** — Streamlit Cloud uses its own secrets system
- Our `config.py` already falls back to `st.secrets` when `.env` is not available
- Make sure `.env` is in `.gitignore` (it already is)

---

## Option 3 — Docker Deployment (VPS / Cloud Server)

### Step 1: Create `Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### Step 2: Build and Run

```bash
# Build the image
docker build -t autopitch .

# Run with environment variables
docker run -d \
  --name autopitch \
  -p 8501:8501 \
  -e GMAIL_ADDRESS=you@gmail.com \
  -e GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx" \
  -e GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx \
  -e SERPER_API_KEY=xxxxxxxxxxxxxxxxxxxx \
  autopitch
```

Visit **http://your-server:8501**

### Optional: Docker Compose

```yaml
# docker-compose.yml
version: "3.8"
services:
  autopitch:
    build: .
    ports:
      - "8501:8501"
    env_file:
      - .env
    restart: unless-stopped
```

```bash
docker compose up -d
```

---

## Option 4 — VPS with Nginx Reverse Proxy

For a VPS (AWS EC2, DigitalOcean, Hetzner, etc.):

### Step 1: Setup the server

```bash
# SSH into your VPS
ssh root@your-server-ip

# Install Python, pip, and venv
apt update && apt install -y python3 python3-pip python3-venv nginx

# Clone your repo
git clone https://github.com/YOUR_USERNAME/autopitch.git /opt/autopitch
cd /opt/autopitch

# Create venv and install
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env
cp .env.example .env
nano .env  # fill in your keys
```

### Step 2: Create a systemd service

```ini
# /etc/systemd/system/autopitch.service
[Unit]
Description=AutoPitch Streamlit App
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/autopitch
Environment="PATH=/opt/autopitch/venv/bin"
ExecStart=/opt/autopitch/venv/bin/streamlit run app.py --server.port 8501 --server.address 127.0.0.1
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable autopitch
sudo systemctl start autopitch
```

### Step 3: Nginx config with HTTPS

```nginx
# /etc/nginx/sites-available/autopitch
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/autopitch /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Add HTTPS with Let's Encrypt
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com
```

---

## Security Checklist

- [ ] `.env` file is **never** committed to git (it's in `.gitignore`)
- [ ] Gmail uses an **App Password**, not your real password
- [ ] Streamlit config has `enableCORS = true` and `enableXsrfProtection = true`
- [ ] API keys are stored in `.env` (local) or Streamlit secrets (cloud), never in code
- [ ] Logs directory is excluded from git (in `.gitignore`)
- [ ] Run `python -m pytest tests/ -v` before every deploy to verify nothing is broken

---

## Running Tests

```bash
# From the project root
python -m pytest tests/ -v

# With coverage (if you install pytest-cov)
pip install pytest-cov
python -m pytest tests/ -v --cov=. --cov-report=term-missing
```

---

## Troubleshooting

| Issue | Fix |
|---|---|
| "No module named 'tenacity'" | Run `pip install -r requirements.txt` |
| "Gmail auth failed" | You need an **App Password**, not your real password. Go to https://myaccount.google.com/apppasswords |
| "Invalid Groq API key" | Get a new key at https://console.groq.com/keys |
| Streamlit blank page | Clear browser cache, hard-refresh (Ctrl+Shift+R) |
| Port 8501 in use | Kill the process or run `streamlit run app.py --server.port 8502` |