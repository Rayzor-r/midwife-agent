# Security

This document covers the security model implemented in Midwife Agent v1.0 Foundation Hardening (Phase 2). It is written for operators and developers — not end users.

---

## 1. Bearer Token Authentication

### How it works

All routes under `/api/*` require an `Authorization: Bearer <token>` header. The token is compared against the `API_KEY` environment variable set in Railway.

**API_KEY is functionally a shared password for the deployment.** It is chosen by the deployment owner as a memorable phrase (for example, `MidwifePractice2026!`). The system does not hash or validate format — any non-empty string is valid.

Implementation: `main.py` — `require_api_key` Starlette HTTP middleware (applied before any route handler).

### Exempt routes

The following routes do NOT require a Bearer token:

| Route | Reason |
|-------|--------|
| `/` | Serves the frontend HTML — unauthenticated by design |
| `/api/health` | Health check — must be reachable by Railway monitoring without a token |
| `/auth/google` | Initiates the OAuth flow — called in a browser, no token available yet |
| `/auth/google/callback` | Receives the OAuth redirect — called by Google, no token available yet |

All other `/api/*` routes are protected.

### Failure behaviour

A request with a missing or incorrect token receives:

```
HTTP 401 Unauthorized
WWW-Authenticate: Bearer
Content-Type: application/json

{"detail": "Unauthorized"}
```

If `API_KEY` is not set in the environment, the middleware is fail-closed: every protected route returns 401.

### Frontend behaviour

The frontend (`static/index.html`) shows a full-screen password overlay on first load. The stored credential is the value of `API_KEY`. On a 401 response from any `/api/*` call, the frontend clears localStorage and re-shows the overlay. A "Sign out" link in the header clears localStorage and reloads the page — use this on shared devices.

### Scope

One `API_KEY` per deployment. Per-staff accounts or per-user keys are out of scope for v1.0 — see REQUIREMENTS.md v2 backlog (SEC-V2-02).

---

## 2. CORS Policy

### Configuration

The CORS `allow_origins` list is set to the value of the `ALLOWED_ORIGIN` environment variable:

```python
allow_origins=[os.getenv("ALLOWED_ORIGIN", "http://localhost:8000")]
```

The wildcard (`*`) is not used. A browser request from an unlisted origin will be rejected with a CORS error before any route handler runs.

### Local development

No `ALLOWED_ORIGIN` env var is needed locally — the default `http://localhost:8000` allows browser requests from the same origin when running with `uvicorn main:app --reload`.

### Railway deployment

Set `ALLOWED_ORIGIN` in Railway Variables to the full HTTPS URL of your Railway deployment. Example:

```
ALLOWED_ORIGIN=https://midwife-agent-production.up.railway.app
```

Do not include a trailing slash. Do not use `*`.

---

## 3. OAuth Token Handling

### Token delivery mechanism

When the Google OAuth flow completes, the callback at `/auth/google/callback` does **not** expose the token in the browser response. The token JSON is written to the server log only:

```python
logger.info("GOOGLE_TOKEN: %s", json.dumps(tok_dict))
```

The browser receives a generic success page with no credentials.

### Retrieving the token

After completing the OAuth flow at `/auth/google`:

1. Open the Railway dashboard for this deployment.
2. Go to **Deployments → Logs**.
3. Search for `GOOGLE_TOKEN`.
4. Copy the full JSON value from the log line.
5. Paste it into the `GOOGLE_TOKEN` Railway environment variable.
6. Redeploy the service.

Only operators with Railway dashboard access can retrieve the token. The token is never sent to the browser.

### Why this approach

Displaying the token in the browser (the previous approach) exposed it to browser history, browser extensions, and anyone looking over the operator's shoulder. Server-log delivery limits exposure to Railway dashboard users only.

---

## 4. Credential Rotation

### When to rotate

Rotate Google OAuth credentials if:
- A credential has been exposed (browser history, shared screen, public repository)
- A team member with Railway access leaves
- As a periodic security practice (annually or more often)

### Step-by-step rotation

**Critical:** Complete these steps in order. Do not rotate credentials before SEC-03 (the safe callback) is deployed — rotating while the old callback is live would expose the new token in the browser immediately.

1. **Confirm the safe callback is deployed.** Visit `/auth/google/callback` in a browser after a fresh OAuth flow. The page must show only the generic success message — no token JSON, no textarea. If you see a textarea, stop and deploy the SEC-03 fix from the Phase 2 plans first.

2. **Rotate the client secret in Google Cloud Console.**
   - Go to [console.cloud.google.com](https://console.cloud.google.com) → APIs & Services → Credentials.
   - Find the OAuth 2.0 Client ID for this application.
   - Click **Reset Secret** (or delete and recreate the client).
   - Note the new `Client ID` and `Client Secret`.

3. **Update Railway environment variables.**
   - Set `GOOGLE_CLIENT_ID` to the new value.
   - Set `GOOGLE_CLIENT_SECRET` to the new value.
   - Do NOT change `GOOGLE_TOKEN` yet — the old token is still valid for a moment.
   - Redeploy the service.

4. **Re-run the OAuth flow to obtain a new token.**
   - Visit `/auth/google` in a browser.
   - Complete the Google sign-in and consent screen.
   - The callback page will show the generic success message.

5. **Retrieve the new token from Railway Logs.**
   - Go to Railway dashboard → Deployments → Logs.
   - Search for `GOOGLE_TOKEN`.
   - Copy the full JSON value from the log line.

6. **Set the new token in Railway.**
   - Set `GOOGLE_TOKEN` to the copied JSON value.
   - Redeploy the service.

7. **Verify.**
   - Call `GET /api/google/status` (with a valid `Authorization: Bearer <API_KEY>` header).
   - Response must be `{"connected": true, "scopes": [...]}`.
   - Run a calendar smoke test via the chat interface.

### Revoke the old token (optional but recommended)

In Google Cloud Console → APIs & Services → OAuth consent screen, you can review and revoke previously issued tokens. This is optional but recommended after a rotation caused by suspected exposure.

---

## Related files

| File | Purpose |
|------|---------|
| `main.py` | Auth middleware (`require_api_key`), CORS config, OAuth callback |
| `calendar_integration.py` | `get_google_credentials()` — reads `GOOGLE_TOKEN` from env |
| `static/index.html` | Frontend password overlay, Authorization header injection |
| `.planning/phases/02-security-hardening/02-CONTEXT.md` | Full decision log for Phase 2 security choices |
| `README.md` | Environment variable reference (all 11 vars) |
