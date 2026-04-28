---
phase: 01-codebase-cleanup
reviewed: 2026-04-28T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - note_tidy.py
  - email_watcher.py
  - .gitignore
findings:
  critical: 1
  warning: 4
  info: 2
  total: 7
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-04-28
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Three files were reviewed: `note_tidy.py`, `email_watcher.py`, and `.gitignore`. The two
Python changes (`os.getenv` replacements) are correct and achieve their intent. The
`.gitignore` additions are appropriate and exhaustive for the credential types in use.

However, pre-existing defects in both Python files were exposed under standard-depth
analysis. One critical bug causes silent data corruption in `note_tidy.py` when the
model produces a "Flags for review" section: the body of the note is silently replaced
with the full original response (including the flags header) whenever the loop completes
without finding a non-flag line. Additionally, `email_watcher.py` carries four
quality/robustness issues that have operational consequences in a production polling
loop, including an unbounded memory leak and a silent credential-fall-through that
returns `None` without logging.

---

## Critical Issues

### CR-01: Flag parser leaves `body_start=0` when all remaining lines are flag bullets — note body is never stripped

**File:** `note_tidy.py:147-156`

**Issue:** `body_start` is initialised to `0` and is only updated inside the `if` branch
that fires when a non-flag, non-empty line is found (i.e., the first line of the note
body). If the model produces a flags section where every remaining line after the header
is a flag bullet (e.g., the note has only flags and no body), the loop ends without ever
setting `body_start` to a non-zero value. The result is:

```python
tidied = "\n".join(lines[0:]).strip()   # entire original response, including "Flags for review:" header
```

The returned `tidied` field then contains the full, un-stripped response — including the
flags header that was supposed to be removed. The `flags` list is populated correctly,
so the UI receives both a correct `flags` list *and* a `tidied` string that still
contains the flags header. Any edge case where the model produces flags without a
subsequent note body (e.g., an empty or unrecognised note) triggers this silently.

A second related bug: blank lines between flag bullets are silently swallowed by the
`if line.strip():` guard on line 153, but the termination condition on line 149 also
fires on the first non-bullet, non-empty line — meaning a flag written without a leading
`-` or `•` (e.g., plain prose as a flag) is incorrectly treated as the start of the
body and is silently dropped from both `flags` and `tidied`.

**Fix:**
```python
if tidied.lower().startswith("flags for review"):
    lines = tidied.split("\n")
    flag_lines = []
    body_start = len(lines)          # safe default: no body found
    for i, line in enumerate(lines[1:], start=1):
        stripped = line.strip()
        if stripped and not stripped.startswith("-") and not stripped.startswith("•"):
            body_start = i
            break
        if stripped:
            flag_lines.append(stripped.lstrip("-• ").strip())
    flags = flag_lines
    tidied = "\n".join(lines[body_start:]).strip()
```

Setting `body_start = len(lines)` means that when no body is found, `lines[len(lines):]`
is an empty list, so `tidied` becomes `""` — which is the correct result for a
flags-only response. The `.strip()` call on `line` is also applied consistently before
the bullet check so that leading-space bullets are not misclassified as body text.

---

## Warnings

### WR-01: `_processed_ids` set grows without bound — unbounded memory leak in long-running process

**File:** `email_watcher.py:22, 135`

**Issue:** Every email message ID ever seen is added to `_processed_ids` (line 135) and
is never evicted. On Railway (where the process may run for weeks without a redeploy),
this set will accumulate every message ID the inbox has ever contained. For an active
inbox with years of history and 10 emails fetched per poll every 2 minutes, the set
could grow to tens of thousands of entries. There is no cap, no TTL, and no eviction.

This is also logically unnecessary: Gmail's `is:unread` filter is the primary
deduplication mechanism. The in-memory set only protects against re-processing a
message that was fetched as unread but not yet marked read within the same poll window.
A bounded structure (e.g., a capped deque or LRU cache of the last N IDs) would be
sufficient and correct.

**Fix:**
```python
from collections import deque

_MAX_PROCESSED = 2000
_processed_ids: set = set()
_processed_ids_order: deque = deque()

def _track_processed(msg_id: str):
    if msg_id not in _processed_ids:
        _processed_ids.add(msg_id)
        _processed_ids_order.append(msg_id)
        if len(_processed_ids_order) > _MAX_PROCESSED:
            old = _processed_ids_order.popleft()
            _processed_ids.discard(old)
```

Replace the bare `_processed_ids.add(msg_id)` call on line 135 with
`_track_processed(msg_id)`.

---

### WR-02: `generate_draft` returns `(None, True)` silently when API key is missing — caller logs "Skipping (spam/automated)" for a credential failure

**File:** `email_watcher.py:37-39, 146`

