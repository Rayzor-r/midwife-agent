# Technology Stack

**Analysis Date:** 2026-04-28

## Languages

**Primary:**
- Python 3.11.9 - All backend logic, API server, integrations, AI tooling

**Secondary:**
- HTML/JavaScript - Single-page frontend (`static/index.html`, `index.html`)

## Runtime

**Environment:**
- Python 3.11.9 (pinned via `runtime.txt`)

**Package Manager:**
- pip
- Lockfile: Not present (only `requirements.txt` with pinned versions)

## Frameworks

**Core:**
- FastAPI 0.111.0 - HTTP API server and route definitions (`main.py`)
- Uvicorn 0.29.0 (with `[standard]` extras) - ASGI server, used in both Dockerfile and Procfile

**Build/Dev:**
- Docker (via `Dockerfile`) - Container image built with `python:3.11-slim`
- Nixpacks (via `railway.toml`) - Railway build system, used when deploying without a prebuilt image

**Testing:**
- Not detected - no test framework or test files present

## Key Dependencies

**Critical:**
- `anthropic>=0.40.0` - Anthropic Claude API client; used in `main.py`, `note_tidy.py`, and `email_watcher.py` for chat, tool-use loops, note formatting, and auto-draft generation
- `fastapi==0.111.0` - All REST endpoints in `main.py`
- `uvicorn[standard]==0.29.0` - Serves the FastAPI app in all deployment contexts

**Google API Stack:**
- `google-api-python-client==2.128.0` - Builds Google Calendar and Drive service objects via `googleapiclient.discovery.build()`
- `google-auth==2.29.0` - OAuth2 credentials and token refresh
- `google-auth-oauthlib==1.2.0` - OAuth2 flow construction (`Flow.from_client_config`)
- `google-auth-httplib2==0.2.0` - HTTP transport for Google auth

**Document Processing:**
- `pdfplumber==0.11.0` - PDF text extraction (`main.py`, `drive_integration.py`)
- `python-docx==1.1.2` - DOCX text extraction (`main.py`, `drive_integration.py`)
- `python-multipart==0.0.9` - Multipart form data for file uploads to `/api/upload`

**Infrastructure:**
- `python-dotenv==1.0.1` - Loads `.env` into environment at startup (`load_dotenv()` in `main.py`)

**Unlisted dependency (Outlook integration):**
- `msal` (Microsoft Authentication Library) - Used in `outlook_integration.py` but NOT listed in `requirements.txt`
- `requests` - Used in `outlook_integration.py` for Microsoft Graph API calls; also not in `requirements.txt`

## Configuration

**Environment:**
- Loaded via `python-dotenv` from `.env` file (`.env.example` present in repo root)
- Required env vars at runtime:
  - `ANTHROPIC_API_KEY` - Anthropic API access
  - `GOOGLE_CLIENT_ID` - Google OAuth client
  - `GOOGLE_CLIENT_SECRET` - Google OAuth client secret
  - `GOOGLE_TOKEN` - Serialized Google OAuth token JSON (stored in Railway Variables)
  - `GOOGLE_DRIVE_FOLDER_ID` - Drive folder to sync for RAG knowledge base
  - `GOOGLE_DRIVE_NOTES_FOLDER_ID` - Separate Drive folder for midwifery notes
  - `CLAUDE_MODEL` - Overrides the default model (defaults to `claude-sonnet-4-5`)
  - `RAILWAY_PUBLIC_DOMAIN` - Set by Railway; used to construct the public base URL
  - `PORT` - Set by Railway; Uvicorn listens on this port
  - `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_TENANT_ID`, `OUTLOOK_TOKEN` - Outlook integration (not wired into main app)

**Build:**
- `Dockerfile` - `python:3.11-slim`, installs `requirements.txt`, runs `uvicorn main:app`
- `railway.toml` - Nixpacks builder, start command `uvicorn main:app --host 0.0.0.0 --port $PORT`, restarts on failure (max 10 retries)
- `Procfile` - Heroku-style process declaration (`web: uvicorn main:app ...`)

## Platform Requirements

**Development:**
- Python 3.11+
- pip (standard)
- `.env` file with required secrets

**Production:**
- Deployed on Railway (confirmed by `railway.toml`, `RAILWAY_PUBLIC_DOMAIN` env var, and hardcoded redirect URI `https://midwife-agent-production.up.railway.app/auth/google/callback` in `calendar_integration.py`)
- Docker container or Nixpacks build

---

*Stack analysis: 2026-04-28*
