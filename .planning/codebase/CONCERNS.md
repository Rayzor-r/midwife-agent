# Codebase Concerns

**Analysis Date:** 2026-04-28

## Tech Debt

**Stale patch files left in the repository root:**
- Issue: `chat_endpoint_patch.py` and `consolidated_patch.py` are migration/patch scripts that have already been applied to `main.py`. They redefine `TOOLS`, `_run_tool`, `build_system_prompt`, and the `/api/chat` endpoint — all of which are now in `main.py`. These files are not imported anywhere and serve no runtime purpose.
- Files: `chat_endpoint_patch.py`, `consolidated_patch.py`
- Impact: Confusion for maintainers about what is canonical. `chat_endpoint_patch.py` imports non-existent functions (`get_message`, `search_messages`) that were renamed in the live integration — the file would crash if executed. Code duplication means future changes to tool definitions or the system prompt must be made in only `main.py`, but the stale copies make it unclear which is authoritative.
- Fix approach: Delete `chat_endpoint_patch.py` and `consolidated_patch.py` from the repository root. Add a note in git history or a brief comment in `main.py` marking the v2.1 upgrade for context.

**`outlook_integration.py` is unreferenced dead code:**
- Issue: A complete Microsoft Graph API / Outlook integration module exists but is not imported anywhere in `main.py`. It references `msal` which is not in `requirements.txt`.
- Files: `outlook_integration.py`
- Impact: The file introduces an undeclared dependency (`msal`). It would fail to import if ever referenced. It implies a planned feature that was never wired in.
- Fix approach: Either add Outlook tools to the agent (add `msal` to `requirements.txt`, add OAuth routes, expose tools) or remove `outlook_integration.py` from the repository until the feature is ready.

**`index.html` at project root is a duplicate of `static/index.html`:**
- Issue: `index.html` exists at the repo root alongside the served copy at `static/index.html`. The FastAPI app only serves `static/index.html`. The root file is not referenced anywhere.
- Files: `index.html`, `static/index.html`
- Impact: Risk of the root file being edited instead of the served copy, leading to silent divergence. Adds noise to the repo root.
- Fix approach: Delete `index.html` from the repo root. The canonical UI is `static/index.html`.

**`files.zip` binary blob committed to the repository:**
- Issue: A `files.zip` archive is committed to the repository root. Its contents are unknown — it may be a snapshot of integration files from earlier development.
- Files: `files.zip`
- Impact: Unnecessary binary in git history. If it contains credentials or identifiable patient data from testing, this is a security concern.
- Fix approach: Inspect and delete `files.zip`. If the content is still needed, track it outside the repository or document its purpose.

**In-memory document store with no persistence:**
- Issue: `document_store` in `main.py` is a plain Python `dict` instantiated at startup (`document_store: dict = {}`). Uploaded documents and Drive-synced content live in memory only.
- Files: `main.py` (line 57)
- Impact: Every Railway redeploy or crash wipes all indexed documents. The midwife must re-upload or re-trigger Drive sync after every deployment. At scale (many large PDFs), memory on the Railway container becomes the hard limit.
- Fix approach: Persist indexed chunks to a lightweight store (SQLite via SQLModel, or write chunk JSON to disk). Reload on startup. For larger deployments, use a vector store such as Chroma or pgvector.

**Keyword-only RAG search with no vector similarity:**
- Issue: `search_documents` in `main.py` (lines 99–114) uses word-overlap scoring (`len(q_words & c_words)`) with a +3 bonus for substring match. There is no embedding-based semantic search.
- Files: `main.py` (lines 99–114)
- Impact: Searching for "antenatal haemorrhage" will miss chunks that use "APH" or "antepartum bleeding". Clinical guideline retrieval for queries using standard abbreviations (FH, VE, SROM) will be unreliable.
- Fix approach: Add sentence-transformers or use the Anthropic embeddings API to generate chunk embeddings at index time, then rank by cosine similarity at query time.

**`_last_sync` and `_processed_ids` are module-level mutable state with no thread safety:**
- Issue: `_last_sync` in `drive_integration.py` (line 27) and `_processed_ids` in `email_watcher.py` (line 14) are plain Python sets/dicts mutated by the background watcher thread and the main FastAPI event loop concurrently.
- Files: `drive_integration.py` (line 27), `email_watcher.py` (lines 14–15)
- Impact: Race conditions can cause duplicate email draft generation or double-indexing of Drive files. Under cpython's GIL this is unlikely to corrupt data, but it is not correct and would break under a multi-worker deployment.
- Fix approach: Protect with `threading.Lock`, or migrate tracking state to a persistent backend (database or file) shared safely across threads.

