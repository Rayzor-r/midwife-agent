---
phase: 02-security-hardening
reviewed: 2026-04-29T00:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - main.py
  - static/index.html
findings:
  critical: 4
  warning: 5
  info: 2
  total: 11
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-04-29
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Reviewed `main.py` and `static/index.html` for the Phase 2 Security Hardening changes: logging setup, CORS tightening, API-key middleware, OAuth token handling, and the frontend auth overlay.

The direction is correct — removing the wildcard CORS origin, protecting `/api/*` routes behind a Bearer key, and eliminating the plaintext token textarea are all meaningful improvements. However four blockers were found that each undermine a stated security goal, and five warnings that degrade robustness or create exploitable edge cases. No changes should ship to production without resolving the blockers.

---

## Critical Issues

### CR-01: `API_KEY=""` default passes the auth check when the env var is unset

**File:** `main.py:69`
**Issue:** The middleware logic is:
```python
if not API_KEY or not auth.startswith("Bearer ") or auth[len("Bearer "):] != API_KEY:
    return Response(..., status_code=401, ...)
```
When `API_KEY` is the empty string (the default when the env var is absent), `not API_KEY` is `True`, so the branch is entered and every request is rejected — the app is effectively down. That is bad, but the inverse failure mode is worse: if someone explicitly sets `API_KEY=""` in Railway (clearing the var), the short-circuit means any Bearer token whatsoever would pass if an operator later changes the condition order. More importantly, the current code means there is **no warning at startup** that the key is missing — the app boots silently and then returns 401 to every authenticated call, which is indistinguishable from a wrong password from the user's perspective.

The stated goal of the phase is to *protect* the endpoints. An unconfigured deployment silently breaks the app rather than loudly refusing to start.

**Fix:** Fail fast at startup if `API_KEY` is empty; never treat an empty string as a valid guard:
```python
# In startup_event or immediately after the constant is set:
API_KEY = os.getenv("API_KEY", "")
if not API_KEY:
    import sys
    logger.critical("API_KEY env var is not set — refusing to start")
    sys.exit(1)
```
And simplify the middleware to remove the short-circuit that masks a misconfiguration:
```python
token = auth[len("Bearer "):] if auth.startswith("Bearer ") else ""
if token != API_KEY:
    return Response(...)
```

---

### CR-02: Google OAuth callback logs the full token to a shared log sink (credential exposure)

**File:** `main.py:621`
**Issue:**
```python
logger.info("GOOGLE_TOKEN: %s", json.dumps(tok_dict))
```
The `tok_dict` produced by `credentials_to_dict` contains the OAuth `access_token`, the `refresh_token`, and the `token_uri`. Writing this to `logger.info` means:
- On Railway, **all logs are visible to anyone with dashboard access** (the plan explicitly says "Railway dashboard → Logs").
- If log forwarding is ever enabled (Datadog, Papertrail, etc.) these tokens go into that system too.
- Log retention means the tokens persist long after they are rotated.

The previous implementation (`<textarea>` rendered in the browser) was also bad, but swapping one exposure vector for another is not a fix — it is a change of audience. The token is still in cleartext in a shared system.

**Fix:** Do not log the full credential object. Instead, log a non-sensitive signal and instruct the operator to retrieve the value through a dedicated mechanism (e.g., a one-time admin endpoint that requires the API key, displays the token once, then clears it from memory):
```python
# Log only a safe indicator, never the token value
logger.info("Google OAuth flow completed. Token obtained for scopes: %s",
            list(creds.scopes))
```
If the Railway-log workflow is intentional for this deployment, at minimum redact the token fields:
```python
safe = {k: ("***" if k in ("token", "refresh_token") else v)
        for k, v in tok_dict.items()}
logger.info("GOOGLE_TOKEN_META: %s", json.dumps(safe))
```
And display the actual token value *only* in the HTML response body (served over HTTPS, visible only to the browser of the person who initiated the flow), not in the log.

---

### CR-03: `/auth/google` and `/auth/google/callback` are completely unprotected

**File:** `main.py:605-631`
**Issue:** The API-key middleware only guards paths that start with `/api/`. The OAuth initiation (`/auth/google`) and callback (`/auth/google/callback`) routes start with `/auth/` and are therefore entirely open — no API key required. Any unauthenticated actor who can reach the Railway URL can:
1. Hit `/auth/google` to initiate a new OAuth flow, redirecting the midwife's browser to a consent screen that re-authorizes the app.
2. Deliver a crafted `code` to `/auth/google/callback` from an attacker-controlled authorization server, logging malicious credentials.

These routes should be protected. Since they are used by the operator (not end users), requiring the API key or a separate admin secret is appropriate.

