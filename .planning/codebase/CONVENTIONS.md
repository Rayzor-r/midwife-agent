# Coding Conventions

**Analysis Date:** 2026-04-28

## Naming Patterns

**Files:**
- Module-level integration files use `snake_case` with a descriptive noun: `calendar_integration.py`, `gmail_integration.py`, `drive_integration.py`, `email_watcher.py`, `note_tidy.py`
- Patch/draft files follow the same pattern: `chat_endpoint_patch.py`, `consolidated_patch.py`
- Entry point is `main.py`

**Functions:**
- Public functions: `snake_case` verbs or verb-noun pairs — `list_events`, `create_event`, `cancel_event`, `get_availability`, `build_system_prompt`, `chunk_text`, `extract_text`, `search_documents`
- Private/internal helpers: leading underscore + `snake_case` — `_fmt`, `_fmt_message`, `_fmt_email`, `_parse_duration`, `_decode_body`, `_get_header`, `_build_mime`, `_gmail_service`, `_drive_service`, `_graph_get`, `_graph_post`, `_graph_patch`, `_graph_delete`, `_run_tool`, `_require_google`
- FastAPI route handlers: descriptive `snake_case` nouns or verb-noun — `serve_frontend`, `chat`, `upload_document`, `list_documents`, `google_auth_start`, `drive_sync`, `calendar_list`, `email_inbox`, `notes_list`, `health`
- Background thread functions: `watch_inbox`, `start_watcher`, `stop_watcher`, `watcher_status`

**Variables:**
- `snake_case` throughout — `api_key`, `doc_id`, `chunk_count`, `days_ahead`, `poll_interval`
- Module-level state uses `snake_case` with a leading underscore for private state dicts: `_last_sync`, `_processed`, `_processed_ids`
- Global mutable state: `document_store`, `_watcher_running`
- Constants: `UPPER_SNAKE_CASE` — `CHUNK_SIZE`, `CHUNK_OVERLAP`, `CLAUDE_MODEL`, `BASE_URL`, `GOOGLE_SCOPES`, `NZ_TZ`, `GRAPH_BASE`, `MS_SCOPES`, `APPOINTMENT_DURATIONS`, `NOTES_FOLDER_ENV`, `TIDY_SYSTEM_PROMPT`, `TOOLS`, `SUPPORTED_MIME_TYPES`

**Types / Classes:**
- Pydantic models use `PascalCase` — `ChatMessage`, `ChatRequest`, `CreateEventRequest`, `UpdateEventRequest`, `DraftEmailRequest`, `UpdateDraftRequest`

## Code Style

**Formatting:**
- No automated formatter config file detected (no `.prettierrc`, `pyproject.toml` with `[tool.black]`, or `.flake8`)
- 4-space indentation throughout
- Max line length is relaxed — long lines are common, especially in dict literals and f-strings
- Blank lines used deliberately: two blank lines between top-level functions/classes, one blank line between logical blocks within a function
- Trailing commas used on multi-line dict/list literals

**Linting:**
- No linting config detected (`flake8`, `pylint`, `ruff`, `mypy` not present)
- Type annotations used on all public function signatures but NOT on internal helpers (e.g. `_gmail_service`, `_drive_service` have no return type annotation)

## Import Organization

**Order observed in every file:**
1. Standard library (`import io`, `import json`, `import os`, `import re`, `import threading`, `import time`)
2. Third-party packages (`import anthropic`, `from fastapi import ...`, `from google.oauth2...`, `import requests`)
3. Local project modules (`from calendar_integration import ...`, `from drive_integration import ...`)

**Deferred / conditional imports:**
- Heavy optional dependencies (`pdfplumber`, `docx`) are imported inside functions at point-of-use to avoid import errors when not installed:
  ```python
  # main.py:83-88
  if ext == ".pdf":
      import pdfplumber
  if ext == ".docx":
      from docx import Document
  ```
- Same pattern in `drive_integration.py:extract_text_from_bytes`
- `uuid` is imported inside `sync_drive_to_knowledge_base` (`drive_integration.py:145`)

**Path Aliases:**
- None. All local imports use bare module names (flat package structure).

## Error Handling

**Integration module pattern (all Google API modules):**
- Catch `googleapiclient.errors.HttpError` specifically, re-raise as `RuntimeError` with a descriptive message:
  ```python
  # calendar_integration.py:118
  except HttpError as e:
      raise RuntimeError(f"Calendar error: {e}")
  ```
- `get_google_credentials` swallows ALL exceptions silently and returns `None` — the caller checks for `None` before proceeding

**Tool dispatcher pattern (`main.py:_run_tool`):**
- Catches ALL exceptions, returns `{"error": str(e)}` dict — never raises to FastAPI
- This is by design so tool errors appear in the chat stream without crashing the request