**`get_google_credentials()` refreshes the token in-place but cannot persist the refreshed token:**
- Issue: When the Google token expires, `get_google_credentials` in `calendar_integration.py` (line 49) calls `creds.refresh(Request())` to get a new access token. The refreshed token is never written back to the `GOOGLE_TOKEN` environment variable in Railway.
- Files: `calendar_integration.py` (lines 35–53)
- Impact: After the access token expires (typically 1 hour), each request refreshes in memory for the life of the process, but after a restart the token will expire again immediately. If the refresh token itself is revoked or expired, all Google integrations silently fail — returning `None` from `get_google_credentials` with no alerting.
- Fix approach: Log a warning when token refresh occurs. Consider storing the refreshed token to a persistent secrets manager (Railway Secrets API, AWS SSM) rather than relying on the statically set env var.

**Hard-coded production redirect URI in source code:**
- Issue: `REDIRECT_URI = "https://midwife-agent-production.up.railway.app/auth/google/callback"` is hardcoded in `calendar_integration.py` (line 64).
- Files: `calendar_integration.py` (line 64)
- Impact: OAuth flow is broken in any environment that is not the production Railway deployment (local dev, staging). The redirect URI must match the Google Cloud Console exactly — a mismatch causes `redirect_uri_mismatch` errors.
- Fix approach: Move redirect URI to an environment variable (`GOOGLE_REDIRECT_URI`) with a sensible local default (`http://localhost:8000/auth/google/callback`).

**Inconsistent model string across files:**
- Issue: The Anthropic model is specified as a string literal in three separate places: `main.py` uses `os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")` (line 54), `note_tidy.py` hardcodes `"claude-sonnet-4-5"` (line 131), and `email_watcher.py` hardcodes `"claude-sonnet-4-6"` (line 79). The three values do not agree.
- Files: `main.py` (line 54), `note_tidy.py` (line 131), `email_watcher.py` (line 79)
- Impact: The watcher uses a different model than the chat agent and note tidy. Model upgrades require changes in multiple places and are easy to miss. Comments in patch files say "confirm exact model string on your end", indicating the model strings may already be stale.
- Fix approach: Centralise to a single `CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")` constant in `main.py` (already partially done) and import or pass it to `note_tidy.py` and `email_watcher.py`.

---

## Known Bugs

**`chat_endpoint_patch.py` imports non-existent functions:**
- Symptoms: If the file were ever imported or executed, it would raise `ImportError`.
- Files: `chat_endpoint_patch.py` (lines 27–28)
- Trigger: The file imports `get_message` and `search_messages` from `gmail_integration`, but those functions are named `get_email` and `search_emails` in the live module.
- Workaround: The file is not imported anywhere, so this is dormant. Fix: delete the file.

**`update_event` in `calendar_integration.py` reads the old start time incorrectly after it has been overwritten:**
- Symptoms: When `reschedule_appointment` is called with a new `start_datetime` but no `duration_minutes`, the code overwrites `existing["start"]` (line 165) and then immediately reads `existing["start"]["dateTime"]` (line 169) to compute the old duration — reading the new start, not the old one.
- Files: `calendar_integration.py` (lines 162–172)
- Trigger: Rescheduling an appointment to a new time without specifying a duration.
- Workaround: The resulting end time will be equal to the new start (zero duration) or produce an error depending on datetime parsing. Fix: capture old start/end before mutating `existing`.

**`note_tidy.py` flags parser breaks on notes with no blank line after the flags header:**
- Symptoms: If the Claude response starts with "Flags for review:" but has no intermediate blank line before the first non-bullet line, `body_start` remains 0 and `tidied` is re-set to the full response including flags.
- Files: `note_tidy.py` (lines 145–157)
- Trigger: Inconsistent Claude output format for the flags block.
- Workaround: Flags will appear duplicated in the `tidied` field. Fix: use a regex to split on the flags section rather than line-by-line iteration.

---

## Security Considerations

**CORS wildcard allows any origin:**
- Risk: Any website can make cross-origin requests to the API, including triggering calendar actions or email draft creation.
- Files: `main.py` (line 43)
- Current mitigation: None. `allow_origins=["*"]` with `allow_methods=["*"]` and `allow_headers=["*"]` is fully open.
- Recommendations: Restrict to the specific front-end origin. For Railway, set `allow_origins=[os.getenv("ALLOWED_ORIGIN", "https://midwife-agent-production.up.railway.app")]`. Add CSRF protection for state-mutating endpoints (calendar create/update/delete, email draft).

