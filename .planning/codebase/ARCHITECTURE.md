<!-- refreshed: 2026-04-28 -->
# Architecture

**Analysis Date:** 2026-04-28

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────┐
│                        Browser / Frontend                            │
│                  `static/index.html` (SPA, vanilla JS)               │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ HTTP + SSE (text/event-stream)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FastAPI Application Layer                          │
│                          `main.py`                                   │
│  /api/chat (SSE stream) · /api/upload · /api/documents               │
│  /api/drive/* · /api/calendar/* · /api/email/* · /api/notes/*        │
│  /auth/google · /auth/google/callback · /api/health                  │
└───┬───────────────┬───────────────┬───────────────┬─────────────────┘
    │               │               │               │
    ▼               ▼               ▼               ▼
┌────────┐   ┌────────────┐  ┌──────────┐  ┌─────────────┐
│Anthropic│   │ calendar_  │  │ gmail_   │  │drive_       │
│ Claude  │   │integration │  │integrat- │  │integration  │
│(tool use│   │    .py     │  │ion.py    │  │   .py       │
│  loop)  │   └─────┬──────┘  └────┬─────┘  └──────┬──────┘
└─────────┘         │              │               │
                    ▼              ▼               ▼
          ┌─────────────────────────────────────────────────┐
          │            Google APIs (OAuth2)                  │
          │  Google Calendar v3 · Gmail v1 · Drive v3        │
          └─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│              Background Thread: email_watcher.py                     │
│  Polls Gmail every 120s · generates draft replies via Claude         │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│              In-Memory Store: document_store (dict)                  │
│  `main.py` module-level · holds chunked RAG knowledge base           │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| FastAPI app | HTTP routing, request/response, startup lifecycle | `main.py` |
| Chat endpoint | Anthropic tool-use loop, SSE streaming to browser | `main.py` (`/api/chat`) |
| Document store | In-memory RAG knowledge base (chunks dict) | `main.py` (`document_store`) |
| RAG retrieval | Keyword-scored chunk search for system prompt context | `main.py` (`search_documents`) |
| Calendar integration | Google Calendar CRUD, availability, OAuth creds | `calendar_integration.py` |
| Gmail integration | Inbox read, search, draft create/update/delete | `gmail_integration.py` |
| Drive integration | Folder sync, file download, incremental indexing | `drive_integration.py` |
| Note tidy | LLM-powered shorthand note formatter (read-only) | `note_tidy.py` |
| Email watcher | Background polling thread, auto-draft replies | `email_watcher.py` |
| Frontend SPA | Single-page chat UI, document upload, status panels | `static/index.html` |

## Pattern Overview

**Overall:** Monolithic Python service with integration modules — a single FastAPI process contains the API layer, the Anthropic agentic loop, and all Google API adapters.

**Key Characteristics:**
- The Anthropic Claude model is the core decision-maker; all tool execution routes through the `_run_tool` dispatcher in `main.py`
- Stateless HTTP for all endpoints except `/api/chat`, which is a stateful SSE stream for the duration of a request
- In-memory `document_store` dict is the only persistence layer — it is lost on restart
- OAuth2 credentials are stored in environment variables (`GOOGLE_TOKEN`), not on disk
- A daemon background thread (`email_watcher.py`) runs independently of the request loop

## Layers

**HTTP / Routing Layer:**
- Purpose: Expose all functionality as REST endpoints; handle auth redirects
- Location: `main.py`
- Contains: FastAPI route handlers, Pydantic request/response models, CORS middleware, static file mount
- Depends on: all integration modules, `anthropic` SDK
- Used by: browser frontend, external HTTP clients

**Anthropic Agent Layer:**
- Purpose: Orchestrate multi-turn Claude tool-use conversations; stream partial results to clients
- Location: `main.py` (`chat()`, `_run_tool()`, `TOOLS`, `build_system_prompt()`)
- Contains: Tool definitions (schema), tool dispatcher, system prompt builder, SSE generator
- Depends on: integration modules (called synchronously from `_run_tool`)
- Used by: `/api/chat` endpoint; `email_watcher.py` (`generate_draft`)

**Google Integration Layer:**
- Purpose: Thin wrappers around Google API clients; all operations are stateless (creds passed in)
- Location: `calendar_integration.py`, `gmail_integration.py`, `drive_integration.py`
- Contains: CRUD functions, OAuth credential builder, response formatters
- Depends on: `google-api-python-client`, `google-auth`, `google-auth-oauthlib`
- Used by: `_run_tool` dispatcher in `main.py`; `email_watcher.py`; `note_tidy.py`

**Note Tidy Layer:**
- Purpose: One-shot LLM reformatting of clinical shorthand notes; never writes back to Drive
- Location: `note_tidy.py`
- Contains: `tidy_note_text()`, `tidy_note_file()`, `tidy_all_unprocessed()`, system prompt constant
- Depends on: `drive_integration.py` (download), `anthropic` SDK
- Used by: `_run_tool` dispatcher

**RAG / Knowledge Base Layer:**
- Purpose: Keyword-based retrieval from uploaded documents; injects context into system prompt
- Location: `main.py` (`chunk_text`, `extract_text`, `search_documents`, `document_store`)
- Contains: In-memory chunk store, text extraction (PDF/DOCX/TXT/MD), BM25-style keyword scorer
- Depends on: `pdfplumber`, `python-docx`
- Used by: `/api/chat`, `/api/upload`, `/api/drive/sync`, `email_watcher.py`

**Background Worker Layer:**
- Purpose: Autonomous Gmail polling; drafts replies without user interaction
- Location: `email_watcher.py`
- Contains: `watch_inbox` (loop), `generate_draft`, `start_watcher`, `stop_watcher`, `watcher_status`
- Depends on: `gmail_integration.py`, `anthropic` SDK, shared `document_store` and `search_documents` refs
- Used by: FastAPI `startup` event (`main.py` line 813)

## Data Flow

### Primary Chat Request Path

1. Browser sends POST `/api/chat` with message history (`main.py` `/api/chat` handler)
2. Latest user message is extracted and scored against `document_store` for RAG chunks (`search_documents`)
3. System prompt assembled with retrieved chunks via `build_system_prompt()`
4. `anthropic.AsyncAnthropic.messages.create()` called with `TOOLS` definitions — up to 8 loop iterations
5. Claude returns `stop_reason == "tool_use"` → `_run_tool(name, args)` dispatches to the correct integration module
6. Tool result serialised as JSON, appended as `user` turn; loop continues
7. Each text block and tool-event streamed to browser as SSE `data:` frames
8. On `stop_reason != "tool_use"`, loop breaks; `done: true` frame sent

### Drive Sync Path

1. POST `/api/drive/sync` (with optional `force=true`)
2. `sync_drive_to_knowledge_base()` lists Drive folder → filters new/modified via `_last_sync` dict
3. Each file downloaded, text extracted, chunked via `chunk_text()`, inserted into `document_store`
4. Stale documents (deleted from Drive) removed from `document_store`

### Email Watcher Auto-Draft Path

1. Daemon thread polls `list_inbox(unread_only=True)` every 120 seconds
2. New message IDs checked against `_processed_ids` set
3. `generate_draft()` calls Claude (non-streaming, synchronous `anthropic.Anthropic`) with knowledge base context
4. Draft saved via `create_draft()` in same Gmail thread; original marked read

### Google OAuth Flow

1. GET `/auth/google` → redirects to Google consent page
2. Google redirects to GET `/auth/google/callback?code=...`
3. Token dict displayed as JSON in HTML page for manual copy-paste into Railway env var `GOOGLE_TOKEN`
4. All subsequent API calls load creds from `GOOGLE_TOKEN` env var via `get_google_credentials()`

**State Management:**
- `document_store` (dict): module-level in `main.py`; shared by reference with `email_watcher` and `drive_integration`
- `_last_sync` (dict): module-level in `drive_integration.py`; tracks Drive file modification times
- `_processed_ids` (set): module-level in `email_watcher.py`; prevents duplicate draft generation
- `_processed` (dict): module-level in `note_tidy.py`; tracks tidied note modification times
- All state is in-memory only — lost on process restart

## Key Abstractions

**Tool Definition (TOOLS list):**
- Purpose: Anthropic-schema JSON objects describing callable tools; Claude selects these by name
- Location: `main.py` (lines 196–356)
- Pattern: Each tool has `name`, `description`, `input_schema` (JSON Schema object)

**`_run_tool` Dispatcher:**
- Purpose: Central if/elif chain mapping tool names to integration module function calls
- Location: `main.py` (`_run_tool`, lines 359–422)
- Pattern: Always returns a JSON-serialisable dict; errors returned as `{"error": "..."}`, never raised

**Google Credentials Object:**
- Purpose: Passed as first argument to all integration functions; refreshed automatically on expiry
- Location: Built in `calendar_integration.get_google_credentials()` from `GOOGLE_TOKEN` env var
- Pattern: `get_google_credentials()` returns `None` if unconfigured; all callers check this

**RAG Chunk:**
- Purpose: Unit of knowledge base storage; identified by `id`, `doc_id`, `doc_name`, `text`, `chunk_idx`
- Location: `main.py` (`chunk_text()`, `document_store`)
- Pattern: Keyword overlap scored at query time; top-k injected into system prompt

## Entry Points

**Web Server:**
- Location: `main.py` (bottom, `if __name__ == "__main__":`)
- Triggers: `uvicorn main:app --host 0.0.0.0 --port $PORT` (via `Procfile` / `railway.toml`)
- Responsibilities: Binds FastAPI app; triggers `startup_event` which starts email watcher thread

**FastAPI Startup Event:**
- Location: `main.py` (`startup_event`, line 813)
- Triggers: Uvicorn application startup
- Responsibilities: Configures logging; starts `email_watcher` daemon thread

**Chat API:**
- Location: `main.py` (`POST /api/chat`)
- Triggers: Browser message submission
- Responsibilities: Runs full Anthropic tool-use agentic loop; streams SSE response

## Architectural Constraints

- **Threading:** Single-threaded async event loop (uvicorn/asyncio) for HTTP; one additional daemon thread for email watcher. `_run_tool` calls integration modules synchronously from within the async generator — these are blocking I/O calls that block the event loop.
- **Global state:** `document_store` (dict), `_last_sync` (dict in `drive_integration.py`), `_processed_ids` (set in `email_watcher.py`), `_processed` (dict in `note_tidy.py`) — all module-level singletons. The email watcher accesses `document_store` by reference from `main.py`.
- **Circular imports:** `email_watcher.py` imports from `gmail_integration` inside the `watch_inbox` function body (deferred import) to avoid a circular dependency. `note_tidy.py` imports from `drive_integration.py`; `drive_integration.py` has no imports from other local modules.
- **No database:** All persistence is in-memory. Restart loses all uploaded documents and sync state.
- **OAuth credential storage:** Token stored only as an env var string; no token refresh persistence — if the token expires between restarts and there is no `refresh_token`, re-auth is required.

## Anti-Patterns

### Blocking I/O Inside Async Generator

**What happens:** `_run_tool()` in `main.py` calls Google API functions (network I/O) synchronously inside the `async def generate()` generator that drives the SSE response.
**Why it's wrong:** This blocks the entire uvicorn event loop for the duration of each Google API call, preventing other requests from being served concurrently.
**Do this instead:** Wrap blocking calls with `asyncio.to_thread()` or use async Google API clients. Example location: `main.py` lines 509–515.

### In-Memory State Lost on Restart

**What happens:** `document_store`, `_last_sync`, `_processed_ids`, and `_processed` are plain Python dicts/sets with no persistence.
**Why it's wrong:** Every deploy or crash requires the midwife to re-upload documents and re-sync Drive.
**Do this instead:** Persist `document_store` to a lightweight database (SQLite, Redis, or Railway's Postgres addon). See `main.py` lines 57–58 for the store definition.

### Duplicate Tool List (Patch Files)

**What happens:** `TOOLS` list and `_run_tool` dispatcher are defined in both `main.py` and in the patch files `chat_endpoint_patch.py` and `consolidated_patch.py`.
**Why it's wrong:** The patch files are dead code that can diverge from `main.py`, creating confusion about the authoritative implementation.
**Do this instead:** Delete `chat_endpoint_patch.py` and `consolidated_patch.py` — their contents are already fully integrated into `main.py`.

## Error Handling

**Strategy:** Integration-layer errors are caught at the `_run_tool` boundary and returned as `{"error": "..."}` dicts to Claude, which can then explain the failure to the user. HTTP endpoint handlers wrap integration calls in try/except and raise `HTTPException` with appropriate status codes.

**Patterns:**
- Google API `HttpError` caught in integration modules, re-raised as `RuntimeError` with a human-readable message
- `_run_tool` catches all exceptions and returns `{"error": str(e)}` — never raises
- FastAPI endpoints use `_require_google()` helper to return 401 before calling any Google API
- Email watcher loop catches all exceptions and logs them, then continues polling

## Cross-Cutting Concerns

**Logging:** Standard library `logging` configured at INFO in `startup_event`. `email_watcher.py` uses a named logger (`email_watcher`). No structured logging or log aggregation configured.
**Validation:** Pydantic models validate all inbound API request bodies. No output validation on integration module return values.
**Authentication:** Google OAuth2 (offline access, refresh token). Token stored in `GOOGLE_TOKEN` env var. No user-level authentication — the app is single-tenant (one midwife). CORS configured with `allow_origins=["*"]` — no origin restriction.

---

*Architecture analysis: 2026-04-28*
