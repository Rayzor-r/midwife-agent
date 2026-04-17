"""
Outlook Email Integration — Midwife Agent
Full email management via Microsoft Graph API
Read inbox, create drafts, reply to threads — midwife always reviews before sending
GC Advisory — gcadvisory.co.nz
"""

import json
import os
from datetime import datetime
from typing import Optional

import requests
from msal import ConfidentialClientApplication

GRAPH_BASE  = "https://graph.microsoft.com/v1.0"
MS_SCOPES   = ["Mail.ReadWrite", "offline_access"]


# ── Auth ───────────────────────────────────────────────────────────────────────

def get_ms_app() -> ConfidentialClientApplication:
    return ConfidentialClientApplication(
        client_id=os.getenv("MS_CLIENT_ID"),
        client_credential=os.getenv("MS_CLIENT_SECRET"),
        authority=f"https://login.microsoftonline.com/{os.getenv('MS_TENANT_ID', 'common')}",
    )


def get_ms_token() -> Optional[str]:
    """Get access token from OUTLOOK_TOKEN env var, refresh if needed."""
    token_json = os.getenv("OUTLOOK_TOKEN")
    if not token_json:
        return None
    try:
        token_data = json.loads(token_json)
        # Try cached token first
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")

        # Use MSAL to refresh if needed
        app = get_ms_app()
        accounts = app.get_accounts()
        result = None
        if accounts:
            result = app.acquire_token_silent(MS_SCOPES, account=accounts[0])
        if not result and refresh_token:
            result = app.acquire_token_by_refresh_token(refresh_token, scopes=MS_SCOPES)
        if result and "access_token" in result:
            # Persist updated token
            token_data.update({
                "access_token":  result["access_token"],
                "refresh_token": result.get("refresh_token", refresh_token),
            })
            return result["access_token"]
        return access_token
    except Exception:
        return None


def build_ms_auth_url(redirect_uri: str) -> str:
    app = get_ms_app()
    return app.get_authorization_request_url(
        scopes=MS_SCOPES,
        redirect_uri=redirect_uri,
        state="midwife_outlook_auth",
    )


def exchange_ms_code(code: str, redirect_uri: str) -> dict:
    app = get_ms_app()
    result = app.acquire_token_by_authorization_code(
        code=code, scopes=MS_SCOPES, redirect_uri=redirect_uri
    )
    if "error" in result:
        raise RuntimeError(f"MS auth error: {result.get('error_description')}")
    return {
        "access_token":  result["access_token"],
        "refresh_token": result.get("refresh_token", ""),
        "id_token":      result.get("id_token", ""),
    }


def _graph_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _graph_get(token: str, path: str, params: dict = None) -> dict:
    r = requests.get(f"{GRAPH_BASE}/{path}", headers=_graph_headers(token), params=params)
    if not r.ok:
        raise RuntimeError(f"Graph API error {r.status_code}: {r.text}")
    return r.json()


def _graph_post(token: str, path: str, body: dict) -> dict:
    r = requests.post(f"{GRAPH_BASE}/{path}", headers=_graph_headers(token), json=body)
    if not r.ok:
        raise RuntimeError(f"Graph API error {r.status_code}: {r.text}")
    return r.json() if r.text else {}


def _graph_patch(token: str, path: str, body: dict) -> dict:
    r = requests.patch(f"{GRAPH_BASE}/{path}", headers=_graph_headers(token), json=body)
    if not r.ok:
        raise RuntimeError(f"Graph API error {r.status_code}: {r.text}")
    return r.json() if r.text else {}


def _graph_delete(token: str, path: str) -> None:
    r = requests.delete(f"{GRAPH_BASE}/{path}", headers=_graph_headers(token))
    if not r.ok:
        raise RuntimeError(f"Graph API error {r.status_code}: {r.text}")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fmt_email(msg: dict) -> dict:
    sender = msg.get("from", {}).get("emailAddress", {})
    return {
        "id":         msg.get("id"),
        "subject":    msg.get("subject", "(no subject)"),
        "from_name":  sender.get("name", ""),
        "from_email": sender.get("address", ""),
        "received":   msg.get("receivedDateTime", ""),
        "body":       msg.get("body", {}).get("content", ""),
        "body_type":  msg.get("body", {}).get("contentType", "text"),
        "is_read":    msg.get("isRead", False),
        "has_attachments": msg.get("hasAttachments", False),
        "conversation_id": msg.get("conversationId", ""),
        "web_link":   msg.get("webLink", ""),
    }


