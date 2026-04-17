"""
Google Drive Integration — Midwife Agent
Auto-indexes documents from a Drive folder into the RAG knowledge base
GC Advisory — gcadvisory.co.nz
"""

import io
import os
import re
import time
from typing import Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

SUPPORTED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "application/vnd.google-apps.document": "gdoc",  # Google Docs — export as docx
}

# Track last sync time to avoid re-indexing unchanged files
_last_sync: dict = {}  # { file_id: modified_time }


def _drive_service(creds: Credentials):
    return build("drive", "v3", credentials=creds)


# ── File listing ───────────────────────────────────────────────────────────────

def list_drive_files(creds: Credentials, folder_id: Optional[str] = None) -> list[dict]:
    """
    List all supported files in a Drive folder.
    If folder_id is None, uses GOOGLE_DRIVE_FOLDER_ID env var.
    Falls back to root My Drive if neither is set.
    """
    svc = _drive_service(creds)
    fid = folder_id or os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    mime_filter = " or ".join(f"mimeType='{m}'" for m in SUPPORTED_MIME_TYPES)

    if fid:
        query = f"('{fid}' in parents) and ({mime_filter}) and trashed=false"
    else:
        query = f"({mime_filter}) and trashed=false"

    try:
        result = svc.files().list(
            q=query,
            fields="files(id,name,mimeType,modifiedTime,size)",
            orderBy="modifiedTime desc",
            pageSize=50,
        ).execute()
        return result.get("files", [])
    except HttpError as e:
        raise RuntimeError(f"Drive API error: {e}")


def get_new_or_modified_files(creds: Credentials, folder_id: Optional[str] = None) -> list[dict]:
    """Return only files that are new or modified since last sync."""
    all_files = list_drive_files(creds, folder_id)
    changed = []
    for f in all_files:
        fid = f["id"]
        mod = f.get("modifiedTime", "")
        if fid not in _last_sync or _last_sync[fid] != mod:
            changed.append(f)
    return changed


def mark_synced(file_id: str, modified_time: str):
    _last_sync[file_id] = modified_time


# ── File download & extraction ─────────────────────────────────────────────────

def download_file(creds: Credentials, file_id: str, mime_type: str) -> bytes:
    """Download a file from Drive. Exports Google Docs to docx."""
    svc = _drive_service(creds)
    try:
        if mime_type == "application/vnd.google-apps.document":
            # Export Google Doc as docx
            request = svc.files().export_media(
                fileId=file_id,
                mimeType="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        else:
            request = svc.files().get_media(fileId=file_id)

        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue()
    except HttpError as e:
        raise RuntimeError(f"Drive download error: {e}")


def extract_text_from_bytes(file_bytes: bytes, filename: str) -> str:
    """Extract text from PDF, DOCX, or TXT bytes."""
    import io as _io
    from pathlib import Path
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        import pdfplumber
        parts = []
        with pdfplumber.open(_io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    parts.append(t)
        return "\n\n".join(parts)

    if ext == ".docx":
        from docx import Document
        doc = Document(_io.BytesIO(file_bytes))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())

    if ext in (".txt", ".md"):
        return file_bytes.decode("utf-8", errors="replace")

    raise ValueError(f"Unsupported: {ext}")


# ── Full sync ──────────────────────────────────────────────────────────────────

def sync_drive_to_knowledge_base(
    creds: Credentials,
    document_store: dict,
    chunk_fn,
    folder_id: Optional[str] = None,
    force_full: bool = False,
) -> dict:
    """
    Sync Drive folder into the in-memory document_store.
    Only processes new or modified files unless force_full=True.
    Returns summary of what was added/updated/removed.
    """
    import uuid

    files = list_drive_files(creds, folder_id) if force_full else get_new_or_modified_files(creds, folder_id)
    drive_ids = {f["id"] for f in list_drive_files(creds, folder_id)}

    # Remove documents that no longer exist in Drive
    stale = [doc_id for doc_id, doc in document_store.items()
             if doc.get("drive_file_id") and doc["drive_file_id"] not in drive_ids]
    for doc_id in stale:
        del document_store[doc_id]

    added, updated, errors = [], [], []

    for f in files:
        file_id   = f["id"]
        filename  = f["name"]
        mime_type = f["mimeType"]
        mod_time  = f.get("modifiedTime", "")

        # Use .docx extension for Google Docs
        if mime_type == "application/vnd.google-apps.document":
            filename = filename + ".docx"

        try:
            file_bytes = download_file(creds, file_id, mime_type)
            text = extract_text_from_bytes(file_bytes, filename)
        except Exception as e:
            errors.append({"file": filename, "error": str(e)})
            continue

        if not text.strip():
            continue

        # Find existing entry for this drive file or create new
        existing_doc_id = next(
            (doc_id for doc_id, doc in document_store.items()
             if doc.get("drive_file_id") == file_id), None
        )
        doc_id = existing_doc_id or str(uuid.uuid4())[:8]
        chunks = chunk_fn(text, doc_id, filename)

        document_store[doc_id] = {
            "id":            doc_id,
            "name":          filename,
            "drive_file_id": file_id,
            "chunks":        chunks,
            "chunk_count":   len(chunks),
            "char_count":    len(text),
            "uploaded_at":   mod_time,
            "source":        "google_drive",
        }

        mark_synced(file_id, mod_time)

        if existing_doc_id:
            updated.append(filename)
        else:
            added.append(filename)

    return {
        "added":   added,
        "updated": updated,
        "removed": stale,
        "errors":  errors,
        "total_docs": len(document_store),
    }
