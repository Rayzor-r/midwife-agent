"""
Notes Engine — Midwife Agent
Generates SOAP-structured clinical note prose from bullet-point observations.
Uses uploaded past notes from Google Drive as style exemplars.
Acronyms expanded via seed glossary (glossary.json) plus terms derived from corpus.

Design rules:
1. Style profile is NEVER written to disk — in-memory only (Railway has no persistent FS).
2. note_tidy.py is untouched — this module serves a different purpose.
3. Abbreviations in INPUT bullets are EXPANDED in output (opposite of note_tidy.py).
4. Output is continuous prose paragraphs — no visible subheadings, no markdown headers.
5. Cold-start (no uploaded notes) is graceful and usable.
GC Advisory — gcadvisory.co.nz
"""

import json
import logging
import os
import re as _re
from pathlib import Path
from typing import Optional

import anthropic
from google.oauth2.credentials import Credentials

from drive_integration import (
    download_file,
    extract_text_from_bytes,
    list_drive_files,
)

logger = logging.getLogger(__name__)

# ── Glossary ──────────────────────────────────────────────────────────────────

_GLOSSARY_PATH = Path(__file__).parent / "glossary.json"

def _load_seed_glossary() -> dict:
    try:
        with open(_GLOSSARY_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Could not load glossary.json: %s", e)
        return {}

SEED_GLOSSARY: dict = _load_seed_glossary()

# ── Style profile cache ────────────────────────────────────────────────────────

_style_profile: Optional[dict] = None
# Shape: {"prose_description": str, "derived_glossary": dict, "notes_read": int}

# ── Style profile builder ─────────────────────────────────────────────────────
# (Implementation in notes_engine_style.py — stub here for cold-start only)

def _cold_start_prompt() -> str:
    return (
        "You are writing a clinical note on behalf of a competent, experienced New Zealand "
        "Lead Maternity Carer (LMC) midwife. Write in the style of an experienced NZ LMC: "
        "professional but concise, continuous prose paragraphs, no subheadings or labels. "
        "The note should read as if written by the midwife herself — warm, precise, and clinical."
    )

def _get_style_prompt() -> str:
    """Return style description for the system prompt — cached or cold-start."""
    if _style_profile:
        return _style_profile["prose_description"]
    return _cold_start_prompt()

def _get_combined_glossary() -> dict:
    """Merge seed glossary with any derived terms from the style profile."""
    combined = dict(SEED_GLOSSARY)
    if _style_profile and _style_profile.get("derived_glossary"):
        combined.update(_style_profile["derived_glossary"])
    return combined

# ── System prompt builder ─────────────────────────────────────────────────────

def _build_generation_prompt(note_type: Optional[str], combined_glossary: dict) -> str:
    glossary_lines = "\n".join(
        f"  {abbr}: {expansion}" for abbr, expansion in sorted(combined_glossary.items())
    )

    note_type_instruction = ""
    if note_type and note_type.lower() == "referral":
        note_type_instruction = (
            "\n\nThis is a REFERRAL LETTER. If the style profile does not contain referral "
            "letter examples, use this four-section structure (the only case where visible "
            "section labels are acceptable):\n"
            "  Recipient: [name, role, facility]\n"
            "  Reason for referral: [1-2 sentences]\n"
            "  Clinical summary: [relevant history and current obs as prose paragraphs]\n"
            "  Request: [what the midwife is asking the recipient to do]"
        )

    return f"""{_get_style_prompt()}

STRICT OUTPUT RULES:
1. Write ONLY continuous prose paragraphs. No markdown headers, no # symbols, no ** bold ** section labels, no bullet points in the output.
2. The SOAP structure (Subjective, Objective, Assessment, Plan) must flow implicitly through paragraph order — never as visible labels.
3. Expand ALL acronyms using the glossary below. Write the full term, not the abbreviation.
4. Do not add clinical information not present in the input bullets.
5. Do not use form-filling language ("BP: 120/80"). Write it as prose: "Blood pressure was 120/80."
6. The note must be ready to copy directly into a clinical record — no preamble, no closing remarks.
{note_type_instruction}

ACRONYM GLOSSARY (always expand these in your output):
{glossary_lines}
"""

# ── Note type detection ────────────────────────────────────────────────────────

_REFERRAL_SIGNALS = {
    "refer", "referral", "letter to", "obstetrician", "specialist",
    "consultant", "re:", "dear dr", "dear nurse",
}

def auto_detect_note_type(bullets: str) -> str:
    """
    Infer whether the bullet input describes a clinical note or a referral letter.
    Returns "referral" if any referral signal keyword is found (case-insensitive).
    Returns "clinical" otherwise.
    """
    text_lower = bullets.lower()
    for signal in _REFERRAL_SIGNALS:
        if signal in text_lower:
            return "referral"
    return "clinical"

# ── Output compliance ─────────────────────────────────────────────────────────

_MARKDOWN_HEADER_RE = _re.compile(r"^#{1,6}\s")
_BOLD_SECTION_RE    = _re.compile(r"^\*\*[A-Za-z ]+\*\*:?\s*$")
_BULLET_LINE_RE     = _re.compile(r"^[-*]\s")
_SOAP_LABEL_RE      = _re.compile(r"^(Subjective|Objective|Assessment|Plan):\s", _re.IGNORECASE)
_SOAP_ABBREV_RE     = _re.compile(r"^[SOAP]:\s")

def _check_output_compliance(note_text: str) -> dict:
    """
    Check generated note text against ACC/DHB LMC documentation format requirements.
    Returns {"passed": bool, "violations": list[str], "warnings": list[str]}.
    Does NOT suppress the note — compliance result is informational.
    """
    violations: list[str] = []
    warnings:   list[str] = []

    for i, line in enumerate(note_text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if _MARKDOWN_HEADER_RE.match(stripped):
            violations.append(f"Line {i}: markdown header '{stripped[:40]}'")
        elif _BOLD_SECTION_RE.match(stripped):
            violations.append(f"Line {i}: bold section label '{stripped[:40]}'")
        elif _BULLET_LINE_RE.match(stripped):
            violations.append(f"Line {i}: bullet point in output '{stripped[:40]}'")
        elif _SOAP_LABEL_RE.match(stripped):
            violations.append(f"Line {i}: explicit SOAP label '{stripped[:40]}'")
        elif _SOAP_ABBREV_RE.match(stripped):
            violations.append(f"Line {i}: abbreviated SOAP label '{stripped[:40]}'")

    return {
        "passed":     len(violations) == 0,
        "violations": violations,
        "warnings":   warnings,
    }

# ── Core generation ───────────────────────────────────────────────────────────

def generate_note(
    bullets: str,
    creds: Optional[Credentials] = None,
    note_type: Optional[str] = None,
) -> dict:
    """
    Generate a SOAP clinical note from bullet-point observations.

    Args:
        bullets: Raw bullet-point observations from the midwife.
        creds: Google credentials (used to build style profile if not yet cached).
        note_type: Optional hint — "referral" triggers the letter format.
                   None means auto-detect from bullet content.

    Returns:
        {
            "note": str,
            "note_type": str,
            "glossary_terms_used": list[str],
            "style_source": str,
            "compliance": {"passed": bool, "violations": list, "warnings": list},
        }
    """
    global _style_profile

    # Attempt lazy style profile build on first call
    if _style_profile is None and creds is not None:
        try:
            from notes_engine_style import build_style_profile
            _style_profile = build_style_profile(creds)
        except ImportError:
            pass  # notes_engine_style not yet present — cold-start
        except Exception as e:
            logger.warning("Style profile build failed, using cold-start: %s", e)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    combined_glossary = _get_combined_glossary()

    # Detect which acronyms appear in the input (for reporting)
    input_upper = bullets.upper()
    glossary_terms_used = [
        abbr for abbr in combined_glossary
        if abbr in input_upper
    ]

    resolved_note_type = note_type if note_type else auto_detect_note_type(bullets)
    system_prompt = _build_generation_prompt(resolved_note_type, combined_glossary)

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5"),
        max_tokens=2048,
        system=system_prompt,
        messages=[{
            "role": "user",
            "content": f"Write a clinical note from these observations:\n\n{bullets}",
        }],
    )

    note_text = "".join(b.text for b in resp.content if b.type == "text").strip()

    compliance = _check_output_compliance(note_text)
    if not compliance["passed"]:
        logger.warning("Generated note failed compliance check: %s", compliance["violations"])

    return {
        "note": note_text,
        "note_type": resolved_note_type,
        "glossary_terms_used": glossary_terms_used,
        "style_source": "drive_corpus" if _style_profile else "cold_start",
        "compliance": compliance,
    }


def refresh_style_profile(creds: Credentials) -> dict:
    """
    Force-rebuild the style profile from the Drive notes corpus.
    Returns {"status": "ok", "notes_read": int} or {"status": "error", "error": str}.
    """
    global _style_profile
    try:
        from notes_engine_style import build_style_profile
        _style_profile = build_style_profile(creds)
        return {"status": "ok", "notes_read": _style_profile.get("notes_read", 0)}
    except ImportError:
        return {"status": "error", "error": "Style profile builder not yet available"}
    except Exception as e:
        logger.error("Style profile refresh failed: %s", e)
        return {"status": "error", "error": str(e)}
