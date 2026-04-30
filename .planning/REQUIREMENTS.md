# Requirements: Midwife Agent v2.0 — Sellable Feature Set

**Defined:** 2026-04-30
**Core Value:** The agent saves a midwife meaningful time on every client encounter — especially note-writing — so that the $4,500 setup cost pays back within the first month of use.

## v1 Requirements

### Clinical Notes

- [ ] **NOTES-01**: Midwife can type bullet-point observations and receive a SOAP-structured clinical narrative with no visible subheadings — Subjective, Objective, Assessment, and Plan flow implicitly through paragraph structure
- [ ] **NOTES-02**: Agent expands midwife-specific acronyms (FHR, NAD, PV, etc.) in generated notes using a glossary; glossary ships with a seed list of common LMC acronyms and is expandable by uploading past notes to Google Drive
- [ ] **NOTES-03**: Four note templates are available — initial booking visit, routine antenatal, postnatal check, referral letter — each with defined expected fields and appropriate output structure
- [ ] **NOTES-04**: Agent infers the appropriate template from bullet-point content, or midwife can explicitly select a template by name
- [ ] **NOTES-05**: Generated note output is compatible with ACC and NZ DHB documentation expectations for LMC records (continuous prose paragraphs, no markdown headers in output)

### User Interface

- [ ] **UI-01**: Each chat message displays a timestamp showing the date and time it was sent

### Gmail Reliability

- [ ] **GMAIL-01**: Email watcher status endpoint reports accurate thread liveness — a heartbeat mechanism detects when the watcher thread has died and surfaces this in `/api/health` or equivalent, replacing the current "running: True even when dead" behaviour
- [ ] **GMAIL-02**: Email watcher resilience — when the thread fails silently, the failure is visible to the operator (status endpoint, logs) and the thread either auto-restarts or provides a clear signal that manual intervention is needed

### Outlook Integration

- [ ] **OUTLOOK-01**: Midwife can connect up to 3 Microsoft Outlook accounts to the agent via MSAL OAuth — built from scratch with `msal` declared in `requirements.txt` (replaces the deleted `outlook_integration.py`)
- [ ] **OUTLOOK-02**: Agent can list inbox and read email content from any connected Outlook account
- [ ] **OUTLOOK-03**: Agent can search email across connected Outlook accounts by keyword, sender, or date range
- [ ] **OUTLOOK-04**: Agent can create draft replies for messages in any connected Outlook account

## v2 Requirements (deferred to v2.1)

### Cultural Fluency

- **TEREO-01**: Agent uses culturally appropriate te reo Maori terms naturally in responses, guided by an uploaded style guide that defines which terms to use and in what context

### Infrastructure

- **STORE-01**: Knowledge base document store persists across Railway redeploys — in-memory store replaced with SQLite on Railway volume or Railway Postgres

### Bug Fixes

- **BUG-01**: `reschedule_appointment` creates the rescheduled event with correct duration (zero-duration bug fixed)
- **BUG-02**: `chunk_text` has an infinite-loop guard for inputs that would previously cause it to loop indefinitely
- **BUG-03**: `signOut()` clears only the API key from localStorage rather than calling `localStorage.clear()` — preserves unrelated stored state

## Out of Scope

| Feature | Reason |
|---------|--------|
| Midwife-specific knowledge base | GC Advisory KB stays; dedicated midwife KB is a future milestone |
| Branding / identity changes | Future milestone |
| Practice Vitals seminar funnel | Future milestone |
| Multi-tenant / per-client replication | Requires v2.1+ persistent store as a prerequisite |
| Vector / semantic search | Keyword RAG is sufficient; revisit when KB grows |
| Per-user API keys / staff accounts | Single-user Bearer token model stays for v2.0 |
| Calendar or Drive feature changes | Not part of sellable feature set — stable in v1.0 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| NOTES-01 | Phase 4 | Pending |
| NOTES-02 | Phase 4 | Pending |
| NOTES-03 | Phase 4 | Pending |
| NOTES-04 | Phase 4 | Pending |
| NOTES-05 | Phase 4 | Pending |
| UI-01 | Phase 5 | Pending |
| GMAIL-01 | Phase 5 | Pending |
| GMAIL-02 | Phase 5 | Pending |
| OUTLOOK-01 | Phase 6 | Pending |
| OUTLOOK-02 | Phase 6 | Pending |
| OUTLOOK-03 | Phase 6 | Pending |
| OUTLOOK-04 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-30*
*Last updated: 2026-04-30 after v2.0 milestone initialization*