**Issue:** When `ANTHROPIC_API_KEY` is not set, `generate_draft` returns `(None, True)`
without logging anything (lines 37-39). The caller at line 145-147 then logs the
misleading message `"Skipping email (spam/automated or generation failed)"`. A missing
credential is not a spam classification — it is a configuration error. In production,
this means every email is silently skipped with a misleading log message, and the
midwife would not know the watcher is inoperative.

**Fix:**
```python
api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    logger.error("ANTHROPIC_API_KEY not set — cannot generate draft for '%s'",
                 email.get("subject", ""))
    return None, True
```

Add the log call inside `generate_draft` before returning, so the error is visible in
Railway logs regardless of how the caller handles the return value.

---

### WR-03: `mark_read` failure is silently swallowed — email will be re-processed on the next poll

**File:** `email_watcher.py:168-171`

**Issue:** The bare `except Exception: pass` block on lines 168-171 discards all
information about `mark_read` failures. If `mark_read` raises (e.g., a transient
network error or a Gmail API quota error), the email will not be marked as read, and
the next poll will fetch it again as unread. The in-memory `_processed_ids` guard will
prevent re-drafting within the same process lifetime, but after a Railway redeploy (or
process restart), the email will be re-processed and a duplicate draft will be created.

**Fix:**
```python
try:
    mark_read(creds, msg_id)
except Exception as exc:
    logger.warning("Failed to mark email '%s' as read: %s", subject, exc)
```

Log the failure at WARNING level. The email should still be added to `_processed_ids`
before `mark_read` is called (which the current code does correctly at line 135) to
avoid re-drafting in the current session.

---

### WR-04: `tidy_all_unprocessed` calls `get_unprocessed_notes` twice — second call races against first and inflates `remaining` count

**File:** `note_tidy.py:194, 209`

**Issue:** `tidy_all_unprocessed` calls `get_unprocessed_notes(creds)` once at line 194
to get the files to process, and then calls it again at line 209 to compute `remaining`.
Both calls make live Drive API requests. Between the two calls, files may be added,
removed, or modified, making the `remaining` count unreliable. More practically, if the
Drive API quota is tight or the folder is large, the second call doubles the API traffic
per batch run. The total count before slicing is available at the first call and should
be captured then.

**Fix:**
```python
def tidy_all_unprocessed(creds: Credentials, max_files: int = 10) -> dict:
    all_unprocessed = get_unprocessed_notes(creds)
    files = all_unprocessed[:max_files]
    results, errors = [], []

    for f in files:
        try:
            result = tidy_note_file(creds, f["id"], f["name"], f["mimeType"])
            results.append(result)
            mark_processed(f["id"], f.get("modifiedTime", ""))
        except Exception as e:
            errors.append({"file": f["name"], "error": str(e)})

    return {
        "processed": len(results),
        "results":   results,
        "errors":    errors,
        "remaining": max(0, len(all_unprocessed) - len(results)),
    }
```

---

## Info

### IN-01: `.gitignore` does not cover `*.json` broadly — `service_account*.json` and OAuth client secret files remain committable

**File:** `.gitignore:29`

**Issue:** The new entries cover `token.json`, `google_token.json`, and
`credentials.json` by exact name. The Google OAuth flow commonly produces files with
other names (e.g., `client_secret_<id>.json`, `oauth_credentials.json`, or any name the
developer chooses when downloading from Google Cloud Console). A developer who saves
an OAuth client secret as `my_credentials.json` or `client_secret.json` will not be
protected. This is a defence-in-depth gap, not an immediate vulnerability (no such
files exist in the repo today), but it is an easy miss during local dev.

**Fix:** Add a pattern that covers the common Google-generated client secret filename
prefix:
```
client_secret*.json
service_account*.json
```

Note: A blanket `*.json` rule would be too broad (it would ignore `package.json` and
similar project files). The two targeted patterns above cover the Google-specific risk
without over-ignoring.

---

### IN-02: `tidy_note_text` creates a new `anthropic.Anthropic` client on every call — client should be module-level or passed in

**File:** `note_tidy.py:128`

**Issue:** A new `anthropic.Anthropic(api_key=api_key)` client is instantiated inside
`tidy_note_text` on every invocation. The `ANTHROPIC_API_KEY` env var is also read
on every call (line 121). For a batch of 10 notes, this creates 10 clients and 10
`os.getenv` calls. While not a correctness issue, it is an unnecessary pattern that
costs connection pool initialisation overhead per note. The same issue exists in
`email_watcher.py` line 77.

**Fix:** Create the client once at module level (after confirming the key is present at
startup), or accept it as a parameter:
```python
# At module level in note_tidy.py
def _get_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")
    return anthropic.Anthropic(api_key=api_key)
```

This is flagged as Info because it has no correctness impact, only readability and
minor startup cost.

---

_Reviewed: 2026-04-28_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
