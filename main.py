"""
Midwife AI Agent — Backend
FastAPI · Anthropic tool use · Google Drive RAG · Google Calendar · Gmail · Note tidy
GC Advisory — gcadvisory.co.nz

v2.1 — Tool use loop added so Claude actually calls the integrations instead
       of hallucinating confirmations. Note tidy feature added.
"""

import io
import json
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from calendar_integration import (
    build_google_flow, cancel_event, create_event, credentials_to_dict,
    get_availability, get_google_credentials, list_events, update_event,
)
from drive_integration import sync_drive_to_knowledge_base
from gmail_integration import (
    create_draft, delete_draft, get_email, get_thread,
    list_drafts, list_inbox, mark_read, search_emails, update_draft,
)
from email_watcher import start_watcher, stop_watcher, watcher_status
from note_tidy import list_note_files, tidy_note_file, tidy_note_text

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(title="Midwife AI Agent", version="2.1.0")
app.add_middleware(CORSMiddleware, allow_origins=[os.getenv("ALLOWED_ORIGIN", "http://localhost:8000")], allow_methods=["*"], allow_headers=["*"])

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

BASE_URL = os.getenv("RAILWAY_PUBLIC_DOMAIN", "http://localhost:8000")
if not BASE_URL.startswith("http"):
    BASE_URL = f"https://{BASE_URL}"

# Anthropic model. Confirm this matches your account's available models.
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")
API_KEY = os.getenv("API_KEY", "")

# ── API key auth middleware ─────────────────────────────────────────────────────

EXEMPT_PATHS = {"/api/health"}

