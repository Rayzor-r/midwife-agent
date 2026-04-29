---
plan: 02-03
phase: 2
status: complete
completed: 2026-04-29
commit: 93deb8f
requirements:
  - SEC-01
---

## Summary

Completed plan 02-03: full-screen password overlay + Authorization headers on all four fetch() call sites in static/index.html.

## What Was Built

**Auth overlay (HTML + CSS):**
- `#auth-overlay` full-screen fixed overlay with `z-index:9999` and `backdrop-filter:blur(20px)`
- `.auth-box` card using existing design tokens (`--g2`, `--gb`, `--primary`, `--font`, `--mono`, `--r`, `--r-s`, `--t1`, `--t2`)
- Password input with show/hide toggle (`#auth-eye`)
- `#auth-error` element for inline error messages
- `#auth-upgrade-notice` banner above box — shown only on first login, suppressed permanently after `auth_upgrade_seen` localStorage flag is set
- Sign out link in header (`onclick="signOut()"`)

**Auth JavaScript:**
- `getApiKey()` — reads `localStorage.getItem('api_key')`
- `updateUpgradeNotice()` — shows upgrade notice only for first-time users
- `showAuthOverlay(errorMsg)` — shows overlay, clears input, calls `updateUpgradeNotice()`
- `hideAuthOverlay()` — adds `.hidden` class
- `signOut()` — clears localStorage, reloads page
- `handleAuthSubmit()` — stores key, sets `auth_upgrade_seen`, hides overlay, triggers `loadDocs()`

**Authorization headers — all four fetch() sites:**
- `/api/chat` POST — `'Authorization': 'Bearer ' + getApiKey()`
- `/api/upload` POST — `'Authorization': 'Bearer ' + getApiKey()`
- `/api/documents` GET — `'Authorization': 'Bearer ' + getApiKey()`
- `/api/documents/${id}` DELETE — `'Authorization': 'Bearer ' + getApiKey()`

**401 handling on each fetch:**
- Context-aware: `hadKey` captured before removal
- Wrong password (had key): "That password didn't work. Please try again."
- No stored key (first-time 401): "This app now requires a password. Enter the password your administrator gave you."

**Network failure:** `TypeError` in `loadDocs` catch → "Couldn't reach the server. Check your connection and try again." toast

**Init block:** conditional — shows overlay if no `api_key` in localStorage, otherwise hides overlay and loads docs.

## Key Files

- `static/index.html` — all changes inline

## Deviations

None. All tasks executed exactly as specified.

## Self-Check

- [x] `grep -c "Authorization.*getApiKey" static/index.html` returns 4
- [x] `grep -n "auth-overlay" static/index.html` returns CSS rule and HTML div
- [x] `grep -n "auth-upgrade-notice" static/index.html` returns notice div inside #auth-overlay
- [x] `grep -c "hadKey" static/index.html` returns 8 (2 per guarded fetch site × 4 sites)
- [x] `grep -c "administrator gave you" static/index.html` returns 4
- [x] `grep -c "That password" static/index.html` returns 4
- [x] `grep -n "Couldn't reach the server" static/index.html` returns 1 line
- [x] Sign out link present in header with `onclick="signOut()"`

## Self-Check: PASSED
