"""
═══════════════════════════════════════════════════════════════════════════════
CONSOLIDATED PATCH — Midwife Agent
───────────────────────────────────────────────────────────────────────────────
Fixes:
  1. /api/chat never passed tools to Claude. The agent hallucinated
     confirmations because it could only generate text, not call endpoints.
     This patch adds a real tool-use loop so calendar and email actions
     actually execute.

  2. Adds a new capability: tidying de-identified shorthand notes from a
     dedicated Drive folder. Uses the same chat, no new UI.

Deploy steps:
  1. Add a new file:  note_tidy.py   (provided separately, unchanged from
                                      earlier — only the endpoints file is
                                      superseded by this consolidated patch)
  2. Replace the /api/chat function in main.py with the version below.
  3. Replace the build_system_prompt function in main.py with the version
     below.
  4. Add the imports listed at the top of this file to main.py.
  5. In Railway, add env var:
        GOOGLE_DRIVE_NOTES_FOLDER_ID = <drive folder id for notes>
     This MUST be a different folder from GOOGLE_DRIVE_FOLDER_ID.
  6. Confirm ANTHROPIC_API_KEY is set and the model string below is valid
     for your account.

GC Advisory — gcadvisory.co.nz
═══════════════════════════════════════════════════════════════════════════════
"""

# ─────────────────────────────────────────────────────────────────────────────
# 1. ADD THESE IMPORTS near the top of main.py, with the other integration
#    imports (around line 26–35):
# ─────────────────────────────────────────────────────────────────────────────

from note_tidy import (
    list_note_files,
    tidy_note_file,
    tidy_note_text,
)

# Also ensure these are already imported from gmail_integration (they are,
# in the current main.py):
#   create_draft, get_email, list_drafts, list_inbox, search_emails


# ─────────────────────────────────────────────────────────────────────────────
# 2. TOOL DEFINITIONS — paste as a module-level constant, after the Pydantic
#    models block (roughly line 210) and before the frontend route.
# ─────────────────────────────────────────────────────────────────────────────

CLAUDE_MODEL = "claude-sonnet-4-5"   # confirm the exact model string on your
                                     # Anthropic account and update if needed

