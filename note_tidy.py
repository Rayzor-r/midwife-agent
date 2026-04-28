"""
Note Tidy — Midwife Agent
Reformats de-identified shorthand notes into a standard structure.

Design rules (non-negotiable):
1. Never change the midwife's wording. Abbreviations stay as abbreviations.
2. Never add information not present in the note.
3. Never save output automatically — return to caller only.
4. Flag ambiguities at the top of the output rather than silently resolving.
5. Never treat the notes as RAG content — this is a one-shot transform,
   not indexed anywhere.
6. De-identification is the midwife's responsibility before upload.
   This module does no identifier scrubbing.

GC Advisory — gcadvisory.co.nz
"""

import json
import os
from datetime import datetime
from typing import Optional

import anthropic
from google.oauth2.credentials import Credentials

from drive_integration import (
    download_file,
    extract_text_from_bytes,
    list_drive_files,
)

# ── Config ────────────────────────────────────────────────────────────────────

# Separate folder from the RAG knowledge base folder. Set this in Railway.
NOTES_FOLDER_ENV = "GOOGLE_DRIVE_NOTES_FOLDER_ID"

# Track processed notes so we don't re-tidy unchanged files.
_processed: dict = {}  # {file_id: modified_time}


# ── System prompt ─────────────────────────────────────────────────────────────

TIDY_SYSTEM_PROMPT = """You are a formatter for de-identified midwifery practice notes. Your only job is to take shorthand notes and lay them out in a standard structure. You are not a clinician, not an editor, and not a summariser.

ABSOLUTE RULES:
1. Never change the midwife's wording. Abbreviations stay as abbreviations (SROM stays SROM, FH stays FH, VE stays VE, etc.). Spelling stays as written.
2. Never add clinical information. If a field is not in the note, it does not appear in the output. Do not write "BP: not recorded" or "FH: not documented". Just omit the field entirely.
3. Never interpret or infer. If the note says "VE 4cm", that is what goes in. Do not add "cervix 4cm dilated".
4. Never reorder time-stamped entries. Labour notes must stay in the exact chronological order the midwife wrote them.
5. If anything is genuinely ambiguous (unclear abbreviation, contradictory times, an obvious typo that could change meaning), list it under "Flags for review" at the top. Do not fix it.

VISIT TYPE DETECTION:
Decide which template applies based on note content:
- Antenatal visit: mentions gestation, antenatal obs, fundal height, FH without labour context
- Labour notes: mentions contractions, SROM/ROM, VE with dilation, time-stamped progression
- Postnatal visit: mentions days postnatal, baby feeding/weight/output, maternal perineum/lochia
- Unsure: use "General visit note" template and flag it

TEMPLATES:

ANTENATAL VISIT
Gestation: [from note, e.g. "38/40"]
Subjective: [what the woman reported, in her midwife's wording]
Objective: [observations, measurements, in note order]
Plan: [next steps, if mentioned]

LABOUR NOTES
Gestation: [from note]
[Time] — [entry in exact order]
[Time] — [entry in exact order]
(continue in chronological order as written)

POSTNATAL VISIT
Day postnatal: [from note]
Maternal: [mother's obs/concerns, in note order]
Baby: [baby's obs/concerns, in note order]
Plan: [next steps, if mentioned]

GENERAL VISIT NOTE
[Reproduce content in logical groupings without changing wording]

OUTPUT FORMAT:
Start with "Flags for review:" section only if there are flags. Omit if none.
Then the appropriate template.
Nothing else. No preamble, no summary, no commentary."""


# ── Drive helpers ─────────────────────────────────────────────────────────────

def list_note_files(creds: Credentials) -> list[dict]:
    """List files in the notes folder (separate from the RAG folder)."""
    folder_id = os.getenv(NOTES_FOLDER_ENV)
    if not folder_id:
        raise RuntimeError(
            f"{NOTES_FOLDER_ENV} not set. Create a dedicated Drive folder for "
            f"notes and set its ID in Railway variables."
        )
    return list_drive_files(creds, folder_id=folder_id)


def get_unprocessed_notes(creds: Credentials) -> list[dict]:
    """Return only notes that haven't been tidied yet, or have been modified."""
    files = list_note_files(creds)
    return [
        f for f in files
        if f["id"] not in _processed or _processed[f["id"]] != f.get("modifiedTime", "")
    ]


def mark_processed(file_id: str, modified_time: str):
    _processed[file_id] = modified_time


# ── Core tidy function ────────────────────────────────────────────────────────

def tidy_note_text(note_text: str) -> dict:
    """
    Send one note's text to Claude for tidying.
    Returns {original, tidied, flags, model, at}.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    if not note_text or not note_text.strip():
        raise ValueError("Empty note")

    client = anthropic.Anthropic(api_key=api_key)

    resp = client.messages.create(
        model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5"),
        max_tokens=2000,
        system=TIDY_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Tidy this note:\n\n---\n{note_text}\n---"
        }],
    )

    tidied = "".join(b.text for b in resp.content if b.type == "text").strip()

    # Extract flags section if present, for separate display in the UI.
    flags = []
    if tidied.lower().startswith("flags for review"):
        lines = tidied.split("\n")
        flag_lines = []
        body_start = len(lines)
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() and not line.startswith("-") and not line.startswith("•"):
                # End of flags section.
                body_start = i
                break
            if line.strip():
                flag_lines.append(line.strip().lstrip("-• ").strip())
        flags = flag_lines
        tidied = "\n".join(lines[body_start:]).strip()

    return {
        "original": note_text,
        "tidied":   tidied,
        "flags":    flags,
        "model":    resp.model,
        "at":       datetime.utcnow().isoformat() + "Z",
    }


def tidy_note_file(creds: Credentials, file_id: str, filename: str,
                   mime_type: str) -> dict:
    """Download a note from Drive, extract text, tidy it, return result."""
    file_bytes = download_file(creds, file_id, mime_type)

    # Match drive_integration behaviour — Google Docs get a .docx extension.
    if mime_type == "application/vnd.google-apps.document" and not filename.endswith(".docx"):
        filename = filename + ".docx"

    text = extract_text_from_bytes(file_bytes, filename)
    if not text.strip():
        raise ValueError(f"No text extracted from {filename}")

    result = tidy_note_text(text)
    result["filename"] = filename
    result["file_id"]  = file_id
    return result


# ── Batch processing ──────────────────────────────────────────────────────────

def tidy_all_unprocessed(creds: Credentials, max_files: int = 10) -> dict:
    """
    Process up to max_files unprocessed notes from the Drive notes folder.
    Returns results array — caller (the UI) decides what to do with them.
    Nothing is saved back to Drive or indexed anywhere.
    """
    all_unprocessed = get_unprocessed_notes(creds)
    files = all_unprocessed[:max_files]
    results, errors = [], []

    for f in files:
        try:
            result = tidy_note_file(creds, f["id"], f["name"], f["mimeType"])
            results.append(result)
            mark_processed(f["id"], f.get("modifiedTime", ""))
        except Exception as e:
            errors.append({"file": f["name"], "error": str(e)})

    return {
        "processed": len(results),
        "results":   results,
        "errors":    errors,
        "remaining": max(0, len(all_unprocessed) - len(results)),
    }
