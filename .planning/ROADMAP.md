# Roadmap: Midwife Agent v1.0 — Foundation Hardening

## Overview

This milestone hardens the existing prototype before any new features land. Three phases deliver in dependency order: first remove dead weight from the repository (low risk, no running code touched), then lock down the live API surface (higher risk, live endpoints modified), then document everything that was done so the foundation is auditable going forward.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Codebase Cleanup** - Delete dead files, purge the binary blob, lock down .gitignore, centralise the model string
- [ ] **Phase 2: Security Hardening** - Add API key middleware, restrict CORS, protect OAuth callback, rotate exposed credentials
- [ ] **Phase 3: Documentation** - Write SECURITY.md and complete the README env var reference

## Phase Details

### Phase 1: Codebase Cleanup
**Goal**: The repository contains only live, intentional code — no stale patches, dead integrations, duplicate UI files, binary blobs, or inconsistent model strings
**Depends on**: Nothing (first phase)
**Requirements**: CLEAN-01, CLEAN-02, CLEAN-03, CLEAN-04, CLEAN-05, CLEAN-06
**Success Criteria** (what must be TRUE):
  1. `chat_endpoint_patch.py`, `consolidated_patch.py`, `outlook_integration.py`, and root `index.html` are absent from the working tree and do not appear in `git ls-files`
  2. `files.zip` has been inspected, its contents confirmed non-sensitive (or purged from git history if sensitive), and the file is no longer present in the repo
  3. `.gitignore` explicitly covers `.env`, `*.token`, `*.key`, `*.pem`, and common credential patterns; `git log --all -p` scan confirms no real credentials are in history
  4. A single `CLAUDE_MODEL` constant is read from the environment in `main.py`; `note_tidy.py` and `email_watcher.py` no longer contain their own hardcoded model string literals
**Plans**: 4 plans

Plans:
- [x] 01-01-PLAN.md — Delete dead patch files, outlook integration, root index.html duplicate
- [ ] 01-02-PLAN.md — Inspect and remove files.zip (with checkpoint for sensitivity decision)
- [ ] 01-03-PLAN.md — Centralise CLAUDE_MODEL env var in note_tidy.py and email_watcher.py
- [ ] 01-04-PLAN.md — Harden .gitignore with credential patterns and scan git history

### Phase 2: Security Hardening
**Goal**: Every live API endpoint requires a valid bearer token, the CORS policy admits only the intended origin, the OAuth callback no longer exposes credentials, and the previously exposed Google credentials have been replaced
**Depends on**: Phase 1
**Requirements**: SEC-01, SEC-02, SEC-03, SEC-04
**Success Criteria** (what must be TRUE):
  1. A `curl` request to any `/api/*` endpoint without an `Authorization: Bearer <token>` header returns HTTP 401; the same request with a valid token returns HTTP 200
  2. The CORS `allow_origins` list in `main.py` is set to the value of `ALLOWED_ORIGIN` env var (not `*`); a browser request from an unlisted origin is rejected with a CORS error
  3. The `/auth/google/callback` page renders a generic success message only — no token JSON, no textarea, no credentials visible in the page source or server logs
  4. Google OAuth credentials (client secret, access token, refresh token) have been rotated in Google Cloud Console and the new values are live in Railway env vars
**Plans**: TBD

### Phase 3: Documentation
**Goal**: Anyone picking up this codebase can understand how authentication works, what all environment variables do, and how to rotate credentials — without reading source code
**Depends on**: Phase 2
**Requirements**: DOC-01, DOC-02
**Success Criteria** (what must be TRUE):
  1. `SECURITY.md` exists at the repo root and documents: the Bearer token auth model, the CORS policy and how to configure it, the OAuth token handling approach, and step-by-step credential rotation instructions
  2. `README.md` contains an environment variable reference table covering all 11 required vars (`API_KEY`, `ALLOWED_ORIGIN`, `CLAUDE_MODEL`, `ANTHROPIC_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_TOKEN`, `GOOGLE_DRIVE_FOLDER_ID`, `GOOGLE_DRIVE_NOTES_FOLDER_ID`, `PORT`, `RAILWAY_PUBLIC_DOMAIN`)
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Codebase Cleanup | 1/4 | In progress | - |
| 2. Security Hardening | 0/TBD | Not started | - |
| 3. Documentation | 0/TBD | Not started | - |
