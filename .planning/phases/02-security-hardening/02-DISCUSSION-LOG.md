# Phase 2: Security Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in 02-CONTEXT.md — this log preserves the discussion.

**Date:** 2026-04-29
**Phase:** 02-security-hardening
**Mode:** discuss (interactive)
**Areas discussed:** Frontend token wiring

---

## Areas Discussed

### Frontend token wiring (SEC-01)

| Question | Options Presented | Decision |
|----------|------------------|----------|
| How does the browser get the Bearer token? | A: localStorage entry, B: server-injected into HTML | Option A — localStorage |
| Why not Option B (server injection)? | Token would be extractable from page source; undermines SEC-01 | Rejected — security goal evaporates |
| UI pattern for auth prompt | Full-screen overlay vs. banner | Full-screen overlay |
| Input type | Plain text vs. password-masked | `type="password"` with show/hide toggle |
| Label/framing | "API key" vs. "password" | "Enter password" — user-facing, not developer-facing |
| 401 behaviour | Clear key + error vs. silent retry | Clear localStorage + re-show overlay with "That password didn't work. Please try again." |
| Network failure behaviour | Same message as 401 vs. distinct | Distinct — "Couldn't reach the server. Check your connection and try again." |
| Sign-out affordance | None vs. corner link | Small "Sign out" link — clears localStorage, reloads |

**Key revision during discussion:**
Initial framing used "API key" language and random hex string. Revised to:
- API_KEY value = memorable phrase chosen by deployment owner (e.g., "MidwifePractice2026!")
- UI language = "password" throughout
- Rationale: single-user tool; users should experience it as a password, not a developer credential

### OAuth callback (SEC-03) — Claude's recommendation, confirmed by user silence

| Question | Options | Decision |
|----------|---------|----------|
| What replaces the token textarea? | A: server log only, B: Railway API write | Option A — log to Railway, generic success page |
| Rationale | B adds complexity; server logs are sufficient for single-operator tool | Accepted |

### Health endpoint scope — Claude's recommendation, confirmed by user silence

| Question | Options | Decision |
|----------|---------|----------|
| /api/health exempt from auth? | Yes (railway monitor) vs. No (strict /api/* rule) | Yes — exempt |
| Rationale | Railway uptime monitor can't send auth headers; health data (version, google status) not sensitive | Accepted |

---

## Additional Context Captured

- **API_KEY semantics:** One shared password per deployment/practice. Not per-user. Multi-user logins are v2.0.
- **Uniform auth surface:** All clients (browser and programmatic) use the same Bearer token from `API_KEY` env var.
- **SEC-03 before SEC-04:** Ordering constraint noted explicitly — do not rotate credentials while the callback still renders them.
- **Email watcher clarification:** `email_watcher.py` calls Google APIs directly, not FastAPI endpoints — does NOT need updating for SEC-01.

---

## Deferred Ideas

- Per-staff accounts / per-user API keys → v2.0
- CSRF protection → v2.0 (SEC-V2-01)
- Railway API write for OAuth token → future if operational complexity grows
