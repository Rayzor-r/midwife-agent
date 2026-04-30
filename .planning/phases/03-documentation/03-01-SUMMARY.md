---
plan: 03-01
phase: 03-documentation
status: complete
completed: 2026-04-30
---

## Summary

Created `SECURITY.md` at the repo root documenting all security decisions from Phase 2 (SEC-01 through SEC-04).

## What was built

- **Section 1 — Bearer Token Authentication**: Documents `require_api_key` middleware, exempt routes (`/`, `/api/health`, `/auth/google`, `/auth/google/callback`), fail-closed behaviour, frontend overlay, and scope constraints.
- **Section 2 — CORS Policy**: Documents `ALLOWED_ORIGIN` env var, local dev default (`http://localhost:8000`), Railway configuration example, no-wildcard/no-trailing-slash rules.
- **Section 3 — OAuth Token Handling**: Documents Railway Logs delivery mechanism, 6-step token retrieval process, rationale for moving away from browser textarea.
- **Section 4 — Credential Rotation**: 7-step numbered runbook including the D-16 sequencing warning (deploy safe callback before rotating).
- **Related files table**: Cross-references `main.py`, `calendar_integration.py`, `static/index.html`, Phase 2 CONTEXT.md, and README.md.

## Key files

### Created
- `SECURITY.md` — 173 lines; four sections covering auth model, CORS, OAuth token handling, credential rotation

## Self-Check: PASSED

### Acceptance criteria
- [x] `SECURITY.md` exists at repo root
- [x] Verbatim phrase "API_KEY is functionally a shared password for the deployment" present (grep: 1)
- [x] Bearer Token Authentication section present (grep: 1)
- [x] All exempt routes listed including `/api/health` and `/auth/google/callback`
- [x] ALLOWED_ORIGIN documented (grep: 5 occurrences)
- [x] GOOGLE_TOKEN documented (grep: 7 occurrences)
- [x] Railway Deployments → Logs path documented
- [x] Step-by-step rotation runbook present, numbered 1-7 (grep: 13 numbered items)
- [x] D-16 sequencing warning present (SEC-03 must be deployed before rotating)
- [x] No real credentials embedded

### Deviations
None.