# ── Inbox operations ───────────────────────────────────────────────────────────

def list_inbox(token: str, top: int = 20, unread_only: bool = False) -> list[dict]:
    """Return recent inbox messages."""
    params = {
        "$top": top,
        "$orderby": "receivedDateTime desc",
        "$select": "id,subject,from,receivedDateTime,isRead,hasAttachments,conversationId,webLink,body",
        "$expand": "body($select=content,contentType)",
    }
    if unread_only:
        params["$filter"] = "isRead eq false"
    result = _graph_get(token, "me/mailFolders/inbox/messages", params)
    return [_fmt_email(m) for m in result.get("value", [])]


def get_email(token: str, message_id: str) -> dict:
    """Get a single email with full body."""
    result = _graph_get(token, f"me/messages/{message_id}")
    return _fmt_email(result)


def get_thread(token: str, conversation_id: str) -> list[dict]:
    """Get all messages in a conversation thread."""
    params = {
        "$filter": f"conversationId eq '{conversation_id}'",
        "$orderby": "receivedDateTime asc",
        "$select": "id,subject,from,receivedDateTime,isRead,body",
    }
    result = _graph_get(token, "me/messages", params)
    return [_fmt_email(m) for m in result.get("value", [])]


def mark_read(token: str, message_id: str) -> dict:
    return _graph_patch(token, f"me/messages/{message_id}", {"isRead": True})


def create_draft(
    token: str,
    to: list[str],
    subject: str,
    body_html: str,
    reply_to_id: Optional[str] = None,
    cc: Optional[list[str]] = None,
) -> dict:
    """
    Create a draft email for midwife review.
    If reply_to_id is given, creates a reply draft on that message.
    NEVER sends automatically — midwife always reviews first.
    """
    if reply_to_id:
        # Create a reply draft — preserves thread context
        body = {"comment": body_html}
        result = _graph_post(token, f"me/messages/{reply_to_id}/createReply", body)
        # Update the draft with our composed body
        update_body = {
            "body": {"contentType": "html", "content": body_html},
            "toRecipients": [{"emailAddress": {"address": addr}} for addr in to],
        }
        if cc:
            update_body["ccRecipients"] = [{"emailAddress": {"address": addr}} for addr in cc]
        result = _graph_patch(token, f"me/messages/{result['id']}", update_body)
    else:
        # New draft
        draft_body = {
            "subject": subject,
            "body": {"contentType": "html", "content": body_html},
            "toRecipients": [{"emailAddress": {"address": addr}} for addr in to],
            "isDraft": True,
        }
        if cc:
            draft_body["ccRecipients"] = [{"emailAddress": {"address": addr}} for addr in cc]
        result = _graph_post(token, "me/messages", draft_body)

    return {
        "draft_id": result.get("id"),
        "subject":  result.get("subject"),
        "web_link": result.get("webLink", ""),
        "status":   "draft_created",
        "note":     "Draft saved to Outlook. Open in Outlook to review and send.",
    }


def update_draft(token: str, draft_id: str, body_html: str) -> dict:
    """Update an existing draft body."""
    result = _graph_patch(token, f"me/messages/{draft_id}", {
        "body": {"contentType": "html", "content": body_html}
    })
    return {"draft_id": result.get("id"), "status": "draft_updated"}


def delete_draft(token: str, draft_id: str) -> dict:
    """Delete a draft."""
    _graph_delete(token, f"me/messages/{draft_id}")
    return {"deleted": True, "draft_id": draft_id}


def list_drafts(token: str) -> list[dict]:
    """List all drafts in the Drafts folder."""
    result = _graph_get(token, "me/mailFolders/drafts/messages", {
        "$top": 20,
        "$orderby": "lastModifiedDateTime desc",
        "$select": "id,subject,toRecipients,lastModifiedDateTime,webLink",
    })
    return [_fmt_email(m) for m in result.get("value", [])]


def search_emails(token: str, query: str, top: int = 10) -> list[dict]:
    """Search emails by keyword."""
    result = _graph_get(token, "me/messages", {
        "$search": f'"{query}"',
        "$top": top,
        "$select": "id,subject,from,receivedDateTime,body,webLink",
    })
    return [_fmt_email(m) for m in result.get("value", [])]
