---
plan: 04-01
phase: 04-notes-overhaul
status: complete
completed: 2026-05-01
requirements_addressed:
  - NOTES-01
  - NOTES-02
---

# Plan 04-01 Summary: SOAP Engine + Glossary + main.py Wiring

## What Was Built

Three atomic deliverables completing the core clinical note generation feature:

1. **`glossary.json`** — 35 NZ LMC acronym-to-term mappings (FHR, NAD, PV, SFH, FMF, and 30 more). Flat JSON object, loaded at import time by `notes_engine.py`. Committed to repo root.

2. **`notes_engine.py`** — New module with:
   - `SEED_GLOSSARY` loaded from `glossary.json` at module import
   - `_style_profile` module-level cache (starts as None, lazy-built on first call)
   - `auto_detect_note_type(bullets)` — keyword detection for referral vs clinical
   - `_check_output_compliance(note_text)` — regex guards for markdown headers, bold section labels, bullet lines, SOAP labels
   - `generate_note(bullets, creds, note_type)` — full LLM call with style prompt, glossary expansion, compliance check; returns `{"note", "note_type", "glossary_terms_used", "style_source", "compliance"}`
   - `refresh_style_profile(creds)` — force-rebuilds style cache via `notes_engine_style.build_style_profile()` (lazy import, guarded by `except ImportError` for cold-start compatibility)

3. **`main.py` (4 edits)**:
   - Import: `from notes_engine import generate_note, refresh_style_profile`
   - `generate_clinical_note` added to `TOOLS` list with `bullets` / `note_type` / `refresh_style` schema
   - `_run_tool` dispatcher branch for `generate_clinical_note` — routes to `generate_note()` or `refresh_style_profile()`
   - `POST /api/notes/generate` route + `GenerateNoteRequest` model (auto-protected by existing Bearer token middleware)

## Key Design Decisions Honored

- **D-01**: No visible subheadings in output — enforced by system prompt `STRICT OUTPUT RULES` and `_check_output_compliance()`
- **D-02**: Style-learning deferred to plan 04-02; cold-start uses generic NZ LMC voice
- **D-09/D-10**: Seed glossary ships with code, usable before any past notes are uploaded
- **D-14**: `generate_clinical_note` tool description covers both clinical and referral paths
- **D-15/D-16**: Bearer token middleware automatically covers `/api/notes/generate` — no extra decorator needed

## Self-Check

| Check | Result |
|-------|--------|
| glossary.json exists, 35 entries, valid JSON | ✓ |
| notes_engine.py file created | ✓ |
| `from notes_engine import` in main.py | ✓ |
| `generate_clinical_note` in TOOLS list (2 occurrences: definition + dispatcher) | ✓ |
| `POST /api/notes/generate` route exists | ✓ |
| 3 atomic commits | ✓ |
| STATE.md/ROADMAP.md not modified | ✓ |

## Self-Check: PASSED

## key-files

### key-files.created
- glossary.json
- notes_engine.py

### key-files.modified
- main.py
