---
plan: 04-02
phase: 04-notes-overhaul
status: complete
completed: 2026-05-01
requirements_addressed:
  - NOTES-03
---

# Plan 04-02 Summary: Style Profile Builder

## What Was Built

**`notes_engine_style.py`** — standalone module with `build_style_profile(creds)` that teaches the engine to write in the midwife's own style.

### Key implementation details

- `_fetch_corpus(creds)` — downloads all files from `GOOGLE_DRIVE_NOTES_FOLDER_ID` (not `GOOGLE_DRIVE_FOLDER_ID`), capped at `MAX_NOTES_FOR_STYLE = 50`
- Google Docs mime type (`application/vnd.google-apps.document`) gets `.docx` appended so `extract_text_from_bytes` can handle it
- Per-file failures are logged as warnings and skipped — a malformed file cannot abort the whole build
- Missing env var raises `RuntimeError` immediately (caller in `notes_engine.py` catches and falls back to cold-start)
- Empty folder returns `{"prose_description": "", "derived_glossary": {}, "notes_read": 0}` without raising
- Single LLM call extracts both style description and practice-specific derived glossary
- JSON parse failure handled: logs warning, uses raw text as prose_description with empty derived_glossary

### Integration with notes_engine.py

- Both `generate_note()` and `refresh_style_profile()` use `from notes_engine_style import build_style_profile` (lazy import)
- The `except ImportError` guard in `generate_note()` no longer fires (module now exists) — cold-start only occurs on Drive auth failure (caught by `except Exception`)
- No circular import: `notes_engine_style` does not import `notes_engine`

## Self-Check

| Check | Result |
|-------|--------|
| notes_engine_style.py created | ✓ |
| `build_style_profile` exported | ✓ |
| Uses `GOOGLE_DRIVE_NOTES_FOLDER_ID` (not `GOOGLE_DRIVE_FOLDER_ID`) | ✓ |
| `MAX_NOTES_FOR_STYLE = 50` defined | ✓ |
| Google Docs mime type handling (.docx append) | ✓ |
| Per-file failure logged and skipped | ✓ |
| Empty folder returns zero-entry dict | ✓ |
| JSON parse failure handled gracefully | ✓ |
| Lazy import guards in notes_engine.py confirmed present | ✓ |
| No circular import | ✓ |

## Self-Check: PASSED

## key-files

### key-files.created
- notes_engine_style.py
