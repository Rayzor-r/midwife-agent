# Midwife Agent — Project Guide

## Project

**Midwife Agent v1.0 — Foundation Hardening**
See `.planning/PROJECT.md` for full context.

**Core value:** The agent reliably handles administrative and communication tasks for a working midwife — so that when a new feature or new client is added, there is a safe, auditable foundation to build on.

## GSD Workflow

This project uses the GSD workflow. Planning artifacts live in `.planning/`.

### Key files
- `.planning/STATE.md` — current position, blockers, decisions
- `.planning/ROADMAP.md` — 3-phase milestone plan
- `.planning/REQUIREMENTS.md` — 12 v1 requirements with traceability
- `.planning/PROJECT.md` — project context, constraints, key decisions
- `.planning/codebase/` — codebase map (STACK, ARCHITECTURE, CONCERNS, etc.)

### Current milestone
Foundation hardening — security, cleanup, documentation. **No new features.**

### Phase order
1. Codebase Cleanup (CLEAN-01 through CLEAN-06)
2. Security Hardening (SEC-01 through SEC-04)
3. Documentation (DOC-01, DOC-02)

### Commands
- `/gsd-plan-phase 1` — plan Phase 1
- `/gsd-execute-phase 1` — execute Phase 1 plans
- `/gsd-progress` — show current status
- `/gsd-discuss-phase <N>` — discuss and clarify a phase before planning

## Critical constraints

- **No new features this milestone** — hardening and cleanup only
- **Active testers on production** — any change breaking the chat endpoint or Google integrations is immediately felt; Phase 2 changes require careful testing before deploy
- **`files.zip` blocker** — must inspect contents before deletion; if sensitive data found, git history purge required (`git filter-repo` or BFG)
- **Railway deployment** — all secrets via Railway env vars; no filesystem persistence between redeploys

## Codebase notes

- Entry point: `main.py` (FastAPI app, all routes, tool-use loop)
- Frontend: `static/index.html` (canonical — root `index.html` is a stale duplicate, to be deleted in Phase 1)
- Integrations: `calendar_integration.py`, `gmail_integration.py`, `drive_integration.py`
- Background: `email_watcher.py` (polls Gmail every 120s, auto-drafts replies)
- Dead code (to be removed in Phase 1): `chat_endpoint_patch.py`, `consolidated_patch.py`, `outlook_integration.py`
