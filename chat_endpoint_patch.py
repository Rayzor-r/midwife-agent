# ─────────────────────────────────────────────────────────────────────────────
# Replacement for the /api/chat endpoint in main.py
#
# The current endpoint describes the calendar/email endpoints in the system
# prompt but does NOT pass Anthropic tools. Claude therefore cannot actually
# call anything — it just generates text and hallucinates confirmations.
#
# This version defines real tools and runs a tool-use loop so Claude actually
# hits the FastAPI functions. Streaming is preserved to the UI; tool calls
# run in between stream segments.
# ─────────────────────────────────────────────────────────────────────────────

from datetime import datetime
import json
import os

import anthropic
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

# Import the existing Python functions directly — no HTTP roundtrip needed.
from calendar_integration import (
    list_events, create_event, update_event, cancel_event, get_availability,
    get_google_credentials,
)
from gmail_integration import (
    list_inbox, get_message, create_draft, search_messages, list_drafts,
)

# ─── Tool definitions ────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "list_calendar_events",
        "description": "List upcoming appointments from Google Calendar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "default": 14},
            },
        },
    },
    {
        "name": "check_availability",
        "description": "Return free slots on a given date between 8am and 5pm NZ time.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "duration_minutes": {"type": "integer", "default": 45},
            },
            "required": ["date"],
        },
    },
    {
        "name": "book_appointment",
        "description": "Create a new appointment in Google Calendar. Always confirm the slot is free first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start_datetime": {"type": "string", "description": "ISO 8601, NZ time"},
                "duration_minutes": {"type": "integer"},
                "description": {"type": "string"},
                "location": {"type": "string"},
            },
            "required": ["title", "start_datetime"],
        },
    },
    {
        "name": "reschedule_appointment",
        "description": "Update an existing appointment by event_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
                "title": {"type": "string"},
                "start_datetime": {"type": "string"},
                "duration_minutes": {"type": "integer"},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "cancel_appointment",
        "description": "Delete an appointment by event_id.",
        "input_schema": {
            "type": "object",
            "properties": {"event_id": {"type": "string"}},
            "required": ["event_id"],
        },
    },
    {
        "name": "list_inbox",
        "description": "List recent emails from Gmail.",
        "input_schema": {
            "type": "object",
            "properties": {
                "top": {"type": "integer", "default": 20},
                "unread_only": {"type": "boolean", "default": False},
            },
        },
    },
    {
        "name": "search_emails",
        "description": "Search Gmail.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_email",
        "description": "Fetch a single email by id.",
        "input_schema": {
            "type": "object",
            "properties": {"message_id": {"type": "string"}},
            "required": ["message_id"],
        },
    },
    {
        "name": "draft_email",
        "description": "Save an email as a draft in Gmail. Never sends.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "array", "items": {"type": "string"}},
                "subject": {"type": "string"},
                "body_html": {"type": "string"},
                "reply_to_id": {"type": "string"},
                "cc": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["to", "subject", "body_html"],
        },
    },
]


# ─── Tool dispatcher ─────────────────────────────────────────────────────────

def _run_tool(name: str, args: dict) -> dict:
    """Execute a tool. Always returns a JSON-serialisable dict."""
    creds = get_google_credentials()
    if not creds:
        return {"error": "Google not connected. Visit /auth/google."}

    try:
        if name == "list_calendar_events":
            return {"events": list_events(creds, args.get("days_ahead", 14))}

        if name == "check_availability":
            d = datetime.fromisoformat(args["date"])
            return {"slots": get_availability(creds, d, args.get("duration_minutes", 45))}

        if name == "book_appointment":
            start = datetime.fromisoformat(args["start_datetime"])
            return create_event(
                creds,
                title=args["title"],
                start_dt=start,
                duration_minutes=args.get("duration_minutes"),
                description=args.get("description", ""),
                location=args.get("location", ""),
            )

        if name == "reschedule_appointment":
            start = (datetime.fromisoformat(args["start_datetime"])
                     if args.get("start_datetime") else None)
            return update_event(
                creds,
                event_id=args["event_id"],
                title=args.get("title"),
                start_dt=start,
                duration_minutes=args.get("duration_minutes"),
            )

        if name == "cancel_appointment":
            return cancel_event(creds, args["event_id"])

        if name == "list_inbox":
            return {"messages": list_inbox(creds, args.get("top", 20),
                                            args.get("unread_only", False))}

        if name == "search_emails":
            return {"messages": search_messages(creds, args["query"])}

        if name == "get_email":
            return get_message(creds, args["message_id"])

        if name == "draft_email":
            return create_draft(
                creds,
                to=args["to"],
                subject=args["subject"],
                body_html=args["body_html"],
                reply_to_id=args.get("reply_to_id"),
                cc=args.get("cc"),
            )

        return {"error": f"Unknown tool: {name}"}

    except Exception as e:
        return {"error": str(e)}


# ─── Patched chat endpoint ───────────────────────────────────────────────────

# NOTE: The system prompt should be rewritten. Remove the "Use ONLY these exact
# endpoints: GET /api/calendar/events..." block — that was instructing Claude
# to speak HTTP, which it cannot do. Keep the role, tone, and "never say you
# lack access" rules. Add: "Use the provided tools to check availability,
# book, reschedule, cancel appointments, and read/draft emails."

@app.post("/api/chat")
async def chat(request: ChatRequest):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(500, "ANTHROPIC_API_KEY not configured")

    user_messages = [m for m in request.messages if m.role == "user"]
    latest_query  = user_messages[-1].content if user_messages else ""
    chunks        = search_documents(latest_query) if document_store else []
    system        = build_system_prompt(chunks)
    messages      = [{"role": m.role, "content": m.content} for m in request.messages]

    async def generate():
        try:
            client = anthropic.AsyncAnthropic(api_key=api_key)

            # Tool-use loop. Max 6 iterations to avoid runaway.
            for _ in range(6):
                resp = await client.messages.create(
                    model="claude-sonnet-4-5",  # confirm exact model string on your end
                    max_tokens=2048,
                    system=system,
                    tools=TOOLS,
                    messages=messages,
                )

                # Stream out any text blocks Claude produced.
                for block in resp.content:
                    if block.type == "text" and block.text:
                        yield f"data: {json.dumps({'text': block.text})}\n\n"

                if resp.stop_reason != "tool_use":
                    break  # Claude is done.

                # Run every tool_use block, append results, loop.
                tool_results = []
                for block in resp.content:
                    if block.type == "tool_use":
                        result = _run_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        })
                        # Surface tool activity to the UI for transparency.
                        yield f"data: {json.dumps({'tool': block.name, 'result': result})}\n\n"

                messages.append({"role": "assistant", "content": [b.model_dump() for b in resp.content]})
                messages.append({"role": "user", "content": tool_results})

            if chunks:
                sources = list({c["doc_name"] for c in chunks})
                yield f"data: {json.dumps({'sources': sources})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})
