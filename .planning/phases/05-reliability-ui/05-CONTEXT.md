# Phase 5: Reliability and UI - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the email watcher accurately report its own liveness, recover from failure automatically, and surface failures clearly through the health endpoint and server logs. Add date+time timestamps to every chat message so the midwife can orient herself when scrolling back through conversation history. No new integrations, no new tools, no UI panels — reliability and polish only.

</domain>

<decisions>
## Implementation Decisions

### Chat message timestamps (UI-01)
- **D-01:** Timestamp format: "DD MMM, HH:MM" — e.g. "01 May, 13:30". No seconds. This format appears on every user and AI message immediately when the message is rendered.
- **D-02:** Use the browser's local timezone via `new Date().toLocaleString()` — not server time. The midwife's device clock is the reference, so the timestamp reflects when she was in the conversation, not UTC.
- **D-03:** The `now()` function in `static/index.html` currently returns HH:MM only. Update it to return "DD MMM, HH:MM". Both `appendUserMsg` and `appendAiMsg` already call `${now()}` in their `.msg-time` div — no structural changes to the message template needed.

### Thread liveness detection (GMAIL-01)
- **D-04:** Use Python's built-in `thread.is_alive()` to detect actual thread death — not the `_watcher_running` boolean flag (which stays `True` even after a crash).
- **D-05:** `start_watcher()` already returns the thread object. Store this reference at module level in `email_watcher.py` (e.g. `_watcher_thread: threading.Thread | None = None`) so `watcher_status()` can call `_watcher_thread.is_alive()`.
- **D-06:** Update `watcher_status()` to return `is_alive` based on `_watcher_thread.is_alive()` (not `_watcher_running`). This fixes the "running: True even when dead" bug.
- **D-07:** Merge watcher liveness into `/api/health` in `main.py` — add a `watcher_alive` key to the health response. The `/api/watcher/status` endpoint stays as a more detailed status endpoint.

### Failure handling and auto-restart (GMAIL-02)
- **D-08:** When `thread.is_alive()` returns False (thread has died), the system must: (a) log a WARNING with timestamp and any available exception info, (b) attempt automatic restart up to 3 times with exponential backoff — delays of 10s, 30s, 90s between attempts, (c) if all 3 restarts fail, log an ERROR and mark the watcher status as permanently dead.
- **D-09:** The liveness check and restart logic runs in a background checker — a lightweight periodic check (e.g. every 60s) in the FastAPI startup lifecycle, or a watchdog thread. This checker owns the restart loop, not the watcher thread itself.
- **D-10:** Failure is surfaced through: (1) server logs (WARNING/ERROR via Python `logging`) and (2) the `/api/health` endpoint (`watcher_alive: false`). The chat UI does NOT show watcher failures — this is operational information for the operator, not the midwife.
- **D-11:** Restart attempts use the same `start_watcher()` call as the original startup. After a successful restart, liveness returns to `True` and the retry counter resets.

### Claude's Discretion
- Exact structure of the watchdog (standalone thread vs periodic FastAPI background task)
- Whether to track restart count and last-restart-time in the status endpoint response
- Backoff implementation detail (threading.Event vs time.sleep in watchdog)

</decisions>

<specifics>
## Specific Ideas

- "The midwife may scroll back through chat history and need to know which day a conversation happened, not just the time" — date is essential, not decorative. The format "DD MMM, HH:MM" is compact enough to not dominate the UI but complete enough to anchor past conversations to a specific day.
- "thread.is_alive() answers the exact question 'is the watcher thread actually running right now'" — no extra infrastructure, no heartbeat timestamp, no secondary state to keep in sync.
- "Auto-restart AND surface the failure" — the midwife doesn't see it in chat; the operator monitors via `/api/health` and server logs (Railway log viewer).
- 3 restart attempts with 10s / 30s / 90s backoff — aggressive enough to recover from transient failures, not so aggressive it hammers a broken Gmail API.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 5 requirements
- `.planning/REQUIREMENTS.md` — UI-01, GMAIL-01, GMAIL-02 (three requirements, all in this phase)
- `.planning/ROADMAP.md` §Phase 5 — goal statement, three success criteria, plan assignments (05-01, 05-02)

### Email watcher (GMAIL-01, GMAIL-02)
- `email_watcher.py` — full file. `watch_inbox()`, `start_watcher()`, `stop_watcher()`, `watcher_status()`. D-05 adds `_watcher_thread` module-level var; D-06 changes `watcher_status()` return value; D-08/09 add restart logic.
- `main.py` lines 909–932 — `startup_event`, `get_watcher_status` endpoint, `stop_watcher_endpoint`. D-07 adds `watcher_alive` to health response; watchdog is also wired here.
- `main.py` lines 893–904 — `/api/health` endpoint. D-07 merges watcher liveness here.

### Chat timestamps (UI-01)
- `static/index.html` — `now()` function (line ~753), `appendUserMsg()` (line ~757), `appendAiMsg()` (line ~770), `.msg-time` CSS (line ~305). D-03 changes `now()` only — no structural changes to templates.

### Security constraint (carry-forward)
- `.planning/phases/02-security-hardening/02-CONTEXT.md` — Bearer token middleware. Any new `/api/*` routes must be protected. (No new routes expected in this phase, but the watchdog endpoint if added must comply.)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `email_watcher.py` → `start_watcher()`: already returns a `threading.Thread` — just store the return value at module level instead of discarding it.
- `email_watcher.py` → `watcher_status()`: already the pattern for returning status dicts — extend it with `is_alive` and restart metadata.
- `static/index.html` → `now()` (line ~753): single function to update for D-03; both message templates already call it.
- `main.py` → `/api/health` (line ~893): already aggregates system status — add `watcher_alive` key here.

### Established Patterns
- Module-level thread state: `_watcher_running`, `_processed_ids` in `email_watcher.py` — `_watcher_thread` follows the same pattern.
- Background thread launch: `start_watcher()` in `startup_event` (`main.py` line 916) — watchdog thread launched the same way.
- Status dict returns from `watcher_status()` — extend, don't replace; `/api/watcher/status` consumers won't break if new keys are added.

### Integration Points
- `email_watcher.py` module-level: add `_watcher_thread` variable, update `start_watcher()` to set it, update `watcher_status()` to call `_watcher_thread.is_alive()`.
- `main.py` `startup_event`: add watchdog thread launch alongside existing `start_watcher()` call.
- `main.py` `/api/health`: add `watcher_alive: bool` to the existing response dict.
- `static/index.html` `now()`: single-line change to date format string.

</code_context>

<deferred>
## Deferred Ideas

- Watcher failure notification in the chat UI (e.g. a banner saying "Email watcher is down") — not this phase; this is operational, not midwife-facing.
- Configurable poll interval or backoff values via env vars — Claude's discretion for now; hardcode sensible defaults.
- Watcher restart history exposed via a dedicated admin endpoint — future phase if needed.

</deferred>

---

*Phase: 05-reliability-ui*
*Context gathered: 2026-05-01*
