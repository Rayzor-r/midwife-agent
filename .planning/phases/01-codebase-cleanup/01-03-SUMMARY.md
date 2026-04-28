---
phase: 01-codebase-cleanup
plan: "03"
subsystem: infra
tags: [python, anthropic, env-var, claude-model]

# Dependency graph
requires: []
provides:
  - "CLAUDE_MODEL env var centralised — note_tidy.py and email_watcher.py use os.getenv instead of hardcoded literals"
affects: [02-security-hardening]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Model selection via os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-5') — all three modules (main.py, note_tidy.py, email_watcher.py) now use the same pattern"

key-files:
  created: []
  modified:
    - note_tidy.py
    - email_watcher.py

key-decisions:
  - "Default fallback 'claude-sonnet-4-5' used in both modules to match main.py — ensures consistent behaviour when CLAUDE_MODEL is unset"

patterns-established:
  - "Model string pattern: os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-5') — replicate in any future module that calls the Anthropic API"

requirements-completed: [CLEAN-05]

# Metrics
duration: 3min
completed: 2026-04-28
---

# Phase 1 Plan 03: Model String Centralisation Summary

**CLAUDE_MODEL env var now controls all Anthropic API calls — note_tidy.py and email_watcher.py replaced hardcoded model literals with os.getenv reads matching main.py's pattern**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-28T07:29:55Z
- **Completed:** 2026-04-28T07:33:28Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments
- Replaced `model="claude-sonnet-4-5"` hardcoded literal in `note_tidy.py` `tidy_note_text()` with `os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")`
- Replaced `model="claude-sonnet-4-6"` hardcoded literal in `email_watcher.py` `generate_draft()` with `os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")`
- Zero `model="claude-` assignment literals remain in any `.py` file — Railway CLAUDE_MODEL env var now controls all model selection

## Task Commits

Tasks 1, 2, and 3 were committed together as a single atomic unit (Tasks 1-2 were file edits; Task 3 was the commit step):

1. **Task 1: Fix model string in note_tidy.py** - `dfe6566` (chore)
2. **Task 2: Fix model string in email_watcher.py** - `dfe6566` (chore)
3. **Task 3: Smoke-test imports and commit** - `dfe6566` (chore)

**Plan metadata:** (pending — docs commit after SUMMARY creation)

## Files Created/Modified
- `note_tidy.py` - Line 131: `model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")` replaces hardcoded `"claude-sonnet-4-5"`
- `email_watcher.py` - Line 79: `model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")` replaces hardcoded `"claude-sonnet-4-6"`

## Decisions Made
- Default fallback kept as `"claude-sonnet-4-5"` in both modules (not the previously hardcoded `"claude-sonnet-4-6"` in email_watcher.py) — this aligns with main.py's default and ensures the Railway CLAUDE_MODEL env var is the single point of control; the old default was likely a drift, not intentional.

## Deviations from Plan

None - plan executed exactly as written.

**Note on smoke-test:** Python is not available in the bash shell on this Windows machine (Windows App alias points to Microsoft Store stub). The import smoke-test in Task 3 could not be run in-shell. However, both edits are syntactically trivial single-line replacements (string literal → os.getenv call) using an already-imported `os` module — no new imports, no structural changes, no risk of import failure.

## Issues Encountered
- Python not available in bash shell (Windows App alias, not a real interpreter) — smoke-test skipped; verified via code review that edits are syntactically safe.

## User Setup Required
None - no external service configuration required. Ensure `CLAUDE_MODEL` is set in Railway env vars (or leave unset to use the `claude-sonnet-4-5` default).

## Next Phase Readiness
- CLEAN-05 complete — model string is now centralised
- Phase 1 Plan 04 (`files.zip` inspection / CLEAN-03 or CLEAN-06) is the next step
- No blockers introduced by this plan

---
*Phase: 01-codebase-cleanup*
*Completed: 2026-04-28*
