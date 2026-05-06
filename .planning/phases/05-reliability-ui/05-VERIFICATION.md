---
phase: 05-reliability-ui
verified: 2026-05-06T00:00:00Z
status: passed
score: 3/3 must-haves verified
overrides_applied: 0
---

# Phase 5: Reliability and UI Verification Report

**Phase Goal:** The email watcher accurately reports its own liveness, failures are visible rather than silent, and every chat message shows when it was sent
**Verified:** 2026-05-06
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Each chat message in the UI shows a timestamp (date and time) at the moment it was sent — visible without hovering or expanding | VERIFIED | `static/index.html` line 753: `now()` returns "DD MMM, HH:MM"; lines 769 and 801: both `appendUserMsg` and `appendAiMsg` embed `${now()}` in `.msg-time` div; `.msg-time` CSS (line 305) always visible |
| 2 | `/api/health` returns accurate watcher_alive: false when watcher thread has died — "running: True even when dead" behaviour is gone | VERIFIED | `email_watcher.py` line 225: `alive = _watcher_thread is not None and _watcher_thread.is_alive()`; `main.py` line 907: `"watcher_alive": status.get("is_alive", False)` in health response |
| 3 | When the watcher thread fails, the failure is visible within one poll cycle — no full application restart required to detect | VERIFIED | `main.py` lines 913-954: `_run_watchdog()` sleeps 60s between checks, logs WARNING per attempt and ERROR after exhaustion; watchdog launched as daemon in `startup_event` (line 970); auto-restart attempted up to 3 times with 10s/30s/90s backoff |

**Score:** 3/3 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `email_watcher.py` | Module-level `_watcher_thread` var, `is_alive()` liveness, updated `watcher_status()` | VERIFIED | Line 27: `_watcher_thread: threading.Thread \| None = None`; line 212: assignment after `thread.start()`; lines 224-230: `watcher_status()` returns both `running` and `is_alive` keys from `_watcher_thread.is_alive()` |
| `main.py` | `_run_watchdog()` function, watchdog thread in `startup_event`, `watcher_alive` in `/api/health` | VERIFIED | Lines 913-954: `_run_watchdog()` with `BACKOFF = [10, 30, 90]`; lines 970-977: daemon thread launched in `startup_event`; line 907: `watcher_alive` in health response |
| `static/index.html` | Updated `now()` returning DD MMM, HH:MM format | VERIFIED | Lines 753-760: `now()` uses `getDate().padStart`, `toLocaleString` for month, `getHours/getMinutes` with `padStart`; produces "01 May, 13:30" format |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `email_watcher.py` | `_watcher_thread.is_alive()` | `watcher_status()` calls `is_alive()` | WIRED | Line 225: `_watcher_thread is not None and _watcher_thread.is_alive()` |
| `main.py startup_event` | watchdog thread | `threading.Thread(target=_run_watchdog, ...)` | WIRED | Lines 970-976: Thread created with `target=_run_watchdog`, `.start()` called |
| `main.py /api/health` | `watcher_status()` | `watcher_alive` key sourced from `status.get("is_alive", False)` | WIRED | Line 898: `status = watcher_status()`; line 907: `"watcher_alive": status.get("is_alive", False)` |
| `static/index.html now()` | `appendUserMsg()` `.msg-time` div | `${now()}` template literal | WIRED | Line 769: `<div class="msg-time">${now()}</div>` |
| `static/index.html now()` | `appendAiMsg()` `.msg-time` div | `${now()}` template literal | WIRED | Line 801: `<div class="msg-time">${now()}</div>` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `static/index.html now()` | timestamp string | `new Date()` browser clock | Yes — live at render time | FLOWING |
| `main.py /api/health` | `watcher_alive` | `_watcher_thread.is_alive()` OS thread check | Yes — real thread state | FLOWING |

### Behavioral Spot-Checks

Step 7b: SKIPPED — requires running the FastAPI server and a browser; server startup with Google credentials is not testable without Railway environment. Key behaviors verified statically via code inspection.

The logic paths are clear from the code:
- `_watcher_thread.is_alive()` returns the OS-level thread liveness — cannot return a stale cached value
- `${now()}` is called at message-append time — cannot return a pre-cached stale timestamp
- `BACKOFF = [10, 30, 90]` and `retry_count < len(BACKOFF)` enforce exactly 3 restart attempts

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| GMAIL-01 | 05-01 | Email watcher status endpoint reports accurate thread liveness | SATISFIED | `/api/health` returns `watcher_alive` from `_watcher_thread.is_alive()` — stale boolean eliminated |
| GMAIL-02 | 05-01 | Failure visible to operator; thread auto-restarts or provides clear signal | SATISFIED | Watchdog logs WARNING per restart attempt and ERROR after 3 failures; `watcher_alive: false` persists in `/api/health` |
| UI-01 | 05-02 | Each chat message displays a timestamp showing date and time it was sent | SATISFIED | `now()` returns "DD MMM, HH:MM"; both message templates call `${now()}` in always-visible `.msg-time` div |

All three requirements mapped to Phase 5 in REQUIREMENTS.md are satisfied. No orphaned requirements for this phase.

### Implementation Deviation (Not a Blocker)

The 05-02 PLAN specified updating `now()` using three separate `toLocaleString()` calls (for day, month, and time). The actual implementation uses `getDate().padStart(2, '0')`, a single `toLocaleString` for month only, and `getHours/getMinutes` with `padStart`. The output format "01 May, 13:30" is identical to the spec. The alternative approach is more portable — it avoids locale-specific separator artifacts that can appear in `toLocaleString` when formatting date parts. Goal truth is fully met; the deviation is in implementation technique, not outcome.

The PLAN acceptance criterion "grep returns exactly 3 lines for toLocaleString" is not met (1 line found). This does not affect goal achievement and is documented here for transparency.

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| None detected | — | — | — |

No TODO/FIXME/placeholder comments, empty handlers, or stub returns found in the modified files (`email_watcher.py`, `main.py`, `static/index.html`).

Notable design check: `_run_watchdog()` resets `retry_count = 0` after a successful `start_watcher()` call. If the newly started thread dies immediately (before the next 60s watchdog check), the watchdog will detect the death and begin a fresh 3-attempt cycle. This means in a pathological crash-on-start scenario, the watchdog can retry more than 3 total times across cycles. However, the 1-hour sleep-then-reset pattern in the exhaustion branch prevents tight restart loops. This is acceptable behavior per the threat model (T-05-02).

### Human Verification Required

None. All three success criteria can be confirmed from static code inspection alone. Visual appearance of timestamps in the chat UI would require a browser test, but the wiring is unambiguous — the `.msg-time` div is always rendered as part of the message template with no toggle, no hover state, and no conditional rendering.

---

_Verified: 2026-05-06_
_Verifier: Claude (gsd-verifier)_
