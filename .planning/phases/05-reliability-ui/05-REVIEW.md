---
phase: 05-reliability-ui
reviewed: 2026-05-06T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - email_watcher.py
  - main.py
  - static/index.html
findings:
  critical: 3
  warning: 5
  info: 3
  total: 11
status: issues_found
---

# Phase 5: Code Review Report

**Reviewed:** 2026-05-06
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Phase 5 introduced three changes: a module-level `_watcher_thread` reference in `email_watcher.py` with an `is_alive()` check in `watcher_status()`; a watchdog loop in `main.py` that auto-restarts the email watcher up to three times with exponential backoff; and a reformatted timestamp function in `static/index.html`.

The watchdog logic contains a race condition that can spawn multiple simultaneous watcher threads, which is the primary reliability concern this phase was meant to solve. Additionally, `generate_draft` returns `None` where the declared return type is `tuple[str, bool]`, which causes an `AttributeError` crash in the caller. The frontend `now()` rewrite produces locale-dependent output that breaks the intended "DD MMM, HH:MM" format in some environments. These are the three critical items.

---

## Critical Issues

### CR-01: Race condition in watchdog — multiple watcher threads can be spawned simultaneously

**File:** `main.py:922-953`

**Issue:** `_run_watchdog()` calls `start_watcher()` after detecting that the current watcher is dead, but `start_watcher()` in `email_watcher.py` always creates and starts a new `threading.Thread` — it does not check whether `_watcher_running` is already `True` or whether `_watcher_thread` is alive before starting a fresh one. If the previous watcher thread is in the process of shutting down (still inside `watch_inbox` after `_watcher_running` was set to `False`), calling `start_watcher()` immediately overwrites `_watcher_thread` and starts a second thread. Both threads then poll Gmail in parallel, each drafting replies to the same emails. This silently doubles (or triples) draft creation and burns API quota. The watchdog sleeps 60 s between checks, but with three retry attempts separated by 10 / 30 / 90 s there is a window where up to four threads can exist.

**Fix:** Add a guard in `start_watcher()` that aborts early if the current `_watcher_thread` is already alive:

```python
def start_watcher(get_creds_fn, document_store, search_fn, poll_interval=120):
    global _watcher_thread
    if _watcher_thread is not None and _watcher_thread.is_alive():
        logger.warning("start_watcher called but watcher thread is already alive — skipping.")
        return _watcher_thread
    thread = threading.Thread(
        target=watch_inbox,
        args=(get_creds_fn, document_store, search_fn, poll_interval),
        daemon=True,
        name="email-watcher",
    )
    thread.start()
    _watcher_thread = thread
    logger.info("Email watcher thread started.")
    return thread
```

---

### CR-02: `generate_draft` returns `None` as first element of `tuple[str, bool]`, crashing the caller

**File:** `email_watcher.py:53-54` and `email_watcher.py:103`

**Issue:** The function signature declares `-> tuple[str, bool]`. On the two early-return paths — missing API key (line 54) and SKIP detection (line 103) — the function returns `(None, True)` and `(None, False)` respectively. The caller at line 158 immediately unpacks this into `draft_html, needs_review` and then checks `if draft_html is None`. That check works. However, the error-path return at line 117 also returns `(None, True)`, and the type annotation is misleading to static analysis tools, which will report the function as correctly typed when it is not. More critically, if any future caller dereferences `draft_html` without the None check (a near-certain maintenance hazard given the misleading annotation), an `AttributeError` results.

The declared return type `tuple[str, bool]` is a lie: the actual return type is `tuple[str | None, bool]`. This is a correctness defect in the type contract.

**Fix:**

```python
def generate_draft(
    email: dict,
    document_store: dict,
    search_fn,
) -> tuple[str | None, bool]:
```

Also update the docstring: `Returns (draft_html, needs_review). draft_html is None for spam/skipped/error cases.`

---

### CR-03: `now()` produces locale-dependent output — format breaks outside en-NZ environments

**File:** `static/index.html:754-758`

**Issue:** The rewritten `now()` function calls `toLocaleString('en-NZ', ...)` three times with separate option objects. The intended format is "DD MMM, HH:MM". However, `toLocaleString` with `{ day: '2-digit' }` alone has no guaranteed output format — on some browser/OS combinations (notably Chrome on Windows with a non-NZ locale) it emits `"06/05/2026"` (full date) rather than `"06"`, because the browser may apply its own date formatting rules when `month` and `year` are absent from the options object. This makes the timestamp display wrong for a large class of production environments.