**Fix:** Add `/auth/google` and `/auth/google/callback` to the middleware scope, or apply a dependency check:
```python
EXEMPT_PATHS = {"/api/health"}   # keep as-is
AUTH_PATHS   = {"/auth/google", "/auth/google/callback"}

@app.middleware("http")
async def require_api_key(request: Request, call_next):
    path = request.url.path
    protected = (path.startswith("/api/") and path not in EXEMPT_PATHS) \
                or path in AUTH_PATHS
    if protected:
        auth = request.headers.get("Authorization", "")
        token = auth[len("Bearer "):] if auth.startswith("Bearer ") else ""
        if token != API_KEY:
            return Response(...)
    return await call_next(request)
```

---

### CR-04: XSS via `doc.id` injected unescaped into an `onclick` attribute

**File:** `static/index.html:967`
**Issue:**
```javascript
item.innerHTML = `
  ...
  <button class="doc-del" onclick="delDoc('${doc.id}')" title="Remove">✕</button>`;
```
`doc.id` is a server-supplied value (from `/api/documents`). It is inserted directly into an `onclick` string attribute without escaping. A malicious document name (or a compromised backend) could return a `doc.id` containing `'); evil(); ('`, which would execute arbitrary JavaScript in the page context.

While `doc.id` is currently generated as an 8-character UUID slice in `main.py:577` (`str(uuid.uuid4())[:8]`), the frontend must not trust that this will always be safe. The frontend and backend are independent layers; the frontend should defend itself.

**Fix:** Use `data-*` attributes and a delegated event listener instead of inline `onclick`:
```javascript
// In renderDocs, replace the onclick with a data attribute:
item.innerHTML = `
  ...
  <button class="doc-del" data-id="${esc(doc.id)}" title="Remove">✕</button>`;

// Then attach the listener:
item.querySelector('.doc-del').addEventListener('click', () => delDoc(doc.id));
```
The `esc()` helper already exists on line 877 and handles `&`, `<`, `>`, `"`. Use it.

---

## Warnings

### WR-01: `logging.basicConfig` is called inside `startup_event`, after `logger` is already used

**File:** `main.py:840-841`
**Issue:**
```python
@app.on_event("startup")
async def startup_event():
    import logging
    logging.basicConfig(level=logging.INFO)
```
`logger = logging.getLogger(__name__)` is assigned at module level (line 30). Any log calls that happen at import time or during app setup — including the `logger.info("GOOGLE_TOKEN: %s", ...)` on line 621 if the callback fires before startup completes — will use a logger with no handlers configured. Under Python's logging default, a `lastResort` handler writes WARNING and above to stderr, but INFO messages are silently dropped.

This means the `GOOGLE_TOKEN` log line (the intended delivery mechanism for the OAuth token) may produce no output at all if `basicConfig` has not been called yet. On Railway, app startup is sequential, so in practice this is unlikely — but it is a brittle ordering dependency.

**Fix:** Move `logging.basicConfig(level=logging.INFO)` to module level, immediately after the `import logging` at line 12, and remove the duplicate `import logging` inside `startup_event`:
```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
```

---

### WR-02: `setStreaming(false)` called without a status label in the 401 handler

**File:** `static/index.html:667`
**Issue:**
```javascript
setStreaming(false);
```
`setStreaming` sets `statusTxt.textContent = label` (line 749). When `label` is `undefined`, the status indicator is blanked out and shows nothing. The `sendMessage` function always calls `setStreaming(false, 'Ready')` at the end, but the `return` on line 669 exits before reaching it. The status pill is left empty after a 401, which is confusing to the user.

**Fix:**
```javascript
setStreaming(false, 'Ready');
```

---

### WR-03: `hadKey` logic reads `localStorage` after it has already been cleared

**File:** `static/index.html:662-666` (and mirrored at lines 906-910, 928-932, 976-980)
**Issue:**
```javascript
const hadKey = !!localStorage.getItem('api_key');
localStorage.removeItem('api_key');
showAuthOverlay(hadKey ? '...' : '...');
```
The `hadKey` read and the `removeItem` call are on consecutive lines with no async gap, so the value is always captured correctly before removal. However, the pattern is repeated identically in four separate 401 handlers (`/api/chat`, `/api/upload`, `/api/documents`, `/api/documents/:id`). This duplication means the message logic is four separate places to update, and three of the four handlers do NOT call `setStreaming(false, ...)` — so a 401 mid-upload leaves `state.streaming = true`, permanently disabling the Send button for the session.

In `uploadFile` (line 905-911), after a 401 the upload progress spinner (`uploadProg`) is never hidden either because the `return` exits before `finally` — wait, `finally` does run regardless. But `state.streaming` is never reset in `uploadFile`.

More critically: in `delDoc` (line 975-981), there is no streaming state to reset, but the function does not call `loadDocs()` after showing the overlay — which is actually correct — but it also does not set the button states, leaving the UI in an indeterminate state.

