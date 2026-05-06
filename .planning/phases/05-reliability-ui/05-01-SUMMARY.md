---
plan: "05-01"
phase: 5
name: "Email Watcher Heartbeat and Resilience"
status: complete
requirements_satisfied:
  - GMAIL-01
  - GMAIL-02
---

## What Was Built

Fixed the email watcher's false liveness reporting and added a watchdog daemon that auto-restarts the watcher on failure.

**email_watcher.py:**
- Added `_watcher_thread: threading.Thread | None = None` module-level variable
- `start_watcher()` now stores the thread reference in `_watcher_thread` after `thread.start()`
- `watcher_status()` rewritten to use `_watcher_thread.is_alive()` — returns both `running` (compat) and `is_alive` (new explicit key)
- The "running: True even when dead" bug is eliminated at the source

**main.py:**
- Added `import threading` to stdlib imports
- Added `_run_watchdog()` function: checks liveness every 60s, auto-restarts up to 3 times with `BACKOFF = [10, 30, 90]` seconds, logs WARNING per attempt and ERROR after exhaustion, sleeps 3600s before next retry cycle
- `startup_event()` now launches a watchdog daemon thread (`email-watcher-watchdog`)
- `/api/health` now includes `watcher_alive` key (boolean, sourced from `watcher_status()["is_alive"]`)
- `/api/health` remains in `EXEMPT_PATHS` — no auth required for Railway health checks

## Key Files

### key-files.created
- `email_watcher.py` — updated liveness tracking, `_watcher_thread` module var
- `main.py` — `_run_watchdog()` function, watchdog thread in startup, `watcher_alive` in health

### key-files.modified
- `email_watcher.py`
- `main.py`

## Commits

- `fix(05-01)`: track _watcher_thread and fix watcher_status() liveness
- `feat(05-01)`: add watchdog thread and watcher_alive to /api/health

## Self-Check: PASSED

- ✓ `_watcher_thread` declared at module level in email_watcher.py
- ✓ `start_watcher()` stores thread reference globally
- ✓ `watcher_status()` returns `is_alive` from `_watcher_thread.is_alive()`
- ✓ `_run_watchdog()` defined with `BACKOFF = [10, 30, 90]`
- ✓ Max 3 restart attempts (`retry_count < len(BACKOFF)`)
- ✓ Watchdog daemon thread launched in `startup_event`
- ✓ `/api/health` includes `watcher_alive` key
- ✓ No new `/api/*` routes added
- ✓ `/api/health` remains in EXEMPT_PATHS
- ✓ GMAIL-01 satisfied: `/api/health` returns accurate `watcher_alive` — no more false "running: True when dead"
- ✓ GMAIL-02 satisfied: failure visible within one watchdog cycle (60s), auto-restart with backoff up to 3 times