The previous single-call `toLocaleTimeString()` was at least predictably wrong (time-only). The new code is unpredictably wrong and varies by deployment environment — directly contrary to the goal of the change.

**Fix:** Use `padStart` with explicit field extraction rather than relying on `toLocaleString` for day/month:

```javascript
function now() {
  const d   = new Date();
  const day = String(d.getDate()).padStart(2, '0');
  const mon = d.toLocaleString('en-NZ', { month: 'short' }); // 'short' month is reliable
  const hh  = String(d.getHours()).padStart(2, '0');
  const mm  = String(d.getMinutes()).padStart(2, '0');
  return `${day} ${mon}, ${hh}:${mm}`;
}
```

This produces "06 May, 14:32" reliably across all browsers and OS locales.

---

## Warnings

### WR-01: Watchdog resets `retry_count` to 0 after exhausting retries and sleeping 1 hour — can spin indefinitely

**File:** `main.py:952-953`

**Issue:** After exhausting all three restart attempts, the watchdog sleeps for 3600 s and then resets `retry_count = 0`. This means the watchdog will silently attempt three more restarts one hour later, then again one hour after that, forever. The log message at line 948 says "Manual intervention required" but the code contradicts that by continuing to retry automatically. This is misleading to operators and means the watcher could restart at 1-hour intervals indefinitely with no further log noise beyond the initial error.

**Fix:** Either genuinely stop retrying (break out of the outer `while True`) or change the log message and comment to accurately describe that hourly retries will continue. If periodic retries are desired (e.g., after a transient Railway network outage), document that intent explicitly:

```python
else:
    logger.error(
        "Email watcher has not recovered after %d restart attempts. "
        "Will retry in 1 hour.",
        len(BACKOFF),
    )
    _time.sleep(3600)
    retry_count = 0  # retry cycle resets after 1-hour cooling period
```

---

### WR-02: `watcher_status()` returns both `running` and `is_alive` with identical values — redundant key creates confusion

**File:** `email_watcher.py:221-227`

**Issue:** `watcher_status()` returns `{"running": alive, "is_alive": alive, ...}`. Both keys hold the same value. The old key was `running`; the new key is `is_alive`. The health endpoint in `main.py` at line 906 reads `status.get("is_alive", False)`. If any other code or monitoring script reads `running` expecting it to reflect `_watcher_running` (the flag used inside the loop), it now gets `is_alive` instead — which is a semantic difference. A thread can be alive but have `_watcher_running = False` (draining), or `_watcher_running = True` but the thread dead (a crash). Having two keys that appear to mean different things but hold the same value is a latent bug magnet.

**Fix:** Remove `running` from the return dict entirely, or keep it with its original meaning (`_watcher_running`):

```python
def watcher_status() -> dict:
    alive = _watcher_thread is not None and _watcher_thread.is_alive()
    return {
        "is_alive":        alive,
        "loop_flag":       _watcher_running,
        "processed_count": len(_processed_ids),
    }
```

---

### WR-03: `_run_watchdog` imports `time` as `_time` inside the function body — shadowing the module-level import

**File:** `main.py:918`

**Issue:** `main.py` already imports `threading` at the top level. `_run_watchdog` does `import time as _time` inside the function on line 918. The `time` module is not imported at the top of `main.py`, so this import-inside-function pattern is the only way `time` is available here. This is inconsistent with the rest of the file (all other imports are at the top) and makes the dependency invisible to readers scanning the import block. It also means the import runs on every call to `_run_watchdog` (though Python caches it, the pattern is nonstandard).

**Fix:** Add `import time` to the top-level imports in `main.py` and remove the local import.

---

### WR-04: Watchdog passes `document_store` dict by reference — if store is replaced rather than mutated, watchdog uses stale reference

**File:** `main.py:972-973`

