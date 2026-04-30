# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-30)

**Core value:** The agent saves a midwife meaningful time on every client encounter — especially note-writing — so that the $4,500 setup cost pays back within the first month of use.
**Current focus:** Milestone v2.0 — Phase 4: Clinical Notes Overhaul (ready to execute)

## Current Position

Phase: 4 of 6 (Clinical Notes Overhaul)
Plan: 3 plans ready (04-01, 04-02, 04-03)
Status: Ready to execute
Last activity: 2026-05-01 — Phase 4 planned (3 plans in 3 sequential waves, NOTES-01 through NOTES-05 covered)

Progress: [░░░░░░░░░░] 0% (v2.0)

## Performance Metrics

**Velocity:**
- Total plans completed: 10 (v1.0)
- Average duration: ~2.5 min
- Total execution time: ~25 min (est.)

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Codebase Cleanup | 4 | ~10 min | ~2.5 min |
| 2. Security Hardening | 4 | ~10 min | ~2.5 min |
| 3. Documentation | 2 | ~5 min | ~2.5 min |

**Recent Trend:**
- Last 5 plans: 01-01 (2 min), 01-02 (checkpoint), 01-03 (3 min), 01-04 (1 min), 02-01 (~3 min)
- Trend: stable

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Roadmap init: SOAP notes use no visible subheadings — continuous prose paragraphs, implicit SOAP structure
- Roadmap init: Glossary ships with seed list — usable before past notes are uploaded
- Roadmap init: Outlook MSAL auth for 3 accounts — tokens stored as Railway env vars (same pattern as GOOGLE_TOKEN)
- NOTES-01 + NOTES-02 are tightly coupled — same plan (04-01); glossary is required by the SOAP engine
- OUTLOOK-01 is a hard prerequisite for OUTLOOK-02/03/04 — plan 06-01 must complete before 06-02/03
- All new /api/* routes must be protected by existing Bearer token middleware (v1.0 carry-forward)
- `msal` must be declared in requirements.txt — undeclared dependency was the reason outlook_integration.py was deleted in Phase 1

### Pending Todos

None.

### Blockers/Concerns

- Active testers on production: any change that breaks the chat endpoint or Google integrations is immediately felt
- Phase 6 (Outlook) is the highest-risk phase — MSAL auth is net-new and involves external OAuth flow

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Cultural fluency | TEREO-01: te reo Maori term insertion | Deferred to v2.1 | v2.0 milestone start |
| Infrastructure | STORE-01: persistent document store | Deferred to v2.1 | v2.0 milestone start |
| Bug fixes | BUG-01, BUG-02, BUG-03 | Deferred to v2.1 | v2.0 milestone start |

## Session Continuity

Last session: 2026-05-01
Stopped at: Phase 4 context gathered. Key decisions: new notes_engine.py (note_tidy.py untouched), style-learning from full past-notes corpus (not rigid templates), glossary.json seed file, style profile cached in memory with lazy build + explicit refresh, referral letters follow same uploaded-examples-first principle.
Resume file: .planning/phases/04-notes-overhaul/04-CONTEXT.md