@app.middleware("http")
async def require_api_key(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and path not in EXEMPT_PATHS:
        auth = request.headers.get("Authorization", "")
        if not API_KEY or not auth.startswith("Bearer ") or auth[len("Bearer "):] != API_KEY:
            return Response(
                content='{"detail":"Unauthorized"}',
                status_code=401,
                media_type="application/json",
                headers={"WWW-Authenticate": "Bearer"},
            )
    return await call_next(request)

# ── Document store ─────────────────────────────────────────────────────────────
document_store: dict = {}
CHUNK_SIZE    = 650
CHUNK_OVERLAP = 120


def chunk_text(text: str, doc_id: str, doc_name: str) -> list[dict]:
    text = re.sub(r"\s+", " ", text).strip()
    chunks, start, idx = [], 0, 0
    while start < len(text):
        end = start + CHUNK_SIZE
        if end < len(text):
            boundary = text.rfind(".", start, end)
            if boundary > start + CHUNK_SIZE // 2:
                end = boundary + 1
        snippet = text[start:end].strip()
        if snippet:
            chunks.append({"id": f"{doc_id}_{idx}", "doc_id": doc_id,
                           "doc_name": doc_name, "text": snippet, "chunk_idx": idx})
            idx += 1
        start = end - CHUNK_OVERLAP
    return chunks


def extract_text(file_bytes: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        import pdfplumber
        parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t: parts.append(t)
        return "\n\n".join(parts)
    if ext == ".docx":
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if ext in (".txt", ".md"):
        return file_bytes.decode("utf-8", errors="replace")
    raise ValueError(f"Unsupported file type: {ext}")


def search_documents(query: str, top_k: int = 10) -> list[dict]:
    clean   = lambda s: re.sub(r"[^\w\s]", "", s.lower())
    q_words = set(clean(query).split())
    if not q_words:
        return []
    scored = []
    for doc in document_store.values():
        for chunk in doc["chunks"]:
            c_words = set(clean(chunk["text"]).split())
            score   = len(q_words & c_words)
            if clean(query) in clean(chunk["text"]):
                score += 3
            if score > 0:
                scored.append((score, chunk))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]


# ── System prompt ──────────────────────────────────────────────────────────────

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


# ── Tool definitions ───────────────────────────────────────────────────────────

TOOLS = [
    # Calendar
    {
        "name": "list_calendar_events",
        "description": (
            "List upcoming appointments from Google Calendar. "
            "Use when the midwife asks what's on her schedule."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "description": "Defaults to 14"},
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
            "Create an appointment in Google Calendar. "
            "Only call after the midwife has confirmed the details."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
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
    # Gmail
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
        "description": "Fetch one email by id to read its full content.",
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
            "NEVER sends. Always save as draft."
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
    # Note tidy
    {
        "name": "list_note_files",
        "description": (
            "List de-identified shorthand notes in the dedicated notes folder "
            "on Google Drive."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "tidy_note_from_drive",
        "description": (
            "Download one note from the Drive notes folder and return a tidied "
            "version in a standard antenatal / labour / postnatal structure. "
            "Never changes wording, never adds information, flags ambiguities. "
            "Nothing is saved back."
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
            "Tidy a note the midwife has pasted directly into the chat."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"note_text": {"type": "string"}},
            "required": ["note_text"],
        },
    },
]


def _run_tool(name: str, args: dict) -> dict:
    """Execute a tool. Errors returned as {'error': ...}, not raised."""
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
                creds, title=args["title"], start_dt=start,
                duration_minutes=args.get("duration_minutes"),
                description=args.get("description", ""),
                location=args.get("location", ""),
            )
        if name == "reschedule_appointment":
            start = (datetime.fromisoformat(args["start_datetime"])
                     if args.get("start_datetime") else None)
            return update_event(
                creds, event_id=args["event_id"], title=args.get("title"),
                start_dt=start, duration_minutes=args.get("duration_minutes"),
            )
        if name == "cancel_appointment":
            return cancel_event(creds, args["event_id"])

        # Gmail
        if name == "list_inbox":
            return {"messages": list_inbox(
                creds, max_results=args.get("max_results", 20),
                unread_only=args.get("unread_only", False),
            )}
        if name == "search_emails":
            return {"messages": search_emails(creds, args["query"])}
        if name == "get_email":
            return get_email(creds, args["message_id"])
        if name == "draft_email":
            return create_draft(
                creds, to=args["to"], subject=args["subject"],
                body_html=args["body_html"],
                reply_to_id=args.get("reply_to_id"),
                cc=args.get("cc"),
            )

        # Note tidy
        if name == "list_note_files":
            return {"files": list_note_files(creds)}
        if name == "tidy_note_from_drive":
            return tidy_note_file(
                creds, file_id=args["file_id"],
                filename=args["filename"], mime_type=args["mime_type"],
            )
        if name == "tidy_pasted_note":
            return tidy_note_text(args["note_text"])

        return {"error": f"Unknown tool: {name}"}

    except Exception as e:
        return {"error": str(e)}


# ── Models ─────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]

class CreateEventRequest(BaseModel):
    title: str
    start_datetime: str
    duration_minutes: Optional[int] = None
    description: Optional[str] = ""
    location: Optional[str] = ""

class UpdateEventRequest(BaseModel):
    event_id: str
    title: Optional[str] = None
    start_datetime: Optional[str] = None
    duration_minutes: Optional[int] = None
    description: Optional[str] = None
    location: Optional[str] = None

class DraftEmailRequest(BaseModel):
    to: list[str]
    subject: str
    body_html: str
    reply_to_id: Optional[str] = None
    cc: Optional[list[str]] = None

class UpdateDraftRequest(BaseModel):
    draft_id: str
    to: list[str]
    subject: str
    body_html: str


# ── Frontend ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    html = static_dir / "index.html"
    if html.exists():
        return HTMLResponse(html.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>index.html not found in static/</h1>", status_code=404)


# ── Chat (with tool-use loop) ──────────────────────────────────────────────────

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
            for _ in range(8):  # cap tool-use iterations
                resp = await client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=2048,
                    system=system,
                    tools=TOOLS,
                    messages=messages,
                )

                # Stream any text blocks.
                for block in resp.content:
                    if block.type == "text" and block.text:
                        yield f"data: {json.dumps({'text': block.text})}\n\n"

                if resp.stop_reason != "tool_use":
                    break

                tool_results = []
                for block in resp.content:
                    if block.type == "tool_use":
                        result = _run_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, default=str),
                        })
                        yield (
                            f"data: {json.dumps({'tool': block.name, 'result': result}, default=str)}\n\n"
                        )

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
        generate(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Manual document upload ─────────────────────────────────────────────────────

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    allowed = {".pdf", ".docx", ".txt", ".md"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(400, f"'{ext}' not supported.")
    data = await file.read()
    try:
        text = extract_text(data, file.filename)
    except Exception as e:
        raise HTTPException(422, f"Extraction failed: {e}")
    if not text.strip():
        raise HTTPException(422, "No text extracted.")
    doc_id = str(uuid.uuid4())[:8]
    chunks = chunk_text(text, doc_id, file.filename)
    document_store[doc_id] = {
        "id": doc_id, "name": file.filename, "chunks": chunks,
        "chunk_count": len(chunks), "char_count": len(text),
        "uploaded_at": datetime.now().isoformat(), "source": "manual",
    }
    return {"doc_id": doc_id, "name": file.filename, "chunks": len(chunks),
            "message": f"Indexed {len(chunks)} sections from '{file.filename}'"}


@app.get("/api/documents")
async def list_documents():
    return [{"id": d["id"], "name": d["name"], "chunks": d["chunk_count"],
             "uploaded_at": d["uploaded_at"], "source": d.get("source", "manual")}
            for d in document_store.values()]


@app.delete("/api/documents/{doc_id}")
async def delete_document(doc_id: str):
    if doc_id not in document_store:
        raise HTTPException(404, "Document not found")
    name = document_store.pop(doc_id)["name"]
    return {"message": f"Removed '{name}'"}


# ── Google OAuth ───────────────────────────────────────────────────────────────

@app.get("/auth/google")
async def google_auth_start():
    flow = build_google_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline", include_granted_scopes="true",
        prompt="consent", state="gcadvisory"
    )
    return RedirectResponse(auth_url)


@app.get("/auth/google/callback")
async def google_auth_callback(code: str = Query(...), state: str = Query(default="")):
    flow = build_google_flow()
    flow.fetch_token(code=code)
    creds    = flow.credentials
    tok_dict = credentials_to_dict(creds)
    logger.info("GOOGLE_TOKEN: %s", json.dumps(tok_dict))
    return HTMLResponse("""
    <html><body style="font-family:sans-serif;padding:40px;max-width:700px;background:#07090f;color:#ebf1ff">
    <h2>Google connected &#10003;</h2>
    <p>Token has been written to server logs.</p>
    <p>Copy it from your Railway dashboard under <strong>Deployments &rarr; Logs</strong>
       (search for <code>GOOGLE_TOKEN</code>), then paste it into the
       <strong>GOOGLE_TOKEN</strong> Railway environment variable and redeploy.</p>
    <p style="margin-top:24px;color:rgba(235,241,255,0.6)">You may close this tab.</p>
    </body></html>
    """)


@app.get("/api/google/status")
async def google_status():
    creds = get_google_credentials()
    return {
        "connected": creds is not None and creds.valid,
        "scopes": list(creds.scopes) if creds else [],
    }


# ── Google Drive sync ──────────────────────────────────────────────────────────

@app.post("/api/drive/sync")
async def drive_sync(force: bool = False):
    creds = get_google_credentials()
    if not creds:
        raise HTTPException(401, "Google not connected. Visit /auth/google first.")
    try:
        return sync_drive_to_knowledge_base(creds, document_store, chunk_text, force_full=force)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/drive/status")
async def drive_status():
    creds     = get_google_credentials()
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
    return {"connected": creds is not None, "folder_id": folder_id, "docs_loaded": len(document_store)}


# ── Calendar ───────────────────────────────────────────────────────────────────

def _require_google():
    creds = get_google_credentials()
    if not creds:
        raise HTTPException(401, "Google not connected. Visit /auth/google first.")
    return creds


@app.get("/api/calendar/events")
async def calendar_list(days: int = 14):
    creds = _require_google()
    try:
        return list_events(creds, days_ahead=days)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/calendar/events")
async def calendar_create(req: CreateEventRequest):
    creds = _require_google()
    try:
        start = datetime.fromisoformat(req.start_datetime)
        return create_event(creds, req.title, start, req.duration_minutes,
                            req.description or "", req.location or "")
    except Exception as e:
        raise HTTPException(500, str(e))


@app.patch("/api/calendar/events")
async def calendar_update(req: UpdateEventRequest):
    creds = _require_google()
    try:
        start = datetime.fromisoformat(req.start_datetime) if req.start_datetime else None
        return update_event(creds, req.event_id, req.title, start,
                            req.duration_minutes, req.description, req.location)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.delete("/api/calendar/events/{event_id}")
async def calendar_cancel(event_id: str):
    creds = _require_google()
    try:
        return cancel_event(creds, event_id)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/calendar/availability")
async def calendar_availability(date: str, duration: int = 45):
    creds = _require_google()
    try:
        d = datetime.fromisoformat(date)
        return get_availability(creds, d, duration)
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Gmail ──────────────────────────────────────────────────────────────────────

@app.get("/api/email/inbox")
async def email_inbox(top: int = 20, unread_only: bool = False):
    creds = _require_google()
    try:
        return list_inbox(creds, max_results=top, unread_only=unread_only)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/email/message/{message_id}")
async def email_get(message_id: str):
    creds = _require_google()
    try:
        return get_email(creds, message_id)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/email/thread/{thread_id}")
async def email_thread(thread_id: str):
    creds = _require_google()
    try:
        return get_thread(creds, thread_id)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/email/draft")
async def email_create_draft(req: DraftEmailRequest):
    creds = _require_google()
    try:
        return create_draft(creds, req.to, req.subject, req.body_html,
                            req.reply_to_id, req.cc)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.patch("/api/email/draft")
async def email_update_draft(req: UpdateDraftRequest):
    creds = _require_google()
    try:
        return update_draft(creds, req.draft_id, req.to, req.subject, req.body_html)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.delete("/api/email/draft/{draft_id}")
async def email_delete_draft(draft_id: str):
    creds = _require_google()
    try:
        return delete_draft(creds, draft_id)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/email/drafts")
async def email_list_drafts():
    creds = _require_google()
    try:
        return list_drafts(creds)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/email/search")
async def email_search(q: str, top: int = 10):
    creds = _require_google()
    try:
        return search_emails(creds, q, top)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/email/read/{message_id}")
async def email_mark_read(message_id: str):
    creds = _require_google()
    try:
        return mark_read(creds, message_id)
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Notes (status endpoint for diagnostics) ────────────────────────────────────

@app.get("/api/notes/list")
async def notes_list():
    """Lightweight check that the notes folder is wired up. The actual
    tidying is done via the chat agent's tools, not via a direct UI call."""
    creds = _require_google()
    try:
        files = list_note_files(creds)
        return {"count": len(files), "files": files}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    creds = get_google_credentials()
    return {
        "status":           "ok",
        "version":          "2.1.0",
        "documents":        len(document_store),
        "total_chunks":     sum(d["chunk_count"] for d in document_store.values()),
        "google_connected": creds is not None,
        "model":            CLAUDE_MODEL,
        "notes_folder_set": bool(os.getenv("GOOGLE_DRIVE_NOTES_FOLDER_ID")),
    }


# ── Email watcher ──────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    if not API_KEY:
        logger.warning(
            "API_KEY env var is not set — all /api/* requests will return 401. "
            "Set API_KEY in Railway Variables before deploying."
        )
    start_watcher(
        get_creds_fn=get_google_credentials,
        document_store=document_store,
        search_fn=search_documents,
        poll_interval=120,
    )


@app.get("/api/watcher/status")
async def get_watcher_status():
    return watcher_status()


@app.post("/api/watcher/stop")
async def stop_watcher_endpoint():
    stop_watcher()
    return {"message": "Watcher stop requested."}


# ── Entry ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
