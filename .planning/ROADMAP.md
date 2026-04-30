# Roadmap: Midwife Agent

## Milestones

- ✅ **v1.0 Foundation Hardening** - Phases 1-3 (shipped 2026-04-30)
- 🚧 **v2.0 Sellable Feature Set** - Phases 4-6 (in progress)

## Phases

<details>
<summary>✅ v1.0 Foundation Hardening (Phases 1-3) — SHIPPED 2026-04-30</summary>

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Codebase Cleanup** - Delete dead files, purge the binary blob, lock down .gitignore, centralise the model string
- [x] **Phase 2: Security Hardening** - Add API key middleware, restrict CORS, protect OAuth callback, rotate exposed credentials
- [x] **Phase 3: Documentation** - Write SECURITY.md and complete the README env var reference

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
- [x] 01-02-PLAN.md — Inspect and remove files.zip (with checkpoint for sensitivity decision)
- [x] 01-03-PLAN.md — Centralise CLAUDE_MODEL env var in note_tidy.py and email_watcher.py
- [x] 01-04-PLAN.md — Harden .gitignore with credential patterns and scan git history

### Phase 2: Security Hardening
**Goal**: Every live API endpoint requires a valid bearer token, the CORS policy admits only the intended origin, the OAuth callback no longer exposes credentials, and the previously exposed Google credentials have been replaced
**Depends on**: Phase 1
**Requirements**: SEC-01, SEC-02, SEC-03, SEC-04
**Success Criteria** (what must be TRUE):
  1. A `curl` request to any `/api/*` endpoint without an `Authorization: Bearer <token>` header returns HTTP 401; the same request with a valid token returns HTTP 200
  2. The CORS `allow_origins` list in `main.py` is set to the value of `ALLOWED_ORIGIN` env var (not `*`); a browser request from an unlisted origin is rejected with a CORS error
  3. The `/auth/google/callback` page renders a generic success message only — no token JSON, no textarea, no credentials in the browser response body or page source. The token is written only to Railway server logs (accessible only to operators with Railway dashboard access) as the secure delivery mechanism.
  4. Google OAuth credentials (client secret, access token, refresh token) have been rotated in Google Cloud Console and the new values are live in Railway env vars
**Plans**: 4 plans