TOOLS = [
    # ── Calendar ──────────────────────────────────────────────────────────
    {
        "name": "list_calendar_events",
        "description": (
            "List upcoming appointments from Google Calendar. "
            "Use when the midwife asks what's on her schedule, what's coming up, "
            "or whether a time is already booked."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {
                    "type": "integer",
                    "description": "How many days ahead to look, defaults to 14",
                },
            },
        },
    },
    {
        "name": "check_availability",
        "description": (
            "Return free slots between 8am and 5pm NZ time on a given date. "
            "Call this BEFORE booking to confirm a slot is free."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "duration_minutes": {"type": "integer", "description": "Default 45"},
            },
            "required": ["date"],
        },
    },
    {
        "name": "book_appointment",
        "description": (
            "Create a new appointment in Google Calendar. "
            "Only call after the midwife has confirmed the details."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "e.g. '36 week check'"},
                "start_datetime": {
                    "type": "string",
                    "description": "ISO 8601 in NZ time, e.g. 2026-05-14T14:00:00",
                },
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

    # ── Gmail ─────────────────────────────────────────────────────────────
    {
        "name": "list_inbox",
        "description": "List recent emails from Gmail.",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "description": "Default 20"},
                "unread_only": {"type": "boolean"},
            },
        },
    },
    {
        "name": "search_emails",
        "description": "Search Gmail, e.g. 'from:teams referral', 'subject:GBS'.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_email",
        "description": "Fetch a single email by id to read its full content.",
        "input_schema": {
            "type": "object",
            "properties": {"message_id": {"type": "string"}},
            "required": ["message_id"],
        },
    },
    {
        "name": "draft_email",
        "description": (
            "Save an email as a draft in Gmail for the midwife to review. "
            "NEVER sends. Always save as draft, never send automatically."
        ),
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

    # ── Note tidy ─────────────────────────────────────────────────────────
    {
        "name": "list_note_files",
        "description": (
            "List de-identified shorthand notes in the dedicated notes folder "
            "on Google Drive. Use when the midwife asks what notes are pending "
            "or wants to see what's in the folder."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "tidy_note_from_drive",
        "description": (
            "Download one note from the Drive notes folder and return a tidied "
            "version in a standard antenatal / labour / postnatal structure. "
            "Never changes wording, never adds information, flags ambiguities. "
            "Nothing is saved back — the midwife reviews the result and copies "
            "it into her clinical record system herself."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_id":   {"type": "string"},
                "filename":  {"type": "string"},
                "mime_type": {"type": "string"},
            },
            "required": ["file_id", "filename", "mime_type"],
        },
    },
    {
        "name": "tidy_pasted_note",
        "description": (
            "Tidy a note the midwife has pasted directly into the chat. "
            "Same rules as tidy_note_from_drive: no wording changes, no "
            "additions, flag ambiguities. Use when the midwife includes a "
            "note in her message rather than referring to a Drive file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"note_text": {"type": "string"}},
            "required": ["note_text"],
        },
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# 3. TOOL DISPATCHER — paste as a module-level function, below the TOOLS list.
# ─────────────────────────────────────────────────────────────────────────────

def _run_tool(name: str, args: dict) -> dict:
    """
    Execute a tool call. Always returns a JSON-serialisable dict.
    Errors are returned as {'error': ...} rather than raised, so the tool-use
    loop can surface them to Claude, who can then explain to the midwife.
    """
    creds = get_google_credentials()
    if not creds:
        return {"error": "Google is not connected. Visit /auth/google."}

    try:
        # Calendar
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

        # Gmail
        if name == "list_inbox":
            return {"messages": list_inbox(
                creds,
                max_results=args.get("max_results", 20),
                unread_only=args.get("unread_only", False),
            )}

        if name == "search_emails":
            return {"messages": search_emails(creds, args["query"])}

        if name == "get_email":
            return get_email(creds, args["message_id"])

        if name == "draft_email":
            return create_draft(
                creds,
                to=args["to"],
                subject=args["subject"],
                body_html=args["body_html"],
                reply_to_id=args.get("reply_to_id"),
                cc=args.get("cc"),
            )

        # Note tidy
        if name == "list_note_files":
            return {"files": list_note_files(creds)}

        if name == "tidy_note_from_drive":
            return tidy_note_file(
                creds,
                file_id=args["file_id"],
                filename=args["filename"],
                mime_type=args["mime_type"],
            )

        if name == "tidy_pasted_note":
            return tidy_note_text(args["note_text"])

        return {"error": f"Unknown tool: {name}"}

    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# 4. REPLACE build_system_prompt with this version.
#    The key change: remove the "GET /api/calendar/events..." HTTP endpoint
#    listing (which Claude could never call) and replace with clear guidance
#    on the tools it actually has.
# ─────────────────────────────────────────────────────────────────────────────

def build_system_prompt(chunks: list[dict]) -> str:
    base = (
        "You are a clinical support assistant for a Licensed Maternity Carer "
        "(LMC) midwifery practice in Northland, New Zealand.\n\n"

        "You have LIVE tools for:\n"
        "  • Google Calendar — check availability, book, reschedule, cancel\n"
        "  • Gmail — read inbox, search, draft emails (drafts only, never sent)\n"
        "  • Note tidy — reformat de-identified shorthand notes into a standard "
        "structure, for notes in the dedicated Drive folder OR pasted directly\n\n"

        "HOW TO USE THE TOOLS:\n"
        "1. If the midwife asks about her schedule, bookings, or availability, "
        "call the calendar tools. Do not ask her to repeat details you can see "
        "by calling list_calendar_events.\n"
        "2. For any booking, call check_availability first, confirm the slot "
        "with her in plain English, then call book_appointment.\n"
        "3. For emails, always save as a draft for her review. Never claim "
        "something was sent.\n"
        "4. For note tidying, use tidy_note_from_drive when she refers to a "
        "file in the notes folder, and tidy_pasted_note when she includes the "
        "note text in her message. Return the tidied output clearly, and "
        "always surface any flags the tool reports.\n\n"

        "ABSOLUTE RULES:\n"
        "• Never say you lack access to the calendar, email, or Drive. "
        "The tools are live.\n"
        "• Never fabricate a confirmation. Only confirm an action after the "
        "matching tool call has returned a successful result.\n"
        "• Never process identifiable client information (names, NHI numbers, "
        "addresses, DOBs). If the midwife includes identifiable detail, ask "
        "her to re-send with identifiers removed.\n"
        "• You are NOT a clinical decision tool. If asked for clinical "
        "advice, state this briefly and point to the loaded guidelines.\n"
        "• You operate under the NZ Privacy Act 2020 and Health Information "
        "Privacy Code 2020.\n\n"

        "RESPONSE STYLE:\n"
        "• Concise and direct. No filler, no marketing tone.\n"
        "• Plain professional language a midwife can use straight away.\n"
        "• Cite the source document when drawing from loaded guidelines.\n"
        "• If information isn't in the loaded documents or tool results, "
        "say so rather than guess.\n"
        "• Flag urgent or transfer-level clinical situations at the top.\n"
        "• For calendar: confirm bookings with date, time and duration, "
        "using the data returned by the tool.\n"
        "• For tidied notes: show the tidied output, then any flags the "
        "tool returned, then a one-line reminder that she should review "
        "before copying into her clinical record.\n\n"

        "TONE: Warm, precise, collegial. Like a well-informed colleague "
        "speaking clearly under time pressure."
    )

    if chunks:
        seen_docs     = list({c["doc_name"] for c in chunks})
        context_block = "\n\n---\n\n".join(
            f"[From: {c['doc_name']}]\n{c['text']}" for c in chunks
        )
        base += (
            "\n\n── LOADED DOCUMENT EXCERPTS ──────────────────────────────\n"
            f"Sources: {', '.join(seen_docs)}\n\n{context_block}\n\n"
            "── END OF DOCUMENT CONTEXT ───────────────────────────────────\n"
            "Use the excerpts above to ground clinical answers. "
            "Always cite which document you draw from."
        )
    else:
        base += (
            "\n\nNote: No policy documents are currently loaded. If the midwife "
            "asks a policy question, tell her to trigger a Drive sync or upload "
            "documents."
        )
    return base


# ─────────────────────────────────────────────────────────────────────────────
# 5. REPLACE the /api/chat endpoint with this version.
#    This is the core fix. The previous version had no tools, so Claude
#    could only produce text and was hallucinating confirmations.
# ─────────────────────────────────────────────────────────────────────────────

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
        client = anthropic.AsyncAnthropic(api_key=api_key)

        try:
            # Tool-use loop. Hard cap at 8 iterations to prevent runaway.
            for _ in range(8):
                resp = await client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=2048,
                    system=system,
                    tools=TOOLS,
                    messages=messages,
                )

                # Stream any text blocks Claude produced this turn.
                for block in resp.content:
                    if block.type == "text" and block.text:
                        yield f"data: {json.dumps({'text': block.text})}\n\n"

                if resp.stop_reason != "tool_use":
                    break  # Claude is done.

                # Run every tool_use block and feed results back.
                tool_results = []
                for block in resp.content:
                    if block.type == "tool_use":
                        result = _run_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, default=str),
                        })
                        # Surface tool activity to the UI for transparency.
                        yield (
                            f"data: {json.dumps({'tool': block.name, 'result': result}, default=str)}\n\n"
                        )

                # Append the assistant turn and the tool results to messages,
                # then loop so Claude can respond to the tool output.
                messages.append({
                    "role": "assistant",
                    "content": [b.model_dump() for b in resp.content],
                })
                messages.append({"role": "user", "content": tool_results})

            if chunks:
                sources = list({c["doc_name"] for c in chunks})
                yield f"data: {json.dumps({'sources': sources})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
