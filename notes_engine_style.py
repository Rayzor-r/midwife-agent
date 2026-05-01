"""
Notes Engine — Style Profile Builder
Downloads all past notes from Google Drive and extracts a reusable style profile
via a single LLM call. The style profile is stored in-memory in notes_engine.py.

This module is imported lazily by notes_engine.py — it is only loaded when a
style profile build is triggered (first note generation with creds, or explicit refresh).

GC Advisory — gcadvisory.co.nz
"""

import json
import logging
import os
from typing import Optional

import anthropic
from google.oauth2.credentials import Credentials

from drive_integration import (
    download_file,
    extract_text_from_bytes,
    list_drive_files,
)

logger = logging.getLogger(__name__)

NOTES_FOLDER_ENV = "GOOGLE_DRIVE_NOTES_FOLDER_ID"
MAX_NOTES_FOR_STYLE = 50  # practical cap to avoid token overflow

# ── Corpus assembly ────────────────────────────────────────────────────────────

def _fetch_corpus(creds: Credentials) -> tuple[str, int]:
    """
    Download all past notes from the Drive notes folder and concatenate into one string.
    Returns (corpus_text, notes_read_count).
    Raises RuntimeError if folder env var is missing or Drive call fails.
    """
    folder_id = os.getenv(NOTES_FOLDER_ENV)
    if not folder_id:
        raise RuntimeError(
            f"{NOTES_FOLDER_ENV} not set. Create a dedicated Drive folder for notes "
            "and set its ID in Railway environment variables."
        )

    try:
        files = list_drive_files(creds, folder_id=folder_id)
    except RuntimeError as e:
        raise RuntimeError(f"Drive API error listing notes folder: {e}") from e

    if not files:
        return "", 0

    files = files[:MAX_NOTES_FOR_STYLE]
    sections = []
    notes_read = 0

    for f in files:
        file_id   = f["id"]
        filename  = f["name"]
        mime_type = f["mimeType"]

        # Google Docs export as docx — must fix extension for extract_text_from_bytes
        if mime_type == "application/vnd.google-apps.document":
            if not filename.endswith(".docx"):
                filename = filename + ".docx"

        try:
            file_bytes = download_file(creds, file_id, mime_type)
            text = extract_text_from_bytes(file_bytes, filename)
        except Exception as e:
            logger.warning("Skipping note '%s': %s", f["name"], e)
            continue

        if not text.strip():
            continue

        sections.append(f"=== Note: {f['name']} ===\n{text.strip()}")
        notes_read += 1

    corpus = "\n\n".join(sections)
    return corpus, notes_read


# ── Style extraction prompt ────────────────────────────────────────────────────

_STYLE_EXTRACTION_SYSTEM = """You are analysing a corpus of clinical notes written by a New Zealand Lead Maternity Carer (LMC) midwife. Your job is to extract a reusable style profile that can teach an AI to write new notes in the same style.

Return ONLY valid JSON with no additional text, markdown, or explanation. The JSON must have exactly these keys:

{
  "prose_description": "A detailed description of how this midwife writes — paragraph length and cadence, sentence structure, clinical vocabulary she favours, how clinical data (obs, measurements) are woven into prose, level of formality, tone (warm/clinical/brief), and structural flow (what she puts in each part of a note). This description will be injected directly into a system prompt to make a new note sound like her. Write 150-300 words.",
  "derived_glossary": {
    "ABBR": "full term",
    "ABBR2": "full term 2"
  }
}

For derived_glossary: include ONLY acronyms that appear in the notes corpus that are specific to this practice or rare enough to need definition. Do NOT include common English words or acronyms that are universally understood. Include 0-20 entries. If no practice-specific acronyms are found, return an empty object {}.

If the notes corpus contains referral letters as well as clinical notes, describe both styles separately in prose_description."""

_STYLE_EXTRACTION_USER_TEMPLATE = """Here is the full corpus of past clinical notes from this midwife practice:

{corpus}

Analyse these notes and return the JSON style profile."""


# ── Main entry point ───────────────────────────────────────────────────────────

def build_style_profile(creds: Credentials) -> dict:
    """
    Download all past notes from Drive, extract a style profile via LLM.

    Returns:
        {
            "prose_description": str,   # Style description for system prompt injection
            "derived_glossary": dict,   # Practice-specific acronyms found in corpus
            "notes_read": int,          # Number of notes successfully processed
        }

    Raises:
        RuntimeError: if GOOGLE_DRIVE_NOTES_FOLDER_ID is not set, or if Drive call fails.
    """
    corpus, notes_read = _fetch_corpus(creds)

    if not corpus:
        logger.info("Notes folder is empty — returning empty style profile")
        return {"prose_description": "", "derived_glossary": {}, "notes_read": 0}

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5"),
        max_tokens=1500,
        system=_STYLE_EXTRACTION_SYSTEM,
        messages=[{
            "role": "user",
            "content": _STYLE_EXTRACTION_USER_TEMPLATE.format(corpus=corpus),
        }],
    )

    raw = "".join(b.text for b in resp.content if b.type == "text").strip()

    # Parse LLM response as JSON
    try:
        profile = json.loads(raw)
        prose_description = str(profile.get("prose_description", ""))
        derived_glossary  = dict(profile.get("derived_glossary", {}))
    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning(
            "Style profile JSON parse failed (%s) — using raw text as description. "
            "This may indicate an LLM formatting issue.", e
        )
        prose_description = raw
        derived_glossary  = {}

    logger.info(
        "Style profile built from %d notes; %d derived glossary terms",
        notes_read, len(derived_glossary)
    )

    return {
        "prose_description": prose_description,
        "derived_glossary":  derived_glossary,
        "notes_read":        notes_read,
    }