Plans:
- [x] 02-01-PLAN.md — Restrict CORS to ALLOWED_ORIGIN env var and remove token textarea from OAuth callback (SEC-02, SEC-03)
- [x] 02-02-PLAN.md — Add API key Bearer token middleware to main.py protecting all /api/* routes (SEC-01 backend)
- [x] 02-03-PLAN.md — Add frontend password overlay, Authorization headers on all fetch() calls, 401/network-failure handling (SEC-01 frontend)
- [x] 02-04-PLAN.md — Rotate Google OAuth credentials in Google Cloud Console and update Railway env vars (SEC-04)

### Phase 3: Documentation
**Goal**: Anyone picking up this codebase can understand how authentication works, what all environment variables do, and how to rotate credentials — without reading source code
**Depends on**: Phase 2
**Requirements**: DOC-01, DOC-02
**Success Criteria** (what must be TRUE):
  1. `SECURITY.md` exists at the repo root and documents: the Bearer token auth model, the CORS policy and how to configure it, the OAuth token handling approach, and step-by-step credential rotation instructions
  2. `README.md` contains an environment variable reference table covering all 11 required vars (`API_KEY`, `ALLOWED_ORIGIN`, `CLAUDE_MODEL`, `ANTHROPIC_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_TOKEN`, `GOOGLE_DRIVE_FOLDER_ID`, `GOOGLE_DRIVE_NOTES_FOLDER_ID`, `PORT`, `RAILWAY_PUBLIC_DOMAIN`)
**Plans**: 2 plans

Plans:
- [x] 03-01-PLAN.md — Write SECURITY.md (auth model, CORS policy, OAuth callback approach, credential rotation steps)
- [x] 03-02-PLAN.md — Complete README.md env var reference table

</details>

---

### 🚧 v2.0 Sellable Feature Set (In Progress)

**Milestone Goal:** Deliver the clinical notes engine, reliable email watcher, and Outlook integration that make the agent worth buying at NZD $4,500 per practice.

**Phase Numbering continues from v1.0 (phases 1-3).**

- [ ] **Phase 4: Clinical Notes Overhaul** - SOAP engine from bullet input, acronym glossary, style-learning from past notes corpus, ACC/DHB-compatible output
- [ ] **Phase 5: Reliability and UI** - Email watcher heartbeat, visible failure surfacing, chat message timestamps
- [ ] **Phase 6: Outlook Integration** - MSAL OAuth for 3 accounts rebuilt from scratch, read/search/draft parity with Gmail

## Phase Details

### Phase 4: Clinical Notes Overhaul
**Goal**: The midwife can type raw bullet-point observations and receive a properly structured, ACC/DHB-compatible clinical narrative — with acronyms expanded, style learned from her uploaded past notes, and no visible markdown headers in the output
**Depends on**: Phase 3 (v1.0 complete — foundation is hardened)
**Requirements**: NOTES-01, NOTES-02, NOTES-03, NOTES-04, NOTES-05
**Success Criteria** (what must be TRUE):
  1. Midwife types bullet-point observations into the chat and receives a continuous-prose SOAP narrative — Subjective, Objective, Assessment, and Plan flow through paragraphs with no visible subheadings or markdown formatting in the output
  2. Common LMC acronyms (FHR, NAD, PV, etc.) in the bullet input are expanded in the generated note — the seed glossary ships with the code and is usable before any past notes are uploaded
  3. When past notes are uploaded to the Drive notes folder, the engine learns note style from that corpus (not predefined templates) — the midwife's own notes are the style exemplar
  4. The agent infers clinical vs referral note type from bullet content automatically; midwife can override explicitly — both paths produce a valid note
  5. The generated output passes a spot-check against ACC and NZ DHB LMC documentation expectations: continuous paragraphs, no markdown headers, standard clinical language
**Plans**: 3 plans

Plans:
- [ ] 04-01-PLAN.md — SOAP engine (notes_engine.py), seed glossary (glossary.json), generate_clinical_note tool and POST /api/notes/generate in main.py — NOTES-01, NOTES-02
- [ ] 04-02-PLAN.md — Style profile builder (notes_engine_style.py): Drive corpus download, LLM style extraction, derived glossary — NOTES-03
- [ ] 04-03-PLAN.md — Auto-detection of note type (clinical vs referral), explicit override, output compliance checker — NOTES-04, NOTES-05
**UI hint**: yes

### Phase 5: Reliability and UI
**Goal**: The email watcher accurately reports its own liveness, failures are visible rather than silent, and every chat message shows when it was sent
**Depends on**: Phase 4
**Requirements**: UI-01, GMAIL-01, GMAIL-02
**Success Criteria** (what must be TRUE):
  1. Each chat message in the UI shows a timestamp (date and time) at the moment it was sent — visible without hovering or expanding
  2. The `/api/health` endpoint (or equivalent) returns an accurate email watcher status: if the watcher thread has died, the status reflects "dead" or equivalent — the current "running: True even when dead" behaviour is gone
  3. When the email watcher thread fails, the failure is visible to the operator within one poll cycle — either via the status endpoint, server logs, or an auto-restart — and does not require a full application restart to detect
**Plans**: 2 plans (estimated)

Plans:
- [ ] 05-01: Email watcher heartbeat and resilience — heartbeat check in `email_watcher.py`, accurate liveness in health endpoint, auto-restart or clear failure signal, GMAIL-01 and GMAIL-02
- [ ] 05-02: Chat message timestamps — timestamp rendering in `static/index.html` for all messages, UI-01
**UI hint**: yes

### Phase 6: Outlook Integration
**Goal**: The midwife can connect up to three Microsoft Outlook accounts and use them to read, search, and draft email replies — with the same capability she already has in Gmail
**Depends on**: Phase 5
**Requirements**: OUTLOOK-01, OUTLOOK-02, OUTLOOK-03, OUTLOOK-04
**Success Criteria** (what must be TRUE):
  1. The midwife can authenticate up to three Outlook accounts via MSAL OAuth — `msal` is declared in `requirements.txt`, tokens are stored as Railway env vars, and the auth flow completes without exposing credentials in the browser
  2. The agent can list the inbox and read full email content from any authenticated Outlook account on request
  3. The agent can search email across authenticated Outlook accounts by keyword, sender, or date range and return matching messages
  4. The agent can create a draft reply to any Outlook message — the draft appears in the account's Drafts folder, ready for the midwife to review and send
**Plans**: 3 plans (estimated)

Plans:
- [ ] 06-01: MSAL auth for three Outlook accounts — `outlook_integration.py` rebuilt from scratch, `msal` in `requirements.txt`, token storage as Railway env vars, OUTLOOK-01
- [ ] 06-02: Read and list email from Outlook accounts — inbox listing and full message read via Microsoft Graph, OUTLOOK-02
- [ ] 06-03: Search email and draft replies — keyword/sender/date search and draft creation across accounts, OUTLOOK-03 and OUTLOOK-04

## Progress

**Execution Order:**
v1.0 complete. v2.0 executes: 4 → 5 → 6

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Codebase Cleanup | v1.0 | 4/4 | Complete | 2026-04-28 |
| 2. Security Hardening | v1.0 | 4/4 | Complete | 2026-04-30 |
| 3. Documentation | v1.0 | 2/2 | Complete | 2026-04-30 |
| 4. Clinical Notes Overhaul | v2.0 | 0/3 | Ready to execute | - |
| 5. Reliability and UI | v2.0 | 0/2 | Not started | - |
| 6. Outlook Integration | v2.0 | 0/3 | Not started | - |
