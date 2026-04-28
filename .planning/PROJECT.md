# Midwife Agent

## What This Is

An AI assistant for Lead Maternity Carers (LMCs) built on FastAPI and Claude, deployed on Railway. It handles midwife-specific workflows: booking appointments via Google Calendar, monitoring Gmail, syncing a RAG knowledge base from Google Drive, auto-drafting email replies, and tidying clinical shorthand notes. The prototype is live and connected to a real Google account, with a small group of colleagues and friends currently testing it.

## Core Value

The agent reliably handles administrative and communication tasks for a working midwife — so that when a new feature or new client is added, there is a safe, auditable foundation to build on.

## Requirements

### Validated

- ✓ Chat interface with Claude AI via streaming SSE — existing
- ✓ Gmail integration (list inbox, search, read email, create draft replies) — existing
- ✓ Google Calendar integration (list events, create/reschedule appointments, get availability, check conflicts) — existing
- ✓ Google Drive sync to RAG knowledge base (PDF/DOCX indexing, incremental updates) — existing
- ✓ Note tidying via Claude (LLM-powered shorthand formatter) — existing
- ✓ Email watcher (background thread, auto-draft replies on incoming mail) — existing
- ✓ Document upload and keyword-scored RAG retrieval — existing
- ✓ Deployed on Railway (Docker / Nixpacks, auto-restart on failure) — existing
- ✓ **CLEAN-01**: Stale patch files deleted — validated in Phase 1
- ✓ **CLEAN-02**: Dead Outlook integration removed — validated in Phase 1
- ✓ **CLEAN-03**: Binary blob (files.zip) inspected (SAFE — source code only) and removed — validated in Phase 1
- ✓ **CLEAN-04**: Duplicate root `index.html` deleted, canonical UI at `static/index.html` preserved — validated in Phase 1
- ✓ **CLEAN-05**: CLAUDE_MODEL centralised — `note_tidy.py` and `email_watcher.py` now read from `os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")` — validated in Phase 1
- ✓ **CLEAN-06**: `.gitignore` hardened with 7 credential patterns; git history scan clean — validated in Phase 1

### Active

- [ ] **SEC-01**: API key authentication middleware protecting all `/api/*` routes (shared secret via `Authorization: Bearer` header, stored in Railway env vars)
- [ ] **SEC-02**: CORS restricted to the specific Railway deployment origin — not wildcard `*`
- [ ] **SEC-03**: OAuth callback page does not render the raw token in HTML; token is written via Railway API or copied via a safer mechanism
- [ ] **SEC-04**: Google OAuth credentials reviewed and rotated given the token was previously exposed in the browser UI
- [ ] **DOC-01**: `SECURITY.md` created, documenting the auth model, CORS policy, OAuth token handling, and instructions for rotating credentials

### Out of Scope

- Midwife-specific knowledge base — GC Advisory KB stays; midwife KB is a future milestone
- Branding changes for midwife product identity — future milestone
- Practice Vitals seminar funnel integration — future milestone
- Multi-tenant support / per-client replication — future milestone
- Vector/semantic search — keyword RAG sufficient for now; revisit when KB grows
- Persistent document store — in-memory acceptable until multi-tenant is needed
- Outlook / Microsoft Graph integration — deferred indefinitely until there is a client who needs it
- New chat features or agent capabilities — no new features this milestone

## Context

- The agent is the prototype for a commercial product targeting LMC midwife practices in Northland, New Zealand
- First paid setup is scoped at NZD $4,500; marketing via a "Practice Vitals" seminar concept
- Domain context for the product: scope of practice awareness, Section 88 funding, Tikanga considerations, LMC-specific workflow patterns
- A small group of testers are live on the production deployment right now — any change that breaks authentication or the chat endpoint is immediately felt
- The codebase map (`.planning/codebase/CONCERNS.md`) has documented the specific issues driving this milestone

## Constraints

- **Compatibility**: No breaking changes to the chat endpoint or Google integrations — testers are active
- **Deployment**: Railway — all secrets via Railway env vars; no filesystem persistence between redeploys
- **Scope**: Zero new features this milestone — hardening and cleanup only
- **Security**: The production Railway URL is known; any unauthenticated endpoint is publicly reachable right now
- **Tech stack**: Python/FastAPI — no framework changes

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Bearer token auth (not session/login) | Single-user tool; a shared secret is sufficient and simple to implement without breaking the existing JS frontend | Pending — Phase 2 |
| CORS locked to Railway origin via env var | Avoids hardcoding; works in local dev if `ALLOWED_ORIGIN` is set to `http://localhost:8000` | Pending — Phase 2 |
| Model string centralised in `main.py` only | Avoid circular imports; `note_tidy.py` and `email_watcher.py` accept model as parameter or read from env | ✓ Done — Phase 1 (both files use `os.getenv`) |
| Inspect `files.zip` before deleting | May contain patient data or credentials — must confirm before removing from git history | ✓ Done — Phase 1 (SAFE: source code only, PATH A taken) |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-28 after Phase 1 completion*
