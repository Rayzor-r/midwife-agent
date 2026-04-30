> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in 04-CONTEXT.md — this log preserves the discussion.

**Date:** 2026-05-01
**Phase:** 04-notes-overhaul
**Mode:** discuss (default)
**Areas discussed:** Module strategy, Past notes integration, Glossary storage, Referral letter format

---

## Discussion Log

### Module strategy

**Question:** The existing note_tidy.py does one-shot formatting with opposing rules to Phase 4 (abbreviations kept, labelled sections). How to handle?

**Options presented:** New notes_engine.py / Extend note_tidy.py / Replace note_tidy.py

**Decision:** New `notes_engine.py`. The two modules serve different purposes and have opposing rules — keeping them separate avoids contaminating the existing tidy behaviour.

---

### Template shapes (requirement correction)

**Mid-discussion correction from user:** The Phase 4 requirement as written (four rigid templates: initial booking, routine antenatal, postnatal check, referral letter) was incorrect. The actual requirement is style-learning from uploaded past notes, not predefined templates.

**Correction stated:** "Every midwife practice writes differently. Rigid templates won't match any real practice. Uploaded past notes ARE the template — they teach the agent what this specific practice's notes look like."

**Outcome:** No predefined template categories. The uploaded past notes corpus is the style source for all note types. Referral letters are the one exception — they accept visible structure because they are correspondence, not clinical notes.

---

### Past notes integration

**Question:** How should the engine access uploaded past notes?

**Initial options:** Download 2–3 at generation time / Separate style cache

**User correction:** Read ALL past notes, not just 2–3. If the corpus exceeds the context window, extract a style profile (paragraph patterns, terminology, acronym usage, structure flow, clinical detail level, tone) and cache it. "Read everything once to learn the style, apply that learning every time."

**Follow-up question:** When should the style profile be built?

**Decision:** Both lazy (first request in a session) AND explicit refresh ("refresh my notes style" in chat). Cache is in-memory — wiped on restart and auto-rebuilt, which is by design (always picks up newly uploaded notes).

**Cold-start fallback:** Generic competent NZ LMC midwife style + seed glossary. Feature is usable before any past notes are uploaded.

---

### Glossary storage

**Question:** Python dict in code or JSON file in repo?

**Decision:** JSON file (`glossary.json`) in repo. Seed list of ~25–35 common LMC acronyms. Additional terms extracted from past notes when style profile is built. Combined glossary applied at generation time via LLM instruction.

---

### Referral letter format

**Question:** Four-section template (Recipient, Reason, Clinical summary, Request) or free-form with header?

**User revision:** Same "uploaded examples first" principle as clinical notes. If past referral letters exist in Drive, learn from those. Four-section template is the cold-start fallback only. Consistent principle: uploaded past documents are always the primary source.

---

## Deferred Ideas

- Persistent style profile storage — deferred to v2.1 (STORE-01 prerequisite)
- Glossary editing UI — future phase
- Te reo Maori term insertion (TEREO-01) — v2.1
- Per-client style profiles — requires multi-tenant architecture (out of v2.0 scope)
