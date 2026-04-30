# Phase 4: Clinical Notes Overhaul - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Turn raw bullet-point observations into SOAP-structured clinical narrative prose that matches how this specific midwife practice actually writes — using uploaded past notes as style exemplars, with acronym expansion via a seed glossary and derived terms. Referral letters follow the same "uploaded examples first" principle, with a four-section fallback if none exist. No new UI features, no email, no Outlook — those are Phases 5 and 6.

</domain>

<decisions>
## Implementation Decisions

### Module strategy
- **D-01:** Create a new `notes_engine.py` module for all SOAP generation logic. `note_tidy.py` is untouched — the existing tidy behaviour (Drive-to-Drive formatting, abbreviations kept as-is, labelled output sections) continues to work as before. The two modules serve different purposes and have opposing rules about abbreviation handling and output formatting.

### Past notes as style exemplars
- **D-02:** Uploaded past notes from the Drive notes folder (`GOOGLE_DRIVE_NOTES_FOLDER_ID`) are the primary source of style, terminology, and structure for note generation. The engine reads ALL past notes in the folder — not a sample.
- **D-03:** Because the full note set may exceed the context window, the engine extracts a **style profile** from the complete set rather than injecting raw note text. The style profile captures: typical paragraph length and cadence, common clinical phrases this practice uses, how acronyms appear in context, level of clinical detail expected, tone, and structural flow (what goes in which part of a note).
- **D-04:** The style profile is cached in memory. It is built lazily on the first note generation request in a session. On Railway restart the cache is wiped and rebuilt automatically on the next request — by design, this means newly uploaded notes are always picked up after a restart.
- **D-05:** The midwife can explicitly trigger a style profile rebuild by saying something like "refresh my notes style" — the agent then re-downloads the Drive folder and rebuilds the profile. This is the mechanism for picking up newly uploaded notes mid-session without waiting for a restart.
- **D-06:** Cold-start fallback (no past notes uploaded yet): the engine uses a generic "competent NZ LMC midwife" style in the system prompt, relying on the seed glossary for acronym expansion. The feature is usable before any past notes are uploaded.

### SOAP output format
- **D-07:** SOAP structure (Subjective → Objective → Assessment → Plan) is always the underlying framework, but it is **implicit** in the paragraph flow. No visible subheadings, no section labels, no markdown headers in the output. The text reads as continuous clinical prose — the way an experienced midwife would write it, not as a filled-in form.
- **D-08:** There are no predefined rigid templates (initial booking, routine antenatal, etc.). Every note type is handled by the same style-learning approach. The uploaded past notes teach the agent what this practice's notes look like for different visit types.

### Acronym glossary
- **D-09:** A seed glossary of common LMC acronyms lives in `glossary.json` committed to the repo. Covers terms like FHR (fetal heart rate), NAD (no abnormality detected), PV (per vaginum), SFH (symphysis-fundal height), FMF (fetal movements felt), etc. Target ~25–35 terms for the seed list.
- **D-10:** When the style profile is built from uploaded past notes, the engine also extracts additional practice-specific acronyms and adds them to the working glossary for the session. The combined glossary (seed + derived) is what gets applied during note generation.
- **D-11:** Glossary expansion from the Claude API response is instructed — the LLM is told to expand acronyms in the output prose using the provided glossary, not to leave them as abbreviations.

### Referral letters
- **D-12:** Referral letters follow the same "uploaded examples first" principle as clinical notes — if the midwife has uploaded past referral letters to the Drive notes folder, the engine learns from those.
- **D-13:** Cold-start fallback for referral letters: a four-section lightweight template — Recipient (name/role/facility), Reason for referral (1–2 sentences), Clinical summary (relevant history and current obs as prose paragraphs), Request (what the midwife is asking the recipient to do). This is the only case where visible structure is acceptable in output.

### API surface
- **D-14:** A `POST /api/notes/generate` endpoint is the primary interface for the SOAP engine (per plan assignment 04-01). This endpoint accepts bullet-point input and returns generated note prose.
- **D-15:** The engine is also accessible via Claude tool use in the chat interface — a new tool (`generate_clinical_note`) wraps the same engine so the midwife can type bullets directly into chat and receive a note inline.
- **D-16:** All new `/api/*` routes are protected by the existing Bearer token middleware (v1.0 carry-forward — non-negotiable).