**Fix:** Extract a shared `handle401()` helper:
```javascript
function handle401() {
  const hadKey = !!localStorage.getItem('api_key');
  localStorage.removeItem('api_key');
  setStreaming(false, 'Ready');
  showAuthOverlay(hadKey
    ? "That password didn't work. Please try again."
    : "This app now requires a password. Enter the password your administrator gave you.");
}
```
And call it at each of the four sites.

---

### WR-04: `handleAuthSubmit` does not verify the password against the server before hiding the overlay

**File:** `static/index.html:1049-1056`
**Issue:**
```javascript
function handleAuthSubmit() {
  const val = document.getElementById('auth-input').value.trim();
  if (!val) return;
  localStorage.setItem('api_key', val);
  localStorage.setItem('auth_upgrade_seen', '1');
  hideAuthOverlay();
  loadDocs();
}
```
The overlay is hidden immediately on any non-empty input before the password has been validated by the server. `loadDocs()` is called async; if it returns 401 the overlay reappears. But between `hideAuthOverlay()` and the 401 response, the full app UI is briefly visible to an attacker entering garbage. More importantly, if the `loadDocs()` network request fails for any reason other than 401 (e.g., a 500 or network timeout), the overlay stays hidden permanently with a bad key in localStorage — the user is "authenticated" with a broken key and all subsequent API calls will silently fail.

**Fix:** Do not hide the overlay until the first API call succeeds:
```javascript
async function handleAuthSubmit() {
  const val = document.getElementById('auth-input').value.trim();
  if (!val) return;
  localStorage.setItem('api_key', val);
  localStorage.setItem('auth_upgrade_seen', '1');
  // Verify before hiding
  const res = await fetch('/api/documents', {
    headers: { 'Authorization': 'Bearer ' + val }
  });
  if (res.status === 401) {
    localStorage.removeItem('api_key');
    document.getElementById('auth-error').textContent = 'Incorrect password.';
    return;
  }
  hideAuthOverlay();
  // loadDocs will use the stored key on next call
  state.docs = await res.json();
  renderDocs();
}
```

---

### WR-05: CORS `allow_credentials` is absent while the CORS origin is now restricted

**File:** `main.py:46`
**Issue:**
```python
app.add_middleware(CORSMiddleware,
    allow_origins=[os.getenv("ALLOWED_ORIGIN", "http://localhost:8000")],
    allow_methods=["*"],
    allow_headers=["*"])
```
`allow_credentials` defaults to `False` in Starlette's CORSMiddleware. This is correct since the app uses `Authorization` header tokens, not cookies. However, `allow_headers=["*"]` combined with a specific origin and no `allow_credentials` means the `Authorization` header is permitted on cross-origin requests without credential cookies — which is the intended design, so the CORS config is not itself broken.

The warning is that `ALLOWED_ORIGIN` defaults to `http://localhost:8000`, which is the same host as the server. On Railway, the actual public domain is in `RAILWAY_PUBLIC_DOMAIN`. If `ALLOWED_ORIGIN` is not explicitly set, production cross-origin requests from any custom domain (or HTTPS variant) will be blocked by CORS — yet the app will appear to work when accessed directly at the Railway URL because same-origin requests bypass CORS entirely. This creates a silent production misconfiguration that is hard to diagnose.

**Fix:** Log a startup warning if `ALLOWED_ORIGIN` is the localhost default in a production environment:
```python
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "")
if not ALLOWED_ORIGIN:
    if os.getenv("RAILWAY_PUBLIC_DOMAIN"):
        ALLOWED_ORIGIN = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}"
        logger.warning("ALLOWED_ORIGIN not set; defaulting to %s", ALLOWED_ORIGIN)
    else:
        ALLOWED_ORIGIN = "http://localhost:8000"
```

---

## Info

### IN-01: `typingEl` use-before-check in the `catch` block

**File:** `static/index.html:724-726`
**Issue:**
```javascript
} catch (err) {
  typingEl?.remove();
```
`typingEl` is assigned from `appendTyping()` before the `try` block (line 647), so it is always defined — the optional chaining `?.` is unnecessary. More importantly, after the `data.text` branch fires on line 695, `typingEl.remove()` is called (line 696, without `?.`). If an error is thrown *after* the typing element has been removed, the `catch` block's `typingEl?.remove()` silently no-ops on a detached node. This is harmless but indicates the error recovery path was not fully reasoned through.

**Suggestion:** No code change is strictly required, but a comment clarifying the intent would reduce confusion.

---

### IN-02: Duplicate `import logging` inside `startup_event`

**File:** `main.py:840`
**Issue:**
```python
@app.on_event("startup")
async def startup_event():
    import logging
    logging.basicConfig(level=logging.INFO)
```
`logging` is already imported at the top of the module (line 12). The inline `import logging` inside the function is dead code — Python will re-use the cached module, but it reads as if `logging` is not available at module scope, which is misleading.

**Fix:** Remove the inline `import logging` from `startup_event`. This is also addressed by fixing WR-01.

---

_Reviewed: 2026-04-29_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
