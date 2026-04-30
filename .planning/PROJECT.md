# Midwife Agent

## What This Is

An AI assistant for Lead Maternity Carers (LMCs) built on FastAPI and Claude, deployed on Railway. It handles midwife-specific workflows: booking appointments via Google Calendar, monitoring Gmail and Outlook, syncing a RAG knowledge base from Google Drive, auto-drafting email replies, and generating clinical notes in SOAP format from bullet-point observations. The agent is live in production and being prepared for commercial sale at NZD $4,500 per midwife practice.

## Core Value

The agent saves a midwife meaningful time on every client encounter — especially note-writing — so that the $4,500 setup cost pays back within the first month of use.

## Current Milestone: v2.0 Sellable Feature Set

**Goal:** Deliver the clinical notes engine and supporting integrations that make the agent worth buying — SOAP formatting, template library, Outlook support, and a reliable email watcher.

**Target features:**
- Clinical notes overhaul: SOAP-structured paragraphs from bullet input, acronym glossary, 4 note templates, ACC/DHB-compatible output
- Chat UI timestamps: date/time on every message
- Outlook integration: 3 accounts, MSAL auth from scratch, read/search/draft
- Gmail watcher fixes: heartbeat check, accurate liveness status, resilience improvements

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
- ✓ **CLEAN-01 through CLEAN-06**: Codebase cleanup (dead files, model string, .gitignore) — validated Phase 1
- ✓ **SEC-01 through SEC-04**: Auth middleware, CORS, OAuth callback safety, credential rotation — validated Phase 2
- ✓ **DOC-01, DOC-02**: SECURITY.md and README.md — validated Phase 3

### Active

- [ ] **NOTES-01**: Clinical SOAP note generation from bullet-point input
- [ ] **NOTES-02**: Midwife acronym glossary with expansion in generated notes
- [ ] **NOTES-03**: Note template library (4 templates: initial booking, routine antenatal, postnatal check, referral letter)
- [ ] **NOTES-04**: Template inference — agent selects template from input content or user picks explicitly
- [ ] **NOTES-05**: Note output format compatible with ACC and NZ DHB LMC documentation expectations
- [ ] **UI-01**: Chat message timestamps (date and time visible on each message)
- [ ] **GMAIL-01**: Email watcher heartbeat — status endpoint reflects actual thread liveness
- [ ] **GMAIL-02**: Email watcher resilience — surfaces thread failures visibly and/or auto-restarts
- [ ] **OUTLOOK-01**: Connect up to 3 Microsoft Outlook accounts via MSAL OAuth (rebuilt from scratch)
- [ ] **OUTLOOK-02**: Read and list email from connected Outlook accounts
- [ ] **OUTLOOK-03**: Search email across connected Outlook accounts
- [ ] **OUTLOOK-04**: Draft email replies for messages in connected Outlook accounts

### Out of Scope

- Midwife-specific knowledge base — GC Advisory KB stays; dedicated midwife KB is a future milestone
- Branding changes for midwife product identity — future milestone
- Practice Vitals seminar funnel integration — future milestone
- Multi-tenant support / per-client replication — future milestone (requires v2.1+ persistent store first)
- Vector/semantic search — keyword RAG sufficient; revisit when KB grows
- Per-user API keys / staff accounts — v2.0 stays single-user Bearer token model

## Context

- The agent is the prototype for a commercial product targeting LMC midwife practices in Northland, New Zealand
- First paid setup is scoped at NZD $4,500; marketing via a "Practice Vitals" seminar concept
- Domain context: scope of practice awareness, Section 88 funding, Tikanga considerations, LMC-specific workflow patterns (SOAP note format is standard for NZ DHB/ACC documentation)
- Active testers on production — any change that breaks authentication, the chat endpoint, or Google integrations is immediately felt
- Te reo Maori term insertion and persistent document store are v2.1 scope — style guide and store architecture will be defined then
- Three Outlook accounts belong to the same midwife (personal, clinic, or shared variants) — all need read/search/draft parity with Gmail

## Constraints

- **Compatibility**: No breaking changes to the chat endpoint or Google integrations — testers are active
- **Deployment**: Railway — all secrets via Railway env vars; no filesystem persistence between redeploys (until v2.1 persistent store)
- **Tech stack**: Python/FastAPI backend; vanilla JS frontend (`static/index.html`) — no framework changes
- **Security**: All API routes protected by Bearer token middleware from v1.0 — new routes must also be protected
- **MSAL dependency**: `outlook_integration.py` was deleted in v1.0 (undeclared msal dependency) — Outlook rebuild must declare `msal` in `requirements.txt` and implement auth cleanly

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Bearer token auth (not session/login) | Single-user tool; a shared secret is sufficient | ✓ Done — Phase 2 |
| CORS locked to Railway origin via env var | Avoids hardcoding; works in local dev | ✓ Done — Phase 2 |
| Model string centralised in `main.py` only | Avoid circular imports | ✓ Done — Phase 1 |
| Inspect `files.zip` before deleting | May contain patient data | ✓ Done — Phase 1 (SAFE) |
| SOAP notes: no visible subheadings | ACC/DHB expected format uses continuous prose paragraphs; implicit structure only | — Pending Phase 4 |
| Glossary ships with seed list | Real past notes will be uploaded later to expand; v2.0 must be useful before upload | — Pending Phase 4 |
| Outlook: MSAL auth for 3 accounts | Same read/search/draft capability as Gmail; tokens stored as Railway env vars like GOOGLE_TOKEN | — Pending Phase 6 |

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
*Last updated: 2026-04-30 after v2.0 milestone start*
