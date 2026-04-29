---
phase: 02-security-hardening
verified: 2026-04-29T00:00:00Z
status: human_needed
score: 4/4 must-haves verified
overrides_applied: 0
gaps: []
human_verification:
  - test: "Browser first-load with cleared localStorage — confirm password overlay appears and upgrade notice is visible above the box"
    expected: "Full-screen overlay visible on top of app, upgrade notice banner shown above .auth-box, app content inaccessible"
    why_human: "DOM rendering and z-index stacking cannot be verified without a running browser"
  - test: "Submit correct password via overlay — confirm overlay dismisses, docs load, auth_upgrade_seen flag set"
    expected: "Overlay hidden, document list renders, localStorage contains api_key and auth_upgrade_seen=1"
    why_human: "localStorage state and live fetch behaviour requires browser interaction"
  - test: "After Sign out, reload — confirm overlay reappears but upgrade notice is suppressed"
    expected: "Overlay visible, upgrade notice NOT shown (auth_upgrade_seen already set)"
    why_human: "Conditional display of upgrade notice depends on localStorage state; requires browser"
  - test: "Live curl smoke test against Railway deployment: /api/health returns 200, /api/documents (no token) returns 401, /api/documents (with valid API_KEY bearer token) returns 200"
    expected: "200, 401, 200 respectively"
    why_human: "Railway deployment state and API_KEY env var value are external to the codebase; cannot verify without live access"
  - test: "SEC-04 credential rotation confirmation — verify GET /api/google/status returns {connected: true} and calendar agent smoke test passes"
    expected: "Google integration live with rotated credentials"
    why_human: "SEC-04 was a manual human task (Google Cloud Console + Railway env vars); no code change to verify. Operator confirmed in 02-04-SUMMARY.md but this requires production system access to independently confirm"
---

# Phase 2: Security Hardening Verification Report

