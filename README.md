# Midwife Agent

A clinical support assistant for a Licensed Maternity Carer (LMC) midwifery practice in Northland, New Zealand.

The agent connects to Google Calendar, Gmail, and Google Drive so the midwife can check availability, book appointments, draft emails, and tidy de-identified notes — through a chat interface, without switching between apps.

Deployed on [Railway](https://railway.app). Backend: FastAPI + Anthropic Claude. Frontend: `static/index.html`.

---

## Quick start (local)

**Prerequisites:** Python 3.11+, a Google Cloud project with OAuth 2.0 credentials, an Anthropic API key.

```bash
# 1. Clone and install dependencies
git clone <repo-url>
cd midwife-agent
pip install -r requirements.txt

# 2. Create .env with required vars (see Environment Variables below)
cp .env.example .env   # or create .env manually
# Edit .env and fill in API_KEY, ANTHROPIC_API_KEY, GOOGLE_CLIENT_ID,
# GOOGLE_CLIENT_SECRET. Leave PORT and RAILWAY_PUBLIC_DOMAIN unset for local dev.

# 3. Start the server
uvicorn main:app --reload

# 4. Open the app
# Visit http://localhost:8000 in your browser.
# Enter your API_KEY value as the password when prompted.

# 5. Connect Google (first run)
# Visit http://localhost:8000/auth/google
# Complete the OAuth consent screen.
# The token will be printed in your terminal (search for GOOGLE_TOKEN).
# Copy the JSON value into GOOGLE_TOKEN in your .env file, then restart.
```

---

## Deployment (Railway)

1. Push the repo to GitHub and connect it to a Railway project.
2. Set all required environment variables in Railway → Variables (see table below).
3. Railway will detect the `Procfile` or `railway.toml` and start the service automatically.
4. Run the Google OAuth flow once after first deploy: visit `https://<your-domain>/auth/google`, complete consent, then retrieve `GOOGLE_TOKEN` from Railway → Deployments → Logs (search `GOOGLE_TOKEN`).

---

## Environment variables

All variables are read at startup. Variables without a default are required — the application will fail or return errors if they are missing.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_KEY` | **Yes** | *(none — fail-closed)* | Shared password for the deployment. All `/api/*` routes return HTTP 401 if this is unset or if the request header does not match. Choose a memorable phrase (e.g. `MidwifePractice2026!`). See [SECURITY.md](./SECURITY.md) for the full auth model. |
| `ANTHROPIC_API_KEY` | **Yes** | *(none)* | Anthropic API key for Claude. Obtain from [console.anthropic.com](https://console.anthropic.com). Used by the chat endpoint, email watcher, and note tidy. |
| `GOOGLE_CLIENT_ID` | **Yes** | *(none)* | OAuth 2.0 client ID from Google Cloud Console → APIs & Services → Credentials. |
| `GOOGLE_CLIENT_SECRET` | **Yes** | *(none)* | OAuth 2.0 client secret for the same credential. |
| `GOOGLE_TOKEN` | **Yes** | *(none)* | JSON token obtained by completing the `/auth/google` OAuth flow. On Railway, retrieve from Deployments → Logs after the flow (search `GOOGLE_TOKEN`). See [SECURITY.md § OAuth Token Handling](./SECURITY.md#3-oauth-token-handling). |
| `ALLOWED_ORIGIN` | **Yes (prod)** | `http://localhost:8000` | Full HTTPS URL of the deployment, used for CORS. Example: `https://midwife-agent-production.up.railway.app`. Must match the browser origin exactly — no trailing slash. Not needed for local development. |
| `RAILWAY_PUBLIC_DOMAIN` | **Yes (prod)** | `http://localhost:8000` | Public URL of the Railway deployment. Used to construct the OAuth redirect URI. Set automatically by Railway if you use the `${{RAILWAY_PUBLIC_DOMAIN}}` reference, or set it manually as the full domain (with or without `https://` — the app normalises it). |
| `CLAUDE_MODEL` | No | `claude-sonnet-4-5` | Anthropic model string passed to every `client.messages.create` call. Override to pin a specific model version. Example: `claude-opus-4-5`. |
| `GOOGLE_DRIVE_FOLDER_ID` | No | *(Drive root)* | Google Drive folder ID for the knowledge base sync (`/api/drive/sync`). If unset, the sync falls back to the root of My Drive. Find the ID in the Drive folder URL: `drive.google.com/drive/folders/<ID>`. |
| `GOOGLE_DRIVE_NOTES_FOLDER_ID` | No | *(none)* | Google Drive folder ID for the note tidy feature. The `tidy_note_from_drive` tool lists files from this folder. If unset, note tidying from Drive is unavailable (pasted notes still work). |
| `PORT` | No | `8000` | Port uvicorn listens on. Set automatically by Railway — do not set manually in Railway Variables. |

---

## Google OAuth setup

1. Create a project in [Google Cloud Console](https://console.cloud.google.com).
2. Enable the **Gmail API**, **Google Calendar API**, and **Google Drive API**.
3. Create an **OAuth 2.0 Client ID** (type: Web application).
4. Add the following to **Authorised redirect URIs**:
   - `http://localhost:8000/auth/google/callback` (local dev)
   - `https://<your-railway-domain>/auth/google/callback` (production)
5. Download the credentials and copy `Client ID` → `GOOGLE_CLIENT_ID`, `Client Secret` → `GOOGLE_CLIENT_SECRET`.
6. After deploying, run the OAuth flow once to obtain `GOOGLE_TOKEN` (see Quick start step 5).

---

## Key files

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app, all routes, tool-use loop, auth middleware |
| `calendar_integration.py` | Google Calendar CRUD + OAuth credential management |
| `gmail_integration.py` | Gmail read, draft, search |
| `drive_integration.py` | Google Drive folder sync into the RAG knowledge base |
| `email_watcher.py` | Background thread: polls Gmail every 120 s, auto-drafts replies |
| `note_tidy.py` | Note formatting via Claude (Drive folder or pasted text) |
| `static/index.html` | Frontend chat UI (canonical — served at `/`) |
| `SECURITY.md` | Auth model, CORS policy, OAuth token handling, credential rotation |

---

## Security

See [SECURITY.md](./SECURITY.md) for:
- Bearer token auth model and exempt routes
- CORS policy configuration
- OAuth token retrieval from Railway Logs
- Step-by-step credential rotation runbook
