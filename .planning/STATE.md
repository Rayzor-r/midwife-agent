# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-28)

**Core value:** The agent reliably handles administrative and communication tasks for a working midwife — so that when a new feature or new client is added, there is a safe, auditable foundation to build on.
**Current focus:** Phase 1 — Codebase Cleanup

## Current Position

Phase: 1 of 3 (Codebase Cleanup)
Plan: 3 of 4 in current phase
Status: Executing
Last activity: 2026-04-28 — 01-03 complete: centralised CLAUDE_MODEL env var in note_tidy.py and email_watcher.py (CLEAN-05)

Progress: [███░░░░░░░] 23%

## Performance Metrics

**Velocity:**
- Total plans completed: 3
- Average duration: 3 min
- Total execution time: 9 min (est.)

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Codebase Cleanup | 3 | ~9 min | ~3 min |

**Recent Trend:**
- Last 5 plans: 01-01 (2 min), 01-02 (checkpoint), 01-03 (3 min)
- Trend: stable

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Roadmap init: Bearer token auth chosen (not session/login) — single shared secret sufficient for single-user tool
- Roadmap init: CORS locked to Railway origin via `ALLOWED_ORIGIN` env var — avoids hardcoding, works locally
- Roadmap init: Model string centralised in `main.py` only — avoid circular imports; consumers accept model as parameter or read from env
- Roadmap init: Inspect `files.zip` before deleting — may contain patient data or credentials
- 01-01: outlook_integration.py inspected before deletion — no embedded credentials found, uses only env vars (MS_CLIENT_ID, MS_CLIENT_SECRET, MS_TENANT_ID, OUTLOOK_TOKEN); safe to delete without git history purge
- 01-01: Root index.html confirmed stale (32 KB) vs canonical static/index.html (40 KB) — different sizes prove it is an outdated duplicate
- 01-03: Default fallback "claude-sonnet-4-5" used in both modules to match main.py — aligns all three Anthropic callers under one env var

### Pending Todos

None yet.

### Blockers/Concerns

- Active testers on production: any change that breaks the chat endpoint or Google integrations is immediately felt — Phase 2 changes must be tested carefully before deploy
- `files.zip` contents unknown — must inspect before delete; if sensitive, git history purge required (git filter-repo / BFG)

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-04-28
Stopped at: Completed 01-03-PLAN.md — CLAUDE_MODEL env var centralised in note_tidy.py and email_watcher.py (CLEAN-05)
Resume file: None