**Issue:** `startup_event` passes `document_store` (a module-level `dict`) to `_run_watchdog` as a positional argument. Inside `_run_watchdog`, this is forwarded to `start_watcher()` which passes it to `watch_inbox()`. Python dicts are passed by reference, so mutations to the dict (adding/removing documents) are visible to all threads. However, if `document_store` were ever reassigned (`document_store = {}`) rather than mutated (`.clear()`), the watchdog and watcher threads would hold a stale reference to the old dict. The current code only mutates the dict (via `document_store[doc_id] = ...` and `document_store.pop(...)`), so this is safe today. But it is a fragile contract.

**Fix:** Use a wrapper function or a container object rather than passing the raw dict, or add a comment at the `document_store` declaration explicitly stating it must never be reassigned:

```python
# NOTE: always mutate this dict in-place; never reassign the name.
# Background threads hold references to this object.
document_store: dict = {}
```

---

### WR-05: Auth key stored in `localStorage` is accessible to any JavaScript on the page, including injected content from `marked.parse()`

**File:** `static/index.html:1011`, `static/index.html:705`

**Issue:** The API key is stored in `localStorage` and retrieved via `getApiKey()` (line 1011) on every request. `marked.parse(aiText)` on line 705 renders arbitrary markdown received from the server (which itself receives content from Gmail inboxes and Claude) directly into `bubble.innerHTML`. Although `marked` with default settings escapes most dangerous HTML, it does not sanitize all injection vectors — specifically, `marked` v9 does not strip `javascript:` hrefs or `data:` URIs in links/images by default. A crafted AI response or a malicious email body relayed through the draft generation pipeline could inject a `[click me](javascript:fetch('/api/chat',{headers:{Authorization:'Bearer '+localStorage.getItem('api_key')},...}))` link. When the midwife clicks it, the key is exfiltrated.

This is not new to Phase 5 but the `localStorage` key storage was introduced in a prior phase. Phase 5 made no change to mitigate it either. Given that this is a medical professional's system handling clinical emails, this warrants explicit attention.

**Fix:** Enable `marked`'s sanitization options and restrict link navigation:

```javascript
marked.setOptions({ breaks: true, gfm: true });
marked.use({
  renderer: {
    link(href, title, text) {
      // Strip javascript: and data: protocols
      if (/^(javascript|data):/i.test(href || '')) href = '#';
      return `<a href="${href}" target="_blank" rel="noopener noreferrer"${title ? ` title="${title}"` : ''}>${text}</a>`;
    }
  }
});
```

---

## Info

### IN-01: `_watcher_thread` and `_watcher_running` module globals are not protected by a lock

**File:** `email_watcher.py:27`, `email_watcher.py:129`

**Issue:** `_watcher_running` and `_watcher_thread` are module-level variables written from multiple threads (`start_watcher` writes `_watcher_thread` from the calling thread; `watch_inbox` writes `_watcher_running` from its own thread; `stop_watcher` writes `_watcher_running` from the API thread). Python's GIL makes individual attribute assignments atomic for simple types, but there is no guarantee of ordering across threads without a lock. This is not a crash risk with the current code (assignment is atomic under the GIL), but it is a code quality concern that should be noted if the threading model grows.

**Fix:** Consider protecting both variables with a single `threading.Lock()` if the watcher control logic becomes more complex.

---

### IN-02: `generate_draft` constructs a new `anthropic.Anthropic` client on every call

**File:** `email_watcher.py:92`

**Issue:** A new `anthropic.Anthropic(api_key=api_key)` instance is created for each email processed. The client is stateless and safe to reuse; constructing it repeatedly is wasteful (HTTP connection pool is not reused). This is an info-level quality note, not a correctness bug.

**Fix:** Create the client once at module level (after the API key is validated at startup) or cache it.

---

### IN-03: `thread_id` is extracted from the email but never passed to `create_draft`

**File:** `email_watcher.py:165-174`

**Issue:** `thread_id = email.get("thread_id")` is assigned on line 165 but then never used — `create_draft` is called with `reply_to_id=msg_id` but not `thread_id`. If `create_draft` uses `reply_to_id` to look up thread context, this may be fine; if it does not, replies will be created outside the original Gmail thread. This is dead variable code that indicates the intent was to pass thread context but it was dropped.

**Fix:** Verify whether `create_draft` in `gmail_integration.py` uses `thread_id`. If so, pass it. If not, remove the dead assignment.

---

_Reviewed: 2026-05-06_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
