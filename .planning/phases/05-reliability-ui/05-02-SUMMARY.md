---
plan: "05-02"
phase: 5
name: "Chat Message Timestamps"
status: complete
requirements_satisfied:
  - UI-01
---

## What Was Built

Updated the `now()` function in `static/index.html` from returning `HH:MM` only to `DD MMM, HH:MM` (e.g. "01 May, 13:30") in the browser's local timezone.

**static/index.html:**
- Replaced `new Date().toLocaleTimeString(...)` single call with three separate `toLocaleString()` calls:
  - `day: '2-digit'` → zero-padded day ("01", "31")
  - `month: 'short'` → abbreviated month name ("Jan", "May", "Dec")
  - `hour: '2-digit', minute: '2-digit', hour12: false` → 24-hour time ("13:30")
- Both `appendUserMsg` and `appendAiMsg` already embed `${now()}` in `.msg-time` — no template changes needed
- `.msg-time` CSS rule untouched

## Key Files

### key-files.modified
- `static/index.html` — updated `now()` function body only

## Commits

- `feat(05-02)`: update now() to return DD MMM, HH:MM timestamp format

## Self-Check: PASSED

- ✓ `now()` returns "DD MMM, HH:MM" format (e.g. "01 May, 13:30")
- ✓ `toLocaleTimeString` no longer present in file
- ✓ Exactly 3 `toLocaleString()` calls — one for day, month, time
- ✓ `hour12: false` — 24-hour clock
- ✓ `month: 'short'` — abbreviated month name
- ✓ `day: '2-digit'` — zero-padded day
- ✓ Both message templates still call `${now()}` unchanged (3 occurrences: function def + 2 template usages)
- ✓ `.msg-time` CSS rule and structure intact
- ✓ UI-01 satisfied: every chat message shows timestamp with date and time when rendered
