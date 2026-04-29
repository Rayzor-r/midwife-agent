---
plan: 02-02
phase: 2
status: complete
completed: 2026-04-29
commit: 2d9dca0
requirements:
  - SEC-01
---

## Summary

Completed plan 02-02 (code task): API key bearer token middleware added to main.py.

## What Was Built

- **Request, Response** added to `from fastapi import` line
- **`API_KEY = os.getenv("API_KEY", "")`** module-level env var read (line 58)
- **`EXEMPT_PATHS = {"/api/health"}`** module-level constant
- **`@app.middleware("http") async def require_api_key`** — Starlette middleware protecting all `/api/*` routes
  - Fail-closed: if `API_KEY` is empty/unset, all protected routes return 401
  - Returns `{"detail":"Unauthorized"}` with `WWW-Authenticate: Bearer` header on failure
  - `/api/health` exempt; `/auth/google` and all non-`/api/` routes naturally exempt
  - No route handlers modified — protection applied uniformly

## Key Files

- `main.py` lines 58–76 — API_KEY env var, EXEMPT_PATHS, require_api_key middleware

## Deviations

None. All code changes completed exactly as specified.

## Deployment Gate (02-02-T02)

⚠ The middleware commit is NOT yet deployed to Railway. Before pushing:
- Set `API_KEY` in Railway Variables (share password with all active testers first)
- Set `ALLOWED_ORIGIN = https://<railway-domain>` in Railway Variables
- Only then: `git push origin main`

See plan 02-02-T02 for full deployment and verification steps.

## Self-Check

- [x] `grep 'Request, Response' main.py` returns line 22 (updated import)
- [x] `grep 'API_KEY = os.getenv' main.py` returns module-level assignment
- [x] `grep 'EXEMPT_PATHS' main.py` returns the constant definition and middleware usage
- [x] `grep '@app.middleware' main.py` returns the require_api_key registration
- [x] `grep 'WWW-Authenticate' main.py` returns the Response headers dict in middleware

## Self-Check: PASSED
