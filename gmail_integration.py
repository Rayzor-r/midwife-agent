"""
Gmail Integration — Midwife Agent
Full email management via Gmail API
Read inbox, create drafts, reply to threads — midwife always reviews before sending
GC Advisory — gcadvisory.co.nz
"""

import base64
import email as email_lib
import os
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def _gmail_service(creds: Credentials):
    return build("gmail", "v1", credentials=creds)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _decode_body(payload: dict) -> str:
    """Extract plain text or HTML body from a Gmail message payload."""
    body = ""
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    elif mime_type == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    elif "parts" in payload:
        # Prefer plain text, fall back to html
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                    break
        if not body:
            for part in payload["parts"]:
                if part.get("mimeType") == "text/html":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                        break

    return body


def _get_header(headers: list, name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _fmt_message(msg: dict) -> dict:
    payload   = msg.get("payload", {})
    headers   = payload.get("headers", [])
    return {
        "id":              msg.get("id"),
        "thread_id":       msg.get("threadId"),
        "subject":         _get_header(headers, "Subject"),
        "from_email":      _get_header(headers, "From"),
        "to":              _get_header(headers, "To"),
        "date":            _get_header(headers, "Date"),
        "snippet":         msg.get("snippet", ""),
        "body":            _decode_body(payload),
        "label_ids":       msg.get("labelIds", []),
        "is_read":         "UNREAD" not in msg.get("labelIds", []),
        "has_attachments": any(
            p.get("filename") for p in payload.get("parts", [])
        ),
    }


# ── Inbox ──────────────────────────────────────────────────────────────────────

def list_inbox(creds: Credentials, max_results: int = 20, unread_only: bool = False) -> list[dict]:
    """Return recent inbox messages."""
    svc = _gmail_service(creds)
    query = "in:inbox"
    if unread_only:
        query += " is:unread"
    try:
        result = svc.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute()
        messages = result.get("messages", [])
        full = []
        for m in messages:
            msg = svc.users().messages().get(
                userId="me", id=m["id"], format="full"
            ).execute()
            full.append(_fmt_message(msg))
        return full
    except HttpError as e:
        raise RuntimeError(f"Gmail error: {e}")


def get_email(creds: Credentials, message_id: str) -> dict:
    """Get a single email with full body."""
    svc = _gmail_service(creds)
    try:
        msg = svc.users().messages().get(
            userId="me", id=message_id, format="full"
        ).execute()
        return _fmt_message(msg)
    except HttpError as e:
        raise RuntimeError(f"Gmail error: {e}")


def get_thread(creds: Credentials, thread_id: str) -> list[dict]:
    """Get all messages in a thread."""
    svc = _gmail_service(creds)
    try:
        thread = svc.users().threads().get(
            userId="me", id=thread_id, format="full"
        ).execute()
        return [_fmt_message(m) for m in thread.get("messages", [])]
    except HttpError as e:
        raise RuntimeError(f"Gmail error: {e}")


def mark_read(creds: Credentials, message_id: str) -> dict:
    """Mark a message as read."""
    svc = _gmail_service(creds)
    try:
        svc.users().messages().modify(
            userId="me", id=message_id,
            body={"removeLabelIds": ["UNREAD"]}
        ).execute()
        return {"marked_read": True, "message_id": message_id}
    except HttpError as e:
        raise RuntimeError(f"Gmail error: {e}")


def search_emails(creds: Credentials, query: str, max_results: int = 10) -> list[dict]:
    """Search emails using Gmail query syntax."""
    svc = _gmail_service(creds)
    try:
        result = svc.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute()
        messages = result.get("messages", [])
        full = []
        for m in messages:
            msg = svc.users().messages().get(
                userId="me", id=m["id"], format="full"
            ).execute()
            full.append(_fmt_message(msg))
        return full
    except HttpError as e:
        raise RuntimeError(f"Gmail error: {e}")


# ── Draft management ───────────────────────────────────────────────────────────

def _build_mime(
    to: list[str],
    subject: str,
    body_html: str,
    cc: Optional[list[str]] = None,
    reply_to_msg: Optional[dict] = None,
) -> MIMEMultipart:
    """Build a MIME message."""
    msg = MIMEMultipart("alternative")
    msg["To"]      = ", ".join(to)
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = ", ".join(cc)
    if reply_to_msg:
        msg["In-Reply-To"] = reply_to_msg.get("id", "")
        msg["References"]  = reply_to_msg.get("id", "")
    msg.attach(MIMEText(body_html, "html"))
    return msg


def create_draft(
    creds: Credentials,
    to: list[str],
    subject: str,
    body_html: str,
    reply_to_id: Optional[str] = None,
    cc: Optional[list[str]] = None,
) -> dict:
    """
    Create a Gmail draft.
    If reply_to_id is given, creates a reply draft in that thread.
    NEVER sends automatically — midwife always reviews first.
    """
    svc = _gmail_service(creds)
    reply_msg = None
    thread_id = None

    if reply_to_id:
        try:
            original = svc.users().messages().get(
                userId="me", id=reply_to_id, format="full"
            ).execute()
            reply_msg = _fmt_message(original)
            thread_id = original.get("threadId")
            # Prepend Re: if not already there
            orig_subject = reply_msg.get("subject", "")
            if not subject.lower().startswith("re:"):
                subject = f"Re: {orig_subject}" if not subject else subject
        except HttpError:
            pass

    mime_msg = _build_mime(to, subject, body_html, cc, reply_msg)
    raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("utf-8")

    draft_body: dict = {"message": {"raw": raw}}
    if thread_id:
        draft_body["message"]["threadId"] = thread_id

    try:
        draft = svc.users().drafts().create(userId="me", body=draft_body).execute()
        return {
            "draft_id": draft.get("id"),
            "subject":  subject,
            "status":   "draft_created",
            "note":     "Draft saved to Gmail. Open Gmail to review and send.",
        }
    except HttpError as e:
        raise RuntimeError(f"Gmail error: {e}")


def update_draft(creds: Credentials, draft_id: str, to: list[str], subject: str, body_html: str) -> dict:
    """Update an existing Gmail draft."""
    svc = _gmail_service(creds)
    mime_msg = _build_mime(to, subject, body_html)
    raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("utf-8")
    try:
        svc.users().drafts().update(
            userId="me", id=draft_id,
            body={"message": {"raw": raw}}
        ).execute()
        return {"draft_id": draft_id, "status": "draft_updated"}
    except HttpError as e:
        raise RuntimeError(f"Gmail error: {e}")


def delete_draft(creds: Credentials, draft_id: str) -> dict:
    """Delete a Gmail draft."""
    svc = _gmail_service(creds)
    try:
        svc.users().drafts().delete(userId="me", id=draft_id).execute()
        return {"deleted": True, "draft_id": draft_id}
    except HttpError as e:
        raise RuntimeError(f"Gmail error: {e}")


def list_drafts(creds: Credentials) -> list[dict]:
    """List all Gmail drafts."""
    svc = _gmail_service(creds)
    try:
        result = svc.users().drafts().list(userId="me", maxResults=20).execute()
        drafts = result.get("drafts", [])
        full = []
        for d in drafts:
            draft = svc.users().drafts().get(userId="me", id=d["id"], format="full").execute()
            msg   = draft.get("message", {})
            full.append({
                "draft_id": d["id"],
                **_fmt_message(msg),
            })
        return full
    except HttpError as e:
        raise RuntimeError(f"Gmail error: {e}")