**Phase Goal:** Every live API endpoint requires a valid bearer token, the CORS policy admits only the intended origin, the OAuth callback no longer exposes credentials, and the previously exposed Google credentials have been replaced.
**Verified:** 2026-04-29
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | CORS allow_origins uses ALLOWED_ORIGIN env var, not wildcard * | VERIFIED | `main.py` line 47: `allow_origins=[os.getenv("ALLOWED_ORIGIN", "http://localhost:8000")]` — no `["*"]` present |
| 2 | /auth/google/callback renders no token JSON; writes token to logger.info | VERIFIED | `main.py` lines 616-632: `logger.info("GOOGLE_TOKEN: %s", json.dumps(tok_dict))` present; no `<textarea>` in file; `tok_dict` appears only in logger call and local assignment, not in any HTML string |
| 3 | @app.middleware("http") require_api_key protects all /api/* routes, exempts /api/health, fail-closed on empty API_KEY | VERIFIED | `main.py` lines 63-77: `EXEMPT_PATHS = {"/api/health"}`, middleware checks `path.startswith("/api/")` and `path not in EXEMPT_PATHS`, `not API_KEY` guard returns 401 if env var unset |
| 4 | static/index.html has getApiKey(), #auth-overlay, Authorization: Bearer headers on all 4 fetch sites, 401 handlers, sign-out link | VERIFIED | All 4 fetch sites patched (lines 658, 904, 927, 978); auth overlay CSS at lines 382-417; HTML at lines 587-603; `getApiKey()` at line 1006; `signOut()` at line 1031; sign-out link at line 505 |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `main.py` | CORS restriction + safe OAuth callback | VERIFIED | `os.getenv("ALLOWED_ORIGIN")` at line 47; no textarea; logger.info for token at line 622 |
| `main.py` | HTTP middleware protecting all /api/* routes | VERIFIED | `@app.middleware("http")` + `require_api_key` at lines 65-77; `API_KEY = os.getenv("API_KEY", "")` at line 59 |
| `static/index.html` | Frontend auth overlay and Authorization header injection | VERIFIED | `#auth-overlay` fixed full-screen overlay; 4 fetch sites with `Authorization: Bearer` + `getApiKey()`; 401 handlers at all 4 sites |
| Railway environment variables | New GOOGLE_TOKEN and GOOGLE_CLIENT_SECRET values (post-rotation) | OPERATOR-CONFIRMED | SEC-04 is a manual task — no code change. 02-04-SUMMARY.md reports rotation complete and `/api/google/status` returned `{"connected": true}`. Cannot independently verify without Railway access. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `main.py` CORSMiddleware | ALLOWED_ORIGIN env var | `os.getenv("ALLOWED_ORIGIN", "http://localhost:8000")` | WIRED | line 47 — exact pattern present |
| `main.py` google_auth_callback | server log only | `logger.info("GOOGLE_TOKEN: %s", ...)` | WIRED | line 622 — token reaches logger, never reaches HTMLResponse body |
| HTTP middleware | API_KEY env var | `os.getenv("API_KEY", "")` | WIRED | line 59 — loaded at module level, consumed at line 70 |
| middleware | /api/health exempt path | `path not in EXEMPT_PATHS` | WIRED | `EXEMPT_PATHS = {"/api/health"}` at line 63; checked at line 68 |
| auth-overlay HTML | localStorage key 'api_key' | `localStorage.setItem / getItem` | WIRED | `getApiKey()` reads `localStorage.getItem('api_key')` at line 1007; `handleAuthSubmit` writes at line 1057 |
| fetch() call sites | getApiKey() helper | `'Authorization': 'Bearer ' + getApiKey()` | WIRED | All 4 call sites confirmed: lines 658, 904, 927, 978 |
| /auth/google/callback | Railway Deployments Logs | logger.info(GOOGLE_TOKEN: ...) | WIRED (code side) | logger.info call confirmed in code; actual Railway log output is operator-confirmed only |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `main.py` require_api_key middleware | `API_KEY` | `os.getenv("API_KEY", "")` at module level | Yes — reads from environment; empty string causes fail-closed 401 for all /api/* | FLOWING |
| `main.py` CORSMiddleware | `ALLOWED_ORIGIN` | `os.getenv("ALLOWED_ORIGIN", "http://localhost:8000")` | Yes — reads from environment; defaults to localhost for local dev | FLOWING |
| `static/index.html` fetch sites | `getApiKey()` return value | `localStorage.getItem('api_key')` | Yes — reads from localStorage set by handleAuthSubmit | FLOWING |

### Behavioral Spot-Checks

Step 7b: SKIPPED for most checks — app requires running server with Railway env vars (API_KEY, ALLOWED_ORIGIN) to produce meaningful results. Static analysis confirms the middleware logic is correct. Live endpoint verification is routed to human verification.

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| No wildcard in CORS | `grep 'allow_origins' main.py` | Single line with `os.getenv("ALLOWED_ORIGIN")` | PASS |
| No textarea in callback | `grep 'textarea' main.py` | No output | PASS |
| GOOGLE_TOKEN in logger.info | `grep 'GOOGLE_TOKEN' main.py` | line 622: `logger.info("GOOGLE_TOKEN: %s", ...)` | PASS |
| API_KEY middleware present | `grep '@app.middleware' main.py` | line 65: `@app.middleware("http")` | PASS |
| 4 Authorization headers in index.html | `grep -c 'Authorization.*getApiKey' static/index.html` | 4 | PASS |
| hadKey pattern count | `grep -n 'hadKey' static/index.html` | 4 sites, 2 lines each (8 total) | PASS |
| administrator gave you message | `grep -c 'administrator gave you' static/index.html` | 4 | PASS |
| That password message | `grep -c 'That password' static/index.html` | 4 | PASS |
| Network failure message | `grep -n "Couldn't reach" static/index.html` | 1 line (line 941) | PASS |
| Sign out link in header | `grep -n 'signOut()' static/index.html` | line 505 (link), line 1031 (function def) | PASS |
| Init block conditional | `grep 'if (!localStorage.getItem' static/index.html` | line 1064 | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SEC-01 | 02-02, 02-03 | All /api/* routes reject requests without valid Authorization: Bearer token | SATISFIED | `require_api_key` middleware in main.py (lines 65-77); all 4 frontend fetch sites send Authorization header; 401 handlers present |
| SEC-02 | 02-01 | CORS allow_origins restricted to ALLOWED_ORIGIN env var, not * | SATISFIED | `main.py` line 47: `os.getenv("ALLOWED_ORIGIN", "http://localhost:8000")` — wildcard removed |
| SEC-03 | 02-01 | /auth/google/callback does not expose token in response; shows generic success only | SATISFIED | No `<textarea>` in main.py; tok_dict only in `logger.info` call; HTMLResponse contains no credential data |
| SEC-04 | 02-04 | Google OAuth credentials rotated; new values live in Railway | OPERATOR-CONFIRMED | Manual task completed per 02-04-SUMMARY.md; independent verification requires Railway dashboard access |

Note: The SEC-03 requirement text contains an internal contradiction — first sentence says "not in server logs" but second sentence allows "logged only to a secured location." The ROADMAP success criterion (the contract) explicitly permits Railway server logs as the delivery mechanism, which is what was implemented. The PLAN followed the ROADMAP contract, not the ambiguous first sentence.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `main.py` | 500 | `api_key = os.getenv("ANTHROPIC_API_KEY")` reuses name `api_key` locally inside `chat()` | Info | No collision — local variable in `chat()` function, module-level `API_KEY` is a different name (uppercase). No impact on middleware. |

No blocker anti-patterns found. No TODO/FIXME/placeholder comments in modified code. No empty implementations in the security-related code paths.

### Human Verification Required

#### 1. Browser overlay rendering and first-login flow

**Test:** Open the app in a browser with cleared localStorage. Confirm the full-screen password overlay appears on top of the app with the upgrade notice visible above the `.auth-box`. Enter the correct API key and confirm overlay dismisses, documents load, and both `api_key` and `auth_upgrade_seen` are set in `localStorage`.
**Expected:** Overlay blocks app access; upgrade notice shown; after correct password, overlay hidden, docs render, `auth_upgrade_seen=1` in localStorage.
**Why human:** DOM rendering, z-index stacking, and localStorage state after live fetch require a running browser.

#### 2. Sign out behavior

**Test:** After logging in, click "Sign out". Confirm page reloads with overlay present but upgrade notice absent (because `auth_upgrade_seen` was previously set).
**Expected:** Overlay shows on reload; upgrade notice does NOT appear (suppressed permanently after first login).
**Why human:** Conditional localStorage-driven UI state requires browser interaction.

#### 3. Live Railway endpoint verification (SEC-01 smoke test)

**Test:**
```bash
# No token — expect 401
curl -s -o /dev/null -w "%{http_code}" https://<railway-domain>/api/documents

# Exempt health route — expect 200
curl -s -o /dev/null -w "%{http_code}" https://<railway-domain>/api/health

# Valid token — expect 200
curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer <API_KEY>" https://<railway-domain>/api/documents
```
**Expected:** 401, 200, 200
**Why human:** Requires Railway deployment to be live with `API_KEY` env var set; cannot verify against production without deployment access.

#### 4. SEC-04 independent confirmation

**Test:** With the rotated credentials live in Railway, run `curl -H "Authorization: Bearer <API_KEY>" https://<domain>/api/google/status` and confirm `{"connected": true}`. Additionally ask the agent to check upcoming calendar appointments.
**Expected:** Google status `connected: true`; calendar agent returns live data.
**Why human:** SEC-04 is entirely a manual/operational task (Google Cloud Console + Railway env vars). The code changes that enable secure token delivery (SEC-03) are verified; the credential rotation itself is operator-confirmed in the SUMMARY but cannot be independently verified without Railway/Google Cloud Console access.

---

## Gaps Summary

No code-level gaps. All four security controls are implemented correctly in the codebase:

- **SEC-02 (CORS):** `allow_origins` uses `os.getenv("ALLOWED_ORIGIN", "http://localhost:8000")` — wildcard eliminated.
- **SEC-03 (OAuth callback):** No `<textarea>`, no token in HTML response, `logger.info("GOOGLE_TOKEN: ...")` present — callback is safe.
- **SEC-01 backend:** `@app.middleware("http")` `require_api_key` is correctly structured — fail-closed, exempts `/api/health`, returns 401 with `WWW-Authenticate: Bearer`.
- **SEC-01 frontend:** All 4 fetch sites have `Authorization: Bearer` headers, all 4 have 401 handlers with `hadKey` context-aware messages, `getApiKey()` wired to `localStorage`, `signOut()` present, overlay shown conditionally on init.
- **SEC-04:** Manual operator task — code side (secure callback for log delivery) is verified. Credential rotation confirmed by operator in SUMMARY but requires human re-confirmation against live Railway environment.

Status is `human_needed` because live deployment verification and visual/interactive overlay behavior cannot be confirmed programmatically.

---

_Verified: 2026-04-29_
_Verifier: Claude (gsd-verifier)_
