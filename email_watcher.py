"""
Email Watcher — Midwife Agent
Runs as a background thread on Railway.
Polls Gmail for new unread emails every 2 minutes.
Drafts intelligent replies using Anthropic + knowledge base.
Flags uncertain replies with [REVIEW NEEDED].
GC Advisory — gcadvisory.co.nz
"""

import json
import logging
import os
import threading
import time
from datetime import datetime

import anthropic

logger = logging.getLogger("email_watcher")

# Track processed email IDs to avoid re-drafting
_processed_ids: set = set()
_watcher_running = False


# ── Draft generation ───────────────────────────────────────────────────────────

def generate_draft(
    email: dict,
    document_store: dict,
    search_fn,
) -> tuple[str, bool]:
    """
    Generate a draft reply for an email.
    Returns (draft_html, needs_review).
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None, True

    # Search knowledge base for relevant context
    query = f"{email.get('subject', '')} {email.get('body', '')[:500]}"
    chunks = search_fn(query, top_k=6)
    kb_context = ""
    if chunks:
        seen = list({c["doc_name"] for c in chunks})
        kb_context = (
            f"\n\nRELEVANT KNOWLEDGE BASE EXCERPTS (from: {', '.join(seen)}):\n"
            + "\n---\n".join(c["text"] for c in chunks)
        )

    system_prompt = (
        "You are an AI assistant for a Licensed Maternity Carer (LMC) midwife in Northland, New Zealand.\n\n"
        "Your job is to draft professional email replies on behalf of the midwife.\n\n"
        "RULES:\n"
        "1. Write in a warm, professional tone as if you ARE the midwife replying.\n"
        "2. Use the knowledge base context if relevant to the email.\n"
        "3. Keep replies concise and direct — no waffle.\n"
        "4. If you are NOT confident about any part of the reply, add [REVIEW NEEDED: <reason>] "
        "on a new line at the top of the draft.\n"
        "5. If the email is clearly spam, marketing, or automated — reply with just: SKIP\n"
        "6. Do NOT include a subject line — just the body.\n"
        "7. Sign off as: Kind regards,\n[Midwife's name]\nLMC Midwife\nNorthland, New Zealand\n\n"
        "8. Format as clean HTML for Gmail (use <p> tags, no complex styling).\n"
        f"{kb_context}"
    )

    user_prompt = (
        f"Email received from: {email.get('from_email', 'Unknown')}\n"
        f"Subject: {email.get('subject', '(no subject)')}\n"
        f"Date: {email.get('date', '')}\n\n"
        f"Email body:\n{email.get('body', '')[:2000]}\n\n"
        "Please draft a reply to this email."
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5"),
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        draft_text = response.content[0].text.strip()

        # Skip spam/automated emails
        if draft_text.upper().startswith("SKIP"):
            return None, False

        needs_review = "[REVIEW NEEDED" in draft_text

        # Wrap plain text in HTML if not already
        if not draft_text.startswith("<"):
            draft_html = draft_text.replace("\n", "<br>")
        else:
            draft_html = draft_text

        return draft_html, needs_review

    except Exception as e:
        logger.error(f"Draft generation error: {e}")
        return None, True


# ── Watcher loop ───────────────────────────────────────────────────────────────

def watch_inbox(get_creds_fn, document_store: dict, search_fn, poll_interval: int = 120):
    """
    Main watcher loop. Runs in a background thread.
    Polls Gmail every poll_interval seconds for new unread emails.
    """
    from gmail_integration import create_draft, get_email, list_inbox, mark_read

    global _processed_ids, _watcher_running
    _watcher_running = True
    logger.info("Email watcher started. Polling every %ds.", poll_interval)

    while _watcher_running:
        try:
            creds = get_creds_fn()
            if not creds:
                logger.warning("Google not connected — skipping poll.")
                time.sleep(poll_interval)
                continue

            # Fetch unread inbox emails
            emails = list_inbox(creds, max_results=10, unread_only=True)

            new_count = 0
            for email in emails:
                msg_id = email.get("id")
                if not msg_id or msg_id in _processed_ids:
                    continue

                _processed_ids.add(msg_id)
                new_count += 1

                subject = email.get("subject", "(no subject)")
                sender  = email.get("from_email", "unknown")
                logger.info("Processing email: '%s' from %s", subject, sender)

                # Generate draft reply
                draft_html, needs_review = generate_draft(email, document_store, search_fn)

                if draft_html is None:
                    logger.info("Skipping email (spam/automated or generation failed): %s", subject)
                    continue

                # Create Gmail draft as reply in same thread
                thread_id = email.get("thread_id")
                reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"

                result = create_draft(
                    creds=creds,
                    to=[sender],
                    subject=reply_subject,
                    body_html=draft_html,
                    reply_to_id=msg_id,
                )

                status = "[REVIEW NEEDED]" if needs_review else "auto-drafted"
                logger.info(
                    "Draft created (%s) for '%s' — draft_id: %s",
                    status, subject, result.get("draft_id")
                )

                # Mark original as read so it doesn't get reprocessed
                try:
                    mark_read(creds, msg_id)
                except Exception:
                    pass

            if new_count == 0:
                logger.debug("No new emails.")

        except Exception as e:
            logger.error("Watcher error: %s", e)

        time.sleep(poll_interval)

    logger.info("Email watcher stopped.")


def start_watcher(get_creds_fn, document_store: dict, search_fn, poll_interval: int = 120):
    """Start the email watcher in a background daemon thread."""
    thread = threading.Thread(
        target=watch_inbox,
        args=(get_creds_fn, document_store, search_fn, poll_interval),
        daemon=True,
        name="email-watcher",
    )
    thread.start()
    logger.info("Email watcher thread started.")
    return thread


def stop_watcher():
    global _watcher_running
    _watcher_running = False
    logger.info("Email watcher stop requested.")


def watcher_status() -> dict:
    return {
        "running": _watcher_running,
        "processed_count": len(_processed_ids),
    }