**No authentication on any API endpoint:**
- Risk: Any actor that can reach the Railway URL can list calendar events, read the Gmail inbox, trigger Drive sync, and create calendar events or email drafts.
- Files: `main.py` — all `/api/*` routes
- Current mitigation: Railway deployment may not be publicly listed, but the URL pattern `*.up.railway.app` is guessable and there is no authentication layer.
- Recommendations: Add a shared secret token checked via an API key header or HTTP Basic Auth. For a single-user tool, a simple `Authorization: Bearer <token>` middleware on all `/api/*` routes with the token stored in Railway env vars is sufficient.

**Google OAuth callback exposes the full token in an HTML page response:**
- Risk: After OAuth completes, `main.py` (lines 599–606) renders the full `GOOGLE_TOKEN` JSON in a `<textarea>` on screen. This is by design for manual copy-paste into Railway, but if a browser extension, screen-sharing session, or browser history captures this, the token is exposed.
- Files: `main.py` (lines 594–606)
- Current mitigation: The page instructs the user to copy and then close the tab. The token is not logged server-side.
- Recommendations: Document the security risk clearly on the page. Consider using the Railway API to write the token variable programmatically, eliminating the manual copy step.

**`files.zip` binary in repository of unknown content:**
- Risk: If the archive contains test data using real patient identifiers or credentials from development, this is a Health Information Privacy Code 2020 breach.
- Files: `files.zip`
- Current mitigation: None — contents unknown.
- Recommendations: Inspect the archive immediately, delete from git history using `git filter-repo` or BFG if sensitive content is found.

---

## Performance Bottlenecks

**Gmail `list_inbox` and `search_emails` make N+1 API calls:**
- Problem: Both functions in `gmail_integration.py` first list message IDs, then fetch each message individually (`get_media` per message). For `max_results=20` this is 21 sequential HTTP calls.
- Files: `gmail_integration.py` (lines 96–108, 152–164)
- Cause: The Gmail list API only returns IDs and metadata; full body requires a separate `get` call per message.
- Improvement path: Use the Gmail batch API (`googleapiclient.http.BatchHttpRequest`) to parallelise the per-message fetches. Alternatively, use `format="metadata"` for the list view and only full-fetch on demand.

**Drive sync makes a redundant second `list_drive_files` call:**
- Problem: `sync_drive_to_knowledge_base` in `drive_integration.py` (line 148) calls `list_drive_files` to compute `drive_ids` even when `force_full=True` has already caused a full `list_drive_files` call on line 147. This is two identical API calls per sync.
- Files: `drive_integration.py` (lines 147–148)
- Cause: The stale-removal logic extracts IDs from the full list, but the variable is computed separately rather than reusing the already-fetched list.
- Improvement path: Reuse the result of the first `list_drive_files` call for both purposes.

**Entire conversation history is sent to Claude on every message:**
- Problem: The `messages` list in `main.py` (line 485) grows unbounded as the conversation continues. Every API call sends the full history to Claude.
- Files: `main.py` (lines 485–495)
- Cause: There is no message truncation, summarisation, or sliding-window logic.
- Improvement path: Cap the history to the last N turns, or summarise older turns using a cheap Claude call before they are truncated.

---

## Fragile Areas

**Email watcher background thread — no restart on failure:**
- Files: `email_watcher.py` (lines 107–181), `main.py` (lines 813–822)
- Why fragile: The watcher runs in a daemon thread started once at startup via `@app.on_event("startup")`. If the thread dies (unhandled exception within the loop that is not caught by the outer `except Exception`), it stops silently. The `/api/watcher/status` endpoint reports `running: True` based on the `_watcher_running` flag, which is never set to `False` on unexpected thread death.
- Safe modification: Wrap the entire `watch_inbox` body in a restart loop. Check thread liveness in `watcher_status()` using `threading.Thread.is_alive()`.
- Test coverage: Zero — no tests exist anywhere in the repository.

**`_run_tool` swallows all exceptions as `{'error': str(e)}`:**
- Files: `main.py` (lines 359–422)
- Why fragile: Every exception from any integration call is caught and returned as a string error dict. Claude receives this and may tell the midwife something failed, but the root cause (network timeout, token expiry, invalid argument) is not logged. Transient errors and programming errors look identical.
- Safe modification: Add `logger.exception(...)` inside the `except` block before returning the error dict.
- Test coverage: Zero.