### Claude's Discretion
- Exact style profile extraction prompt design (how to summarise a corpus of notes into a reusable style description)
- Acronym detection heuristics for the derived glossary extraction
- How to distinguish referral letters from clinical notes in the uploaded folder (file naming, content detection, or treat all as one corpus)
- Maximum notes to download for style profile build (practical limit based on Drive folder size and token budget)
- Error handling for Drive auth failures during style profile build

</decisions>

<specifics>
## Specific Ideas

- "Read everything once to learn the style, apply that learning every time" — the style profile is the distilled knowledge of the full note corpus, not a few cherry-picked examples.
- "The midwife's notes file is the source of truth for style, terminology, and structure" — the engine defers to uploaded past notes over any hardcoded opinion.
- The output should read like "a senior midwife wrote it, not like an AI filled in a form."
- Cold-start path must be graceful and useful — the seed glossary + generic NZ LMC midwife style should produce acceptable notes even before any past notes are uploaded.
- The "refresh style" command should be something the midwife can say naturally in chat, not a technical slash command.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 4 requirements
- `.planning/REQUIREMENTS.md` §Clinical Notes — NOTES-01 through NOTES-05 (five requirements, all in this phase)
- `.planning/ROADMAP.md` §Phase 4 — goal statement, success criteria, and plan assignments (04-01, 04-02, 04-03)

### Existing note infrastructure to understand before modifying
- `note_tidy.py` — full file. Existing note tidy module. D-01 says do NOT modify this. Understand its approach to see what the new engine must NOT replicate.
- `main.py` lines 341–380 — existing note tool definitions (`list_note_files`, `tidy_note_from_drive`, `tidy_pasted_note`). New tools must be added alongside, not replacing.
- `main.py` lines 432–440 — existing `_run_tool` dispatcher entries for note tools.

### Security constraint
- `.planning/phases/02-security-hardening/02-01-PLAN.md` — Bearer token middleware. All new `/api/*` routes must be protected (D-16).
- `main.py` — `require_api_key` dependency. Use this on the new notes endpoint.

### Deployment constraint
- `.planning/PROJECT.md` §Constraints — Railway env vars only; no filesystem persistence between redeploys. Style profile cache must be in-memory, not written to disk.

[No external clinical standards documents in the repo — ACC/DHB format requirements are captured in D-07 and D-13 above]

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `note_tidy.py` → `tidy_note_text()`: shows the pattern for a one-shot LLM call with a detailed system prompt. The new engine follows the same pattern but with a different system prompt and pre-built style context.
- `drive_integration.py` → `list_drive_files()`, `download_file()`, `extract_text_from_bytes()`: already handles Drive auth, file listing, and text extraction from PDF/DOCX/TXT. The style profile builder will call these directly.
- `main.py` → `get_google_credentials()`: credential builder used by all Drive/Gmail/Calendar operations. The notes engine uses the same pattern.
- `main.py` → `require_api_key`: FastAPI dependency for Bearer token auth. Use this on `POST /api/notes/generate`.

### Established Patterns
- Tool definitions in `TOOLS` list (`main.py` lines 196–356): JSON schema objects with `name`, `description`, `input_schema`. New `generate_clinical_note` tool follows this exact shape.
- `_run_tool` dispatcher (`main.py` lines 359–440): if/elif chain. New tool must be added here.
- Module-level in-memory cache pattern: `_processed` dict in `note_tidy.py`, `_processed_ids` set in `email_watcher.py`. The style profile cache follows this same pattern (module-level variable in `notes_engine.py`).
- LLM calls in integration modules use `os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")` and `os.getenv("ANTHROPIC_API_KEY")` — `notes_engine.py` must do the same.

### Integration Points
- `notes_engine.py` imports from `drive_integration.py` for file access (same as `note_tidy.py`)
- `main.py` imports `notes_engine` functions, adds new tool definitions to `TOOLS`, adds new dispatcher entries to `_run_tool`, adds `POST /api/notes/generate` route
- `glossary.json` loaded at module import time in `notes_engine.py`; path relative to repo root

</code_context>

<deferred>
## Deferred Ideas

- Persistent style profile storage across restarts (would require SQLite/Postgres — deferred to v2.1 with STORE-01)
- Automatic classification of uploaded notes by type (referral vs clinical) using file naming conventions — Claude's discretion for Phase 4
- Per-client style profiles for multi-tenant use — out of scope for v2.0 (single-tenant)
- Glossary UI for the midwife to review and edit the derived acronym list — future phase
- Te reo Maori term insertion in generated notes (TEREO-01) — deferred to v2.1

</deferred>

---

*Phase: 04-notes-overhaul*
*Context gathered: 2026-05-01*
