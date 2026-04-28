# Codebase Structure

**Analysis Date:** 2026-04-28

## Directory Layout

```
midwife-agent/                    # Project root / repo root
├── main.py                       # FastAPI app, all routes, Anthropic agent loop, RAG store
├── calendar_integration.py       # Google Calendar CRUD + OAuth credential management
├── gmail_integration.py          # Gmail read/search/draft operations
├── drive_integration.py          # Google Drive folder sync + file download/extraction
├── note_tidy.py                  # LLM-powered clinical note formatter (read-only)
├── email_watcher.py              # Background polling thread for inbox auto-draft
├── chat_endpoint_patch.py        # Dead code — superseded patch, safe to delete
├── consolidated_patch.py         # Dead code — superseded patch, safe to delete
├── index.html                    # Alternate/legacy frontend (unused by app at runtime)
├── static/
│   └── index.html                # Active single-page chat UI (served at /)
├── requirements.txt              # Python dependencies (pip)
├── runtime.txt                   # Python version pin (python-3.11.9) for Railway/Nixpacks
├── Procfile                      # Heroku-style start command (uvicorn)
├── railway.toml                  # Railway deployment config (builder + start command)
├── Dockerfile                    # Container build (alternative to Nixpacks)
├── files.zip                     # Archived files (not used at runtime)
└── .planning/
    └── codebase/                 # GSD planning documents
        ├── ARCHITECTURE.md
        └── STRUCTURE.md
```

## Directory Purposes

**Root (module files):**
- Purpose: All Python source lives at the root level — there are no sub-packages
- Contains: One file per integration domain, plus the central `main.py`
- Key files: `main.py` (entry point and orchestrator), `calendar_integration.py`, `gmail_integration.py`, `drive_integration.py`, `note_tidy.py`, `email_watcher.py`

**`static/`:**
- Purpose: Static assets served by FastAPI's `StaticFiles` mount at `/static`
- Contains: `index.html` (the active SPA frontend — vanilla JS, inline CSS)
- Generated: No — manually authored
- Committed: Yes

**`.planning/codebase/`:**
- Purpose: GSD codebase map documents consumed by `/gsd-plan-phase` and `/gsd-execute-phase`
- Contains: ARCHITECTURE.md, STRUCTURE.md (and other maps as generated)
- Generated: Yes (by GSD mapper agent)
- Committed: Yes

## Key File Locations

**Entry Points:**
- `main.py`: FastAPI `app` object, all HTTP routes, uvicorn `__main__` block
- `Procfile`: `web: uvicorn main:app --host 0.0.0.0 --port $PORT`
- `railway.toml`: `startCommand = "sh -c 'uvicorn main:app --host 0.0.0.0 --port $PORT'"`
- `Dockerfile`: Alternative container-based deployment

**Configuration:**
- `requirements.txt`: All runtime Python dependencies
- `runtime.txt`: Python version (`python-3.11.9`)
- `railway.toml`: Railway platform deployment configuration
- `.env` (not committed): Local development environment variables

**Core Logic:**
- `main.py` lines 57–114: In-memory document store, `chunk_text`, `extract_text`, `search_documents`
- `main.py` lines 119–191: `build_system_prompt()` — RAG context injection
- `main.py` lines 196–356: `TOOLS` list — Anthropic tool schemas
- `main.py` lines 359–422: `_run_tool()` — tool dispatcher
- `main.py` lines 475–537: `/api/chat` SSE endpoint with tool-use loop
- `calendar_integration.py`: `get_google_credentials()`, `build_google_flow()`, calendar CRUD
- `gmail_integration.py`: `list_inbox()`, `get_email()`, `create_draft()`
- `drive_integration.py`: `sync_drive_to_knowledge_base()`, `download_file()`
- `note_tidy.py`: `tidy_note_text()`, `tidy_note_file()`, `TIDY_SYSTEM_PROMPT`
- `email_watcher.py`: `watch_inbox()`, `generate_draft()`, `start_watcher()`

**Frontend:**
- `static/index.html`: Complete SPA — HTML, CSS, and JavaScript in one file (inline everything)

**Dead Code:**
- `chat_endpoint_patch.py`: Superseded by current `main.py` — can be deleted
- `consolidated_patch.py`: Superseded by current `main.py` — can be deleted
- `index.html` (root level): Not served by the app (app serves `static/index.html`); may be a leftover

## Naming Conventions

**Files:**
- Snake_case for all Python modules: `calendar_integration.py`, `email_watcher.py`, `note_tidy.py`
- Each filename directly describes its domain: one file = one integration concern
- No versioning suffixes in file names (patches are separate files but should be deleted)

**Directories:**
- Lowercase, flat — no nested package hierarchy
- Single `static/` directory for all web assets

**Functions:**
- Public integration functions: descriptive snake_case verbs — `list_events`, `create_event`, `get_availability`, `create_draft`, `sync_drive_to_knowledge_base`
- Private helpers prefixed with `_`: `_run_tool`, `_require_google`, `_fmt`, `_parse_duration`, `_gmail_service`, `_decode_body`, `_build_mime`

**Variables:**
- Module-level singletons: SCREAMING_SNAKE_CASE constants (`TOOLS`, `CLAUDE_MODEL`, `CHUNK_SIZE`, `NZ_TZ`, `TIDY_SYSTEM_PROMPT`)
- Module-level mutable state: prefixed with `_` (`_last_sync`, `_processed_ids`, `_processed`, `_watcher_running`)
- Pydantic models: PascalCase (`ChatRequest`, `ChatMessage`, `CreateEventRequest`)

**API Routes:**
- REST style, grouped by domain prefix: `/api/chat`, `/api/calendar/*`, `/api/email/*`, `/api/drive/*`, `/api/notes/*`, `/auth/google*`
- Auth routes under `/auth/` not `/api/auth/`

## Where to Add New Code

**New Google API Integration (e.g., Google Tasks, Google Contacts):**
- Create: `{domain}_integration.py` at the project root (e.g., `tasks_integration.py`)
- Register: Add tool schemas to `TOOLS` list in `main.py`
- Dispatch: Add if-branches to `_run_tool()` in `main.py`
- Import: Add import block near the other integration imports in `main.py` (lines 29–39)
- REST endpoints: Add `@app.get/post/patch/delete("/api/{domain}/...")` handlers in `main.py`

**New Anthropic Tool:**
- Tool schema: Add entry to `TOOLS` list in `main.py` (after line 196)
- Execution: Add dispatch branch in `_run_tool()` in `main.py` (before the final `return {"error": ...}`)
- Update system prompt: Reflect new capability in `build_system_prompt()` tool description block

**New REST Endpoint (no Claude tool):**
- Add `@app.{method}("/api/...")` handler directly in `main.py` grouped with its domain section
- Use `_require_google()` helper for any endpoint needing Google credentials

**New Frontend Feature:**
- Edit `static/index.html` — all HTML, CSS, and JS is inline in this single file

**Utility / Shared Logic:**
- If it is specific to one integration: add to that module
- If it crosses multiple integrations: add to `main.py` in the relevant section (document store helpers, etc.)
- There is no `utils.py` or shared helpers module — do not create one without a clear multi-file need

## Special Directories

**`static/`:**
- Purpose: Web assets served by FastAPI `StaticFiles` at `/static`; `index.html` served at `/`
- Generated: No
- Committed: Yes

**`.planning/`:**
- Purpose: GSD planning artefacts (codebase maps, phase plans)
- Generated: Yes (GSD tooling)
- Committed: Yes

---

*Structure analysis: 2026-04-28*
