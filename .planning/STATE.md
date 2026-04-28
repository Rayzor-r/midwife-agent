# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-28)

**Core value:** The agent reliably handles administrative and communication tasks for a working midwife — so that when a new feature or new client is added, there is a safe, auditable foundation to build on.
**Current focus:** Phase 2 — Security Hardening

## Current Position

Phase: 2 of 3 (Security Hardening)
Plan: 0 of 4 in current phase — ready to execute
Status: Ready to execute — 4 plans across 3 waves
Last activity: 2026-04-29 — Phase 2 planned; 4 plans created (02-01 through 02-04) covering SEC-01 through SEC-04

Progress: [████░░░░░░] 33%

## Performance Metrics

**Velocity:**
- Total plans completed: 4
- Average duration: 2 min
- Total execution time: ~10 min (est.)

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Codebase Cleanup | 4 | ~10 min | ~2.5 min |

**Recent Trend:**
- Last 5 plans: 01-01 (2 min), 01-02 (checkpoint), 01-03 (3 min), 01-04 (1 min)
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
- 01-02: files.zip inspection result: SAFE — contained only source code snapshots (main.py, calendar_integration.py, outlook_integration.py, drive_integration.py, requirements.txt); no credentials or patient data; removed via normal git rm (PATH A); no history purge or force-push required
- 01-04: Git history scan returned clean (no credentials found) — SEC-04 rotation not urgently required due to history leak, but still recommended given prior browser UI exposure

### Pending Todos

None yet.

### Decisions (Phase 2 additions)

- 02-discuss: API_KEY is a shared deployment password (memorable phrase), not a random hex string — one per practice, v2.0 concern for per-user keys
- 02-discuss: Frontend auth = full-screen password overlay (localStorage, type=password), "Sign out" corner link
- 02-discuss: 401 → clear localStorage + re-show overlay; network failure → distinct "can't reach server" message
- 02-discuss: SEC-03 = server-log token delivery (no textarea in callback page); SEC-03 must deploy before SEC-04
- 02-discuss: /api/health exempt from auth middleware; all other /api/* routes protected
- 02-discuss: email_watcher.py calls Google directly — does NOT go through /api/* — no auth change needed there

### Blockers/Concerns

- Active testers on production: any change that breaks the chat endpoint or Google integrations is immediately felt — Phase 2 changes must be tested carefully before deploy
- SEC-04 requires human action in Google Cloud Console (credential rotation) — cannot be fully automated

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-04-29
Stopped at: Phase 2 context gathered — 18 implementation decisions locked, CONTEXT.md written.
Resume file: .planning/phases/02-security-hardening/02-CONTEXT.md
