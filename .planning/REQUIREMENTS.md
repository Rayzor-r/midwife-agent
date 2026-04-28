# Requirements: Midwife Agent v1.0 — Foundation Hardening

**Defined:** 2026-04-28
**Core Value:** The agent reliably handles administrative and communication tasks for a working midwife — so that when a new feature or new client is added, there is a safe, auditable foundation to build on.

## v1 Requirements

### Security

- [ ] **SEC-01**: All `/api/*` routes reject requests without a valid `Authorization: Bearer <token>` header matching a secret stored in Railway env vars. Acceptance test: an automated test (or documented manual test using curl) confirms that requests without a valid token to any `/api/*` endpoint return HTTP 401, and requests with a valid token return HTTP 200.
- [ ] **SEC-02**: CORS `allow_origins` restricted to the specific deployment origin (read from `ALLOWED_ORIGIN` env var, defaulting to `http://localhost:8000` for local dev), not `*`.
- [ ] **SEC-03**: The `/auth/google/callback` response does not expose the token in any form — not in the rendered page, the page source, server logs, or any response body. The callback shows only a generic success message. The token is written server-side (to Railway env vars via the Railway API, or logged only to a secured location with explicit instructions).
- [ ] **SEC-04**: Google OAuth credentials (client secret, access token, refresh token) reviewed and rotated given the token was previously rendered in the browser UI.

### Cleanup

- [ ] **CLEAN-01**: `chat_endpoint_patch.py` and `consolidated_patch.py` deleted from repo.
- [ ] **CLEAN-02**: `outlook_integration.py` deleted from repo.
- [ ] **CLEAN-03**: `files.zip` inspected for sensitive content (patient data, credentials), then removed from the working tree and purged from git history using `git filter-repo` or BFG if sensitive content is found.
- [ ] **CLEAN-04**: Root `index.html` deleted (canonical UI is `static/index.html`).
- [ ] **CLEAN-05**: Claude model string centralised — one `CLAUDE_MODEL` env-var read in `main.py`; `note_tidy.py` and `email_watcher.py` read from env or accept the model as a parameter rather than hardcoding separate string literals.
- [ ] **CLEAN-06**: `.gitignore` verified to include `.env`, `*.token`, `*.key`, `*.pem`, and common credential file patterns. Confirm no real credentials are currently committed to git history (via `git log --all -p` scan or equivalent).

### Documentation

- [ ] **DOC-01**: `SECURITY.md` created documenting the auth model (Bearer token), CORS policy, OAuth token handling, and step-by-step credential rotation instructions.
- [ ] **DOC-02**: `README.md` updated (or created) with a complete environment variable reference covering at minimum: `API_KEY`, `ALLOWED_ORIGIN`, `CLAUDE_MODEL`, `ANTHROPIC_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_TOKEN`, `GOOGLE_DRIVE_FOLDER_ID`, `GOOGLE_DRIVE_NOTES_FOLDER_ID`, `PORT`, `RAILWAY_PUBLIC_DOMAIN`.

## v2 Requirements

### Security (deferred)

- **SEC-V2-01**: CSRF protection on state-mutating endpoints (calendar create/update/delete, email draft)
- **SEC-V2-02**: Audit log of agent actions (calendar events created, emails drafted, notes tidied) with timestamp and triggering query

### Infrastructure (deferred)

- **INFRA-V2-01**: Persistent document store — chunks survive redeploys (SQLite or file-based)
- **INFRA-V2-02**: Semantic/vector search replacing keyword RAG
- **INFRA-V2-03**: Email watcher thread health check — restart on silent death; `watcher_status` reflects actual thread liveness

## Out of Scope

| Feature | Reason |
|---------|--------|
| New agent capabilities or chat features | No new features this milestone — hardening only |
| Midwife-specific knowledge base | Future milestone — GC Advisory KB stays for now |
| Branding changes | Future milestone |
| Practice Vitals seminar funnel | Future milestone |
| Multi-tenant / per-client replication | Future milestone |
| Outlook / Microsoft Graph integration | Deferred indefinitely |
| User login / session auth | Out of scope — single-user Bearer token is sufficient |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SEC-01 | Phase 2 | Pending |
| SEC-02 | Phase 2 | Pending |
| SEC-03 | Phase 2 | Pending |
| SEC-04 | Phase 2 | Pending |
| CLEAN-01 | Phase 1 | Pending |
| CLEAN-02 | Phase 1 | Pending |
| CLEAN-03 | Phase 1 | Pending |
| CLEAN-04 | Phase 1 | Pending |
| CLEAN-05 | Phase 1 | Pending |
| CLEAN-06 | Phase 1 | Pending |
| DOC-01 | Phase 3 | Pending |
| DOC-02 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-28*
*Last updated: 2026-04-28 after roadmap creation*
