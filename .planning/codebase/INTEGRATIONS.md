# External Integrations

**Analysis Date:** 2026-04-28

## APIs & External Services

**AI / LLM:**
- Anthropic Claude API - Powers chat agent tool-use loop, note tidying, and email auto-drafting
  - SDK/Client: `anthropic` Python package (`anthropic.AsyncAnthropic` for streaming chat, `anthropic.Anthropic` for sync note tidy and email watcher)
  - Auth: `ANTHROPIC_API_KEY` env var
  - Models used:
    - `claude-sonnet-4-5` — default for chat and note tidy (overridable via `CLAUDE_MODEL` env var; hardcoded in `note_tidy.py`)
    - `claude-sonnet-4-6` — hardcoded in `email_watcher.py` for auto-draft generation
  - Files: `main.py`, `note_tidy.py`, `email_watcher.py`

**Google Workspace:**
- Google Calendar API v3 - Full appointment CRUD (list, create, update, delete, availability check)
  - SDK/Client: `googleapiclient.discovery.build("calendar", "v3", credentials=creds)`
  - Auth: OAuth2 via `GOOGLE_TOKEN` env var (serialized credentials JSON); flow via `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`
  - Scopes: `https://www.googleapis.com/auth/calendar`
  - File: `calendar_integration.py`

- Gmail API v1 - Read inbox, search, create/update/delete drafts, mark read, get threads
  - SDK/Client: `googleapiclient.discovery.build("gmail", "v1", credentials=creds)`
  - Auth: Shared Google OAuth token
  - Scopes: `https://www.googleapis.com/auth/gmail.modify`
  - File: `gmail_integration.py`

- Google Drive API v3 - List and download files from a designated folder for RAG indexing and note tidying
  - SDK/Client: `googleapiclient.discovery.build("drive", "v3", credentials=creds)`
  - Auth: Shared Google OAuth token
  - Scopes: `https://www.googleapis.com/auth/drive.readonly`
  - Env vars: `GOOGLE_DRIVE_FOLDER_ID` (RAG knowledge base folder), `GOOGLE_DRIVE_NOTES_FOLDER_ID` (note tidy folder)
  - File: `drive_integration.py`

**Microsoft / Outlook (secondary, not wired to main app):**
- Microsoft Graph API v1.0 (`https://graph.microsoft.com/v1.0`) - Outlook inbox, drafts, thread, mark-read, search
  - SDK/Client: `msal.ConfidentialClientApplication` for auth; `requests` for Graph API calls
  - Auth: `OUTLOOK_TOKEN` env var (access + refresh token JSON); `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_TENANT_ID`
  - Scopes: `Mail.ReadWrite`, `offline_access`
  - File: `outlook_integration.py`
  - Note: This module is fully implemented but is NOT imported in `main.py`. It exists as an alternate email backend.

## Data Storage

**Databases:**
- None — no database is used. All document/knowledge-base state is held in the in-memory Python dict `document_store` in `main.py`. State is lost on process restart.

**File Storage:**
- Google Drive (read-only) — source of documents for knowledge base and midwifery notes
- Local filesystem — `static/` directory for the frontend HTML (`static/index.html`)
- No persistent file writes by the application

**Caching:**
- In-memory dicts only:
  - `document_store` (`main.py`) — indexed document chunks
  - `_last_sync` (`drive_integration.py`) — tracks Drive file modification times to avoid re-indexing
  - `_processed` (`note_tidy.py`) — tracks which notes have been tidied
  - `_processed_ids` (`email_watcher.py`) — set of Gmail message IDs already auto-drafted

## Authentication & Identity

**Auth Provider:**
- Google OAuth2 — primary auth for all Google Workspace APIs
  - Implementation: Authorization Code Flow via `google_auth_oauthlib.flow.Flow`
  - OAuth flow entry: `GET /auth/google` → redirects to Google consent screen
  - Callback: `GET /auth/google/callback` → exchanges code, renders token as JSON for manual copy into Railway Variables
  - Token stored as JSON string in `GOOGLE_TOKEN` env var; loaded and refreshed at each request via `get_google_credentials()` in `calendar_integration.py`
  - Hardcoded production redirect URI: `https://midwife-agent-production.up.railway.app/auth/google/callback` (in `calendar_integration.py` line 64)

- Microsoft OAuth2 (MSAL) — secondary auth for Outlook
  - Implementation: Authorization Code Flow via `msal.ConfidentialClientApplication`
  - Not wired to any route in `main.py`
  - File: `outlook_integration.py`

## Monitoring & Observability

**Error Tracking:**
- None — no error tracking service (Sentry, Datadog, etc.) is configured

**Logs:**
- Python standard `logging` module; configured at `INFO` level on startup (`main.py` `startup_event`)
- Email watcher logs to `logging.getLogger("email_watcher")`
- Tool errors are caught and returned as `{"error": "..."}` dicts rather than raised exceptions

## CI/CD & Deployment

**Hosting:**
- Railway — confirmed by `railway.toml`, `RAILWAY_PUBLIC_DOMAIN` env var, and hardcoded redirect URI domain

**CI Pipeline:**
- None detected — no GitHub Actions, CircleCI, or other CI config files present

**Build:**
- Railway can use either Nixpacks (`railway.toml` builder) or the `Dockerfile` (both present)
- `Procfile` also present for Heroku-compatible platforms

## Environment Configuration

**Required env vars:**
- `ANTHROPIC_API_KEY` — Anthropic Claude API key
- `GOOGLE_CLIENT_ID` — Google OAuth2 client ID
- `GOOGLE_CLIENT_SECRET` — Google OAuth2 client secret
- `GOOGLE_TOKEN` — Serialized Google credentials JSON (obtained via `/auth/google` flow)
- `GOOGLE_DRIVE_FOLDER_ID` — Drive folder ID for RAG document sync
- `GOOGLE_DRIVE_NOTES_FOLDER_ID` — Drive folder ID for midwifery note tidy
- `PORT` — Set by Railway; Uvicorn bind port
- `RAILWAY_PUBLIC_DOMAIN` — Set by Railway; used to build `BASE_URL` in `main.py`

**Optional env vars:**
- `CLAUDE_MODEL` — Override default LLM model (default: `claude-sonnet-4-5`)
- `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_TENANT_ID`, `OUTLOOK_TOKEN` — Outlook integration (unused in main app)

**Secrets location:**
- All secrets stored as Railway environment variables
- `.env.example` present in repo root as a template; `.env` is gitignored

## Webhooks & Callbacks

**Incoming:**
- `GET /auth/google/callback` — Google OAuth2 redirect callback; exchanges authorization code for credentials
- No other webhooks — Gmail is polled (not push/webhook)

**Outgoing:**
- None — no outgoing webhooks are sent by the application

## Background Processes

**Email Watcher:**
- Runs as a daemon thread started on FastAPI app startup (`startup_event` in `main.py`)
- Polls Gmail for unread emails every 120 seconds
- Uses Anthropic API to generate draft replies, then saves them to Gmail via Gmail API
- Controlled via `GET /api/watcher/status` and `POST /api/watcher/stop`
- File: `email_watcher.py`

---

*Integration audit: 2026-04-28*
