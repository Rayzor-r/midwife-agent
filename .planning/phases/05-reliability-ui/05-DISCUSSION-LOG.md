# Phase 5: Reliability and UI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in 05-CONTEXT.md — this log preserves the discussion.

**Date:** 2026-05-01
**Phase:** 05-reliability-ui
**Mode:** discuss (default)
**Areas discussed:** Timestamp format, Thread liveness detection, Failure handling

---

## Pre-discussion codebase findings

- Timestamps already partially implemented: `now()` returns HH:MM, `.msg-time` CSS is visible, both `appendUserMsg` and `appendAiMsg` call `${now()}`. Gap: time-only vs date+time.
- `_watcher_running` flag is the known "running: True even when dead" bug — it's set in-thread and never cleared on crash.
- `/api/health` does not include watcher status; liveness is on a separate `/api/watcher/status` endpoint.
- `start_watcher()` returns the thread object but the return value is discarded in `startup_event`.

---

## Area 1: Timestamp format (UI-01)

**Question:** Current `now()` shows HH:MM only. Requirement says "date and time". What format and scope?

**User decision:** "DD MMM, HH:MM" (e.g. "01 May, 13:30"). No seconds. Browser local timezone. Date is essential — midwives scroll back through chat history and need to know which day a conversation happened, not just the time.

---

## Area 2: Thread liveness detection (GMAIL-01)

**Question:** How should the status endpoint detect actual thread death? `thread.is_alive()` vs heartbeat timestamp.

**User decision:** `thread.is_alive()` — built into Python, no extra infrastructure, answers the exact question directly. Heartbeat timestamp adds complexity (needs a checker loop) for no real benefit at this scale.

---

## Area 3: Failure handling (GMAIL-02)

**Question:** When the watcher thread dies — auto-restart, or surface the failure, or both?

**User decision:** Both — auto-restart AND surface. Specifics: log WARNING on death, attempt restart up to 3 times with exponential backoff (10s, 30s, 90s), log ERROR and mark as permanently dead if all 3 fail. Surface via `/api/health` and server logs only — not in the chat UI. Operator-facing, not midwife-facing.

---

## Claude's discretion items

- Exact structure of the watchdog (standalone thread vs periodic FastAPI background task)
- Whether to expose restart count and last-restart-time in status response
- Backoff implementation detail
