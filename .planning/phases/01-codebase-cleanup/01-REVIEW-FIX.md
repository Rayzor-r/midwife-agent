---
phase: 01-codebase-cleanup
fix_date: 2026-04-29
findings_in_scope: critical_warning
findings_fixed: 5
findings_skipped: 0
status: all_fixed
---

# Phase 1: Code Review Fix Report

**Fix date:** 2026-04-29
**Scope:** critical + warning
**Status:** all_fixed

## Fixes Applied

### CR-01 — note_tidy.py: body_start safe default

**Files modified:** `note_tidy.py`
**Commit:** c3f6cd2
**Applied fix:** Changed `body_start = 0` to `body_start = len(lines)` on line 147 of `tidy_note_text`. When Claude returns a flags-only response (no body text follows the flag bullets), `lines[len(lines):]` evaluates to `[]` and `tidied` becomes `""` — correct empty body. The old default of `0` caused `"\n".join(lines[0:])` to reproduce the entire original response as the tidied body.

---

### WR-01 — email_watcher.py: bounded _processed_ids

**Files modified:** `email_watcher.py`
**Commit:** c3f6cd2
**Applied fix:** Added `from collections import deque` to imports. Replaced the bare `_processed_ids: set = set()` declaration with a `_MAX_PROCESSED = 2000` cap constant, a parallel `_processed_ids_order: deque = deque()`, and a `_track_processed(msg_id)` helper that evicts the oldest entry when the deque exceeds the cap. Replaced the bare `_processed_ids.add(msg_id)` call in the polling loop with `_track_processed(msg_id)`.

---

### WR-02 — email_watcher.py: credential error logging

**Files modified:** `email_watcher.py`
**Commit:** c3f6cd2
**Applied fix:** Added `logger.error("ANTHROPIC_API_KEY not set — cannot generate draft for '%s'", email.get("subject", ""))` immediately before the silent `return None, True` in `generate_draft`. Missing API key is now visible as an error in Railway logs rather than silently suppressing draft generation.

---

### WR-03 — email_watcher.py: mark_read failure logged

**Files modified:** `email_watcher.py`
**Commit:** c3f6cd2
**Applied fix:** Replaced `except Exception: pass` in the `mark_read` try/except block with `except Exception as exc: logger.warning("Failed to mark email '%s' as read: %s", subject, exc)`. Transient Gmail API failures on mark-as-read are now surfaced as warnings rather than silently swallowed.

---

### WR-04 — note_tidy.py: single get_unprocessed_notes call

**Files modified:** `note_tidy.py`
**Commit:** c3f6cd2
**Applied fix:** In `tidy_all_unprocessed`, captured the full result of `get_unprocessed_notes(creds)` into `all_unprocessed` at function entry, then sliced `all_unprocessed[:max_files]` for the processing loop. The `remaining` count in the return dict now uses `max(0, len(all_unprocessed) - len(results))` instead of calling `get_unprocessed_notes(creds)` a second time, eliminating the redundant Drive API round-trip.

---

## Skipped (Info — out of scope)

- IN-01: .gitignore client_secret*.json patterns — informational, no code change required
- IN-02: module-level Anthropic client — informational refactor suggestion, out of scope for this fix pass

## Commit

`c3f6cd2` — fix: apply phase 1 code review fixes (CR-01, WR-01 through WR-04)

---

_Fixed: 2026-04-29_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
