---
plan: 04-03
phase: 04-notes-overhaul
status: complete
completed: 2026-05-01
requirements_addressed:
  - NOTES-04
  - NOTES-05
---

# Plan 04-03 Summary: Auto-detection + Compliance Checker

## What Was Built

Both deliverables for this plan were included in `notes_engine.py` (committed in plan 04-01) since they are tightly coupled to `generate_note()`. No code changes were required in this wave — verification confirmed all functions are present and correctly wired.

### `auto_detect_note_type(bullets: str) -> str`

- Returns `"referral"` if any signal from `_REFERRAL_SIGNALS` is found (case-insensitive):
  `refer`, `referral`, `letter to`, `obstetrician`, `specialist`, `consultant`, `re:`, `dear dr`, `dear nurse`
- Returns `"clinical"` otherwise
- Called by `generate_note()` when `note_type` argument is `None`
- Explicit `note_type="referral"` or `note_type="clinical"` bypasses auto-detection entirely
- Resolved type always returned in the response dict (NOTES-04 repudiation mitigation)

### `_check_output_compliance(note_text: str) -> dict`

Five hard-fail regex guards against ACC/DHB LMC format violations (NOTES-05):

| Pattern | What it catches |
|---------|----------------|
| `^#{1,6}\s` | Markdown headers (# Assessment, ## Plan) |
| `^\*\*[A-Za-z ]+\*\*:?\s*$` | Bold section labels (**Assessment:**) |
| `^[-*]\s` | Bullet points in output (- item, * item) |
| `^(Subjective\|Objective\|Assessment\|Plan):\s` | Explicit SOAP labels |
| `^[SOAP]:\s` | Abbreviated SOAP labels (S:, O:, A:, P:) |

Returns `{"passed": bool, "violations": list[str], "warnings": list[str]}`.

Integrated into `generate_note()`:
- Runs on every generated note
- Failure logs a warning with the first violating line (truncated to 40 chars)
- Note is still returned — caller decides how to handle
- `"compliance"` key always present in generate_note() return dict

## Verification

Confirmed by grep against `notes_engine.py`:
- `auto_detect_note_type` defined at line 118, called in `generate_note` at line 218 ✓
- `_REFERRAL_SIGNALS` set at line 113 with all 9 keywords ✓
- `_check_output_compliance` defined at line 138 ✓
- All 5 compiled regex patterns present (lines 132-136) ✓
- `compliance` key in `generate_note` return dict at line 243 ✓
- Compliance warning logged at line 235-236 ✓

## Self-Check

| Check | Result |
|-------|--------|
| auto_detect_note_type() exists in notes_engine.py | ✓ |
| _REFERRAL_SIGNALS contains all 9 keywords | ✓ |
| generate_note() calls auto_detect when note_type=None | ✓ |
| _check_output_compliance() exists with all 5 regex guards | ✓ |
| compliance key in generate_note() return dict | ✓ |
| NOTES-04 addressed: auto-detection + explicit override | ✓ |
| NOTES-05 addressed: compliance spot-check on every output | ✓ |

## Self-Check: PASSED

## key-files

### key-files.modified
- notes_engine.py (verified — functions already present from plan 04-01)
