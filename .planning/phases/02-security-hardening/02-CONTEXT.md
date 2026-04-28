# Phase 2: Security Hardening - Context

**Gathered:** 2026-04-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Every live API endpoint requires a valid bearer token, the CORS policy admits only the intended origin, the OAuth callback no longer exposes credentials, and the previously exposed Google credentials have been replaced. No new features — hardening only.

Requirements: SEC-01, SEC-02, SEC-03, SEC-04

</domain>

<decisions>
## Implementation Decisions

### Auth middleware (SEC-01)

- **D-01:** FastAPI middleware checks `Authorization: Bearer <token>` on all `/api/*` routes against the `API_KEY` env var. Missing or mismatched token returns HTTP 401.
- **D-02:** Exempt from auth: `/` (frontend), `/api/health`, `/auth/google`, `/auth/google/callback`. Everything else under `/api/*` is protected.
- **D-03:** No per-user keys, no session management, no login endpoint — pure header comparison against a single env var value.

### API_KEY semantics

- **D-04:** `API_KEY` is a memorable phrase chosen by the deployment owner (e.g., "MidwifePractice2026!") — not a random hex string. The system does not hash or validate format; any non-empty string is valid.
- **D-05:** One key per deployment/practice. Multi-user logins (per-staff accounts) are a v2.0 concern — out of scope for v1.0.
- **D-06:** All programmatic clients (email watcher, future scheduled jobs) use the same Bearer token approach, reading `API_KEY` from the environment. Auth surface is uniform across browser and server-side callers.

### Frontend auth UX

- **D-07:** Full-screen password overlay on first load — not a banner or inline prompt. Shown when no credential exists in `localStorage`.
- **D-08:** Input field is `type="password"` (masked) with a show/hide eye toggle. Label says "Enter password" — not "Enter API key" or "Enter token". Users should experience this as a password, not a developer credential.
- **D-09:** On 401 from any `/api/*` call: clear `localStorage`, re-show overlay with message "That password didn't work. Please try again."
- **D-10:** On fresh load with no stored credential: show overlay with no error message — just the prompt.
- **D-11:** On network failure (non-401 error, no response): show "Couldn't reach the server. Check your connection and try again." Distinguish clearly from auth failure — don't blame the password when the server is unreachable.
- **D-12:** Small "Sign out" link somewhere in the chat UI (corner is fine). Clears `localStorage` and reloads the page. Exists so users on shared devices can clear their session when done.
- **D-13:** Overlay styled consistently with the existing dark/glass UI — same fonts (`--font`, `--mono`), same colour tokens (`--primary`, `--g2`, `--gb`, `--t1`, `--t2`), same border radius and spacing. Not a browser `prompt()` box.

### CORS restriction (SEC-02)

- **D-14:** `allow_origins` changes from `["*"]` to `[os.getenv("ALLOWED_ORIGIN", "http://localhost:8000")]`. No other CORS changes needed — existing `allow_methods` and `allow_headers` can remain as-is for now.

### OAuth callback (SEC-03)

- **D-15:** Remove the token `<textarea>` from `/auth/google/callback`. The callback writes the token to the server log (`logger.info("GOOGLE_TOKEN: %s", json.dumps(tok_dict))`) and renders a generic success page: "Google connected ✓ — Token has been written to server logs. Copy it from your Railway dashboard under Deployments → Logs."
- **D-16:** SEC-03 must be implemented and deployed **before** SEC-04. Do not rotate credentials while the callback still renders them in the browser — the new token would be exposed immediately.

### Credential rotation (SEC-04)

- **D-17:** SEC-04 is primarily a human action: revoke existing Google OAuth credentials in Google Cloud Console, create new client secret, then trigger a fresh OAuth flow. The new token will appear in Railway logs (via the updated SEC-03 callback) and must be copied into the `GOOGLE_TOKEN` Railway env var.
- **D-18:** Step order: (1) deploy SEC-03 fix first, (2) then rotate credentials in Google Cloud Console, (3) then re-run `/auth/google` to get a fresh token, (4) copy token from Railway logs into env var, (5) redeploy.

### Claude's Discretion

- Middleware implementation pattern (FastAPI `Depends()` per route vs. Starlette `app.middleware("http")` — either is acceptable; choose based on what keeps `main.py` cleanest)
- HTTP status code for missing vs. invalid token (standard: 401 for both; no need to distinguish)
- Whether to add `WWW-Authenticate: Bearer` header to 401 responses (standard HTTP practice; include it)

</decisions>

<specifics>
## Specific Ideas

- "API_KEY is functionally a shared password for the deployment" — this framing should appear verbatim in SECURITY.md so it's clear to whoever reads the docs.
- On shared devices, the "Sign out" link matters. Note this in the UI so users know it exists.
- The password overlay should feel like the rest of the app — the current chat UI has a refined dark/glass aesthetic; the overlay should match rather than stand out as a bolted-on security screen.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

No external specs for this phase — all requirements and decisions are fully captured in this document and the planning files below.

### Key files to read before planning
- `.planning/REQUIREMENTS.md` — SEC-01 through SEC-04 acceptance criteria (exact test conditions)
- `.planning/ROADMAP.md` — Phase 2 success criteria (curl test conditions for SEC-01, CORS test for SEC-02)
- `main.py` — entry point: current CORS config (line 43), current OAuth callback (lines 594–606), all `/api/*` route definitions
- `static/index.html` — frontend: all `fetch()` calls that need `Authorization` headers (lines 597, 835, 849, 885)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `BASE_URL = os.getenv("RAILWAY_PUBLIC_DOMAIN", "http://localhost:8000")` — existing env var pattern in `main.py`; `API_KEY` and `ALLOWED_ORIGIN` follow the same `os.getenv(VAR, default)` shape
- `_require_google()` helper (main.py) — existing pattern for raising `HTTPException(401)` before protected operations; auth middleware can follow the same raise pattern
- CSS design tokens in `static/index.html` (`--primary`, `--g2`, `--gb`, `--t1`, `--t2`, `--font`, `--r`) — the overlay must use these rather than hardcoded values

### Established Patterns
- All `fetch()` calls in the frontend are currently bare (no headers); adding `Authorization: Bearer ${key}` is a uniform change to all four call sites (lines 597, 835, 849, 885)
- The existing `_require_google()` pattern shows FastAPI's `HTTPException(401, ...)` is already used for auth-like gating; the new middleware extends this pattern application-wide

### Integration Points
- `main.py:43` — CORS middleware line to change (`["*"]` → `[os.getenv("ALLOWED_ORIGIN", "http://localhost:8000")]`)
- `main.py:594–606` — OAuth callback block to replace (remove textarea, add logger.info, render success message)
- `static/index.html` fetch sites — lines 597 (`/api/chat`), 835 (`/api/upload`), 849 (`/api/documents` GET), 885 (`/api/documents/{id}` DELETE)
- Email watcher (`email_watcher.py`) — currently calls Google APIs directly, not the FastAPI endpoints; does NOT need the Bearer token for its own operation (it calls Google, not `/api/*`). No change needed there for SEC-01.

</code_context>

<deferred>
## Deferred Ideas

- Per-staff accounts / per-user API keys — v2.0 (REQUIREMENTS.md v2 backlog)
- CSRF protection on state-mutating endpoints — v2.0 (SEC-V2-01 in REQUIREMENTS.md)
- Railway API write for OAuth token (fully automated token delivery) — deferred; server-log approach is sufficient for v1.0 operational complexity

</deferred>

---

*Phase: 02-security-hardening*
*Context gathered: 2026-04-29*