**FastAPI route pattern:**
- Routes call `_require_google()` which raises `HTTPException(401, ...)` if not connected
- All routes wrap integration calls in `try/except Exception as e: raise HTTPException(500, str(e))`
- Document upload uses `HTTPException(400, ...)` for bad input, `HTTPException(422, ...)` for extraction failures, `HTTPException(404, ...)` for missing resources

**Background watcher (`email_watcher.py`):**
- Outer `while` loop has a broad `except Exception as e: logger.error(...)` that prevents the thread from crashing
- Inner operations (like `mark_read`) are wrapped in bare `except Exception: pass` to tolerate non-critical failures

**Microsoft Graph (`outlook_integration.py`):**
- Raises `RuntimeError(f"Graph API error {r.status_code}: {r.text}")` on any non-OK HTTP response
- Auth errors: raises `RuntimeError(f"MS auth error: {result.get('error_description')}")` on failed token exchange

## Logging

**Framework:** Python stdlib `logging` module. Only `email_watcher.py` uses it actively.

```python
# email_watcher.py:19-20
import logging
logger = logging.getLogger("email_watcher")
```

**Configured in `main.py` startup:**
```python
# main.py:816
logging.basicConfig(level=logging.INFO)
```

**Patterns:**
- `logger.info(...)` for normal operation milestones (watcher started, email processed, draft created)
- `logger.warning(...)` for degraded but non-fatal states (Google not connected)
- `logger.error(f"...: {e}")` for caught exceptions that don't surface to the user
- `logger.debug(...)` for noisy polling messages (no new emails)
- Integration modules (`calendar_integration.py`, `gmail_integration.py`, etc.) do NOT log — they raise exceptions only

## Comments

**Module docstrings:** Every file opens with a triple-quoted docstring naming the module, its purpose, and the organisation tag (`GC Advisory — gcadvisory.co.nz`). `main.py` includes a version and changelog note.

**Section separators:** Horizontal rule comments mark logical sections within files:
```python
# ── Credentials ────────────────────────────────────────────────────────────────
# ── Calendar CRUD ──────────────────────────────────────────────────────────────
# ── Gmail ──────────────────────────────────────────────────────────────────────
```

**Inline comments:** Used sparingly to clarify non-obvious logic (e.g., `# Prefer plain text, fall back to html` in `gmail_integration.py:44`, chunk overlap calculation in `main.py`).

**Function docstrings:** Short one-liners on public functions describing return value or side-effect constraint:
```python
def list_inbox(creds, max_results=20, unread_only=False) -> list[dict]:
    """Return recent inbox messages."""

def create_draft(...) -> dict:
    """
    Create a Gmail draft.
    If reply_to_id is given, creates a reply draft in that thread.
    NEVER sends automatically — midwife always reviews first.
    """
```

**Business rule comments:** Critical domain constraints written in ALL CAPS inline: `# NEVER sends automatically`, `# Track processed email IDs to avoid re-drafting`

**JSDoc/TSDoc:** Not applicable (Python project).

## Function Design

**Size:** Most integration functions are short (10-30 lines). The main exceptions are:
- `main.py:build_system_prompt` (~70 lines) — large string construction
- `main.py:chat` with nested `generate()` (~50 lines) — streaming generator
- `note_tidy.py:tidy_note_text` (~45 lines) — Claude API call + flag parsing
- `drive_integration.py:sync_drive_to_knowledge_base` (~60 lines) — full sync loop

**Parameters:**
- `Credentials` object always passed as the first parameter to integration functions
- Optional parameters use Python default values, typed with `Optional[T]` from `typing`
- Positional-or-keyword style; no keyword-only arguments enforced

**Return Values:**
- Integration functions always return `dict` or `list[dict]`
- Tool dispatcher (`_run_tool`) always returns `dict` — never raises
- Route handlers return `dict` directly (FastAPI serialises to JSON) or `StreamingResponse`
- Private helpers (`_fmt`, `_fmt_message`, `_fmt_email`) normalise external API shapes into a consistent internal dict schema

## Module Design

**Exports:**
- No `__all__` declarations. All public names are exported implicitly.
- `main.py` imports named symbols explicitly from each integration module

**Barrel Files:**
- None. `main.py` is the aggregating entry point but it is not a barrel file — it contains substantial application logic.

**State isolation:**
- Module-level mutable state is used in three modules: `document_store` (dict) in `main.py`, `_last_sync` (dict) in `drive_integration.py`, `_processed` (dict) in `note_tidy.py`, `_processed_ids` (set) and `_watcher_running` (bool) in `email_watcher.py`
- All state is in-memory with no persistence to disk or database

---

*Convention analysis: 2026-04-28*