**`chunk_text` can produce infinite loop on edge-case input:**
- Files: `main.py` (lines 62–77)
- Why fragile: The `start = end - CHUNK_OVERLAP` update on line 76 can set `start` to a value equal to or less than its previous value if `CHUNK_OVERLAP >= CHUNK_SIZE`. With the current constants (`CHUNK_SIZE=650`, `CHUNK_OVERLAP=120`) this is safe, but a config change could create an infinite loop.
- Safe modification: Add a guard: `if start >= end: break` inside the while loop.

**`get_availability` does not account for all-day events:**
- Files: `calendar_integration.py` (lines 208–212)
- Why fragile: The busy-slot filtering loop checks `s = e.get("start", {}).get("dateTime")`. All-day events use `date` instead of `dateTime` and are silently skipped. If the midwife has an all-day block (conference, leave), it is treated as free.
- Safe modification: Handle all-day events by treating them as blocking the full 8am–5pm window.

---

## Scaling Limits

**In-memory document store:**
- Current capacity: Limited to the Railway container's available RAM (typically 512 MB–1 GB on free/hobby tiers).
- Limit: A single large PDF (>200 pages) can consume 10–50 MB of text chunks. Approximately 20–100 large documents before memory pressure causes slowdowns or OOM kills.
- Scaling path: Persist chunks to SQLite or a file-based vector store (Chroma, FAISS). Mount Railway persistent volumes or use a managed database.

**Drive sync downloads all files sequentially:**
- Current capacity: Acceptable for small folders (<20 files, <50 MB total).
- Limit: A folder with 100 documents will timeout on Railway's default 30-second request timeout.
- Scaling path: Run sync as a background task (FastAPI `BackgroundTasks`) rather than in the request handler. Stream progress via a status endpoint.

---

## Dependencies at Risk

**`pdfplumber` pinned to `0.11.0` with no upper bound:**
- Risk: `pdfplumber` depends on `pdfminer.six`, which has had breaking changes across minor versions. A transitive upgrade could silently break PDF text extraction.
- Impact: Documents silently return empty text, removing them from the RAG knowledge base.
- Migration plan: Pin `pdfplumber` with an upper bound or use `pip-tools`/`pip-compile` to lock the full dependency tree.

**`anthropic>=0.40.0` is an unbounded minimum:**
- Risk: The Anthropic SDK has shipped breaking changes in its streaming and tool-use APIs between major versions. An `anthropic` upgrade could break the tool-use loop in `main.py`.
- Impact: The `/api/chat` endpoint fails for all users.
- Migration plan: Pin to a tested range, e.g. `anthropic>=0.40.0,<1.0.0`, and add a CI check that runs on dependency updates.

**`fastapi==0.111.0` pinned but `uvicorn` uses `[standard]` extras:**
- Risk: `uvicorn[standard]` pulls in `websockets` and `httptools` which are not pinned. A breaking `uvicorn` or `httptools` update could affect SSE streaming behaviour.
- Impact: SSE streaming to the UI breaks or becomes unreliable.
- Migration plan: Pin `uvicorn` to a specific version without the `[standard]` extras and declare `websockets` and `httptools` explicitly if needed.

---

## Missing Critical Features

**No user authentication:**
- Problem: The entire application — including Gmail, Calendar, and clinical note access — is unauthenticated.
- Blocks: Safe deployment to any network-accessible URL. Compliance with NZ Health Information Privacy Code 2020, which requires access controls on health-adjacent systems.

**No audit log:**
- Problem: There is no record of what actions the agent took (calendar events created, emails drafted, notes tidied) or on whose behalf.
- Blocks: Clinical accountability. If an appointment is created incorrectly or an email draft is sent in error, there is no trail to diagnose what happened.

**Token refresh after expiry is not persisted:**
- Problem: Refreshed Google tokens are not written back to Railway env vars. After the initial access token expires, the process must be alive to hold the refreshed token in memory.
- Blocks: Reliable unattended operation. After every redeploy, the token starts expired and must refresh in the first request — which may fail if the refresh token itself has aged out.

---

## Test Coverage Gaps

**Zero test coverage across the entire codebase:**
- What's not tested: All integration modules (`calendar_integration.py`, `gmail_integration.py`, `drive_integration.py`, `note_tidy.py`, `email_watcher.py`), all FastAPI endpoints in `main.py`, the RAG search function, and the tool dispatcher `_run_tool`.
- Files: All `.py` files
- Risk: Regressions in calendar CRUD, email draft creation, Drive sync logic, and note tidy parsing will go undetected until a production error occurs. The `update_event` bug described above (zero-duration rescheduling) is an example of a defect that a unit test would catch.
- Priority: High — the system handles health-adjacent scheduling and communication for a regulated clinical professional.

---

*Concerns audit: 2026-04-28*
