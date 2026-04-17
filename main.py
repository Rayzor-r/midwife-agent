"""
Midwife AI Agent — Backend
FastAPI · Anthropic streaming · Google Drive RAG · Google Calendar · Outlook Email
GC Advisory — gcadvisory.co.nz
"""

import io
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

from calendar_integration import (
    build_google_flow, cancel_event, create_event, credentials_to_dict,
    get_availability, get_google_credentials, list_events, update_event,
)
from drive_integration import sync_drive_to_knowledge_base
from outlook_integration import (
    build_ms_auth_url, create_draft, delete_draft, exchange_ms_code,
    get_email, get_ms_token, get_thread, list_drafts, list_inbox,
    mark_read, search_emails, update_draft,
)

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(title="Midwife AI Agent", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

BASE_URL = os.getenv("RAILWAY_PUBLIC_DOMAIN", "http://localhost:8000")
if not BASE_URL.startswith("http"):
    BASE_URL = f"https://{BASE_URL}"

# ── Document store (in-memory RAG) ─────────────────────────────────────────────
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
    clean  = lambda s: re.sub(r"[^\w\s]", "", s.lower())
    q_words = set(clean(query).split())
    if not q_words:
        return []
    scored = []
    for doc in document_store.values():
        for chunk in doc["chunks"]:
            c_words = set(clean(chunk["text"]).split())
            score = len(q_words & c_words)
            if clean(query) in clean(chunk["text"]):
                score += 3
            if score > 0:
                scored.append((score, chunk))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]


# ── System prompt ──────────────────────────────────────────────────────────────

def build_system_prompt(chunks: list[dict]) -> str:
    base = (
        "You are a clinical support assistant for a Licensed Maternity Carer (LMC) midwifery practice "
        "in Northland, New Zealand.\n\n"
        "You help with four things:\n"
        "1. Clinical policy and guideline questions — answered from Google Drive documents\n"
        "2. Professional email drafting — in the midwife's voice, saved as Outlook drafts (never sent automatically)\n"
        "3. Calendar management — checking availability, booking, viewing, editing and cancelling appointments\n"
        "4. Scheduling and referral support\n\n"
        "How to respond:\n"
        "• Be concise and direct. No filler phrases.\n"
        "• Use plain, professional language a midwife can use straight away.\n"
        "• Structure responses with clear headings and short paragraphs.\n"
        "• Cite the source document whenever drawing from loaded guidelines.\n"
        "• If information is not in the loaded documents, say so — do not guess.\n"
        "• Flag urgent or transfer-level clinical situations clearly at the top.\n"
        "• For email drafts: always confirm the draft has been saved to Outlook Drafts for review.\n"
        "• For calendar: confirm bookings with date, time and duration.\n"
        "• You are NOT a clinical decision tool. State this briefly if relevant.\n"
        "• Never process identifiable client information (names, NHI numbers, clinical records).\n"
        "• You operate under the NZ Privacy Act 2020.\n\n"
        "Tone: Warm, precise, collegial. Like a well-informed colleague speaking clearly under time pressure."
    )
    if chunks:
        seen_docs = list({c["doc_name"] for c in chunks})
        context_block = "\n\n---\n\n".join(
            f"[From: {c['doc_name']}]\n{c['text']}" for c in chunks
        )
        base += (
            f"\n\n── LOADED DOCUMENT EXCERPTS ──────────────────────────────────\n"
            f"Sources: {', '.join(seen_docs)}\n\n{context_block}\n\n"
            f"── END OF DOCUMENT CONTEXT ───────────────────────────────────\n"
            "Use the excerpts above to ground your answer. Always cite which document you draw from."
        )
    else:
        base += (
            "\n\nNote: No documents are currently loaded. The Google Drive folder may need syncing. "
            "Ask the user to trigger a Drive sync or upload documents manually."
        )
    return base


# ── Models ─────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]

class CreateEventRequest(BaseModel):
    title: str
    start_datetime: str          # ISO 8601 e.g. "2026-05-01T14:00:00"
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
    body_html: str


# ── Frontend ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    html = static_dir / "index.html"
    if html.exists():
        return HTMLResponse(html.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>index.html not found in static/</h1>", status_code=404)


# ── Chat ───────────────────────────────────────────────────────────────────────

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
            async with client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=system,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield f"data: {json.dumps({'text': text})}\n\n"
            if chunks:
                sources = list({c["doc_name"] for c in chunks})
                yield f"data: {json.dumps({'sources': sources})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


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
    redirect_uri = f"{BASE_URL}/auth/google/callback"
    flow = build_google_flow(redirect_uri)
    auth_url, _ = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    return RedirectResponse(auth_url)


@app.get("/auth/google/callback")
async def google_auth_callback(code: str = Query(...), state: str = Query(default="")):
    redirect_uri = f"{BASE_URL}/auth/google/callback"
    flow = build_google_flow(redirect_uri)
    flow.fetch_token(code=code)
    creds = flow.credentials
    token_dict = credentials_to_dict(creds)
    return HTMLResponse(f"""
    <html><body style="font-family:sans-serif;padding:40px">
    <h2>Google connected ✓</h2>
    <p>Copy this token and add it as the <strong>GOOGLE_TOKEN</strong> environment variable in Railway:</p>
    <textarea rows="6" style="width:100%;font-size:12px">{json.dumps(token_dict)}</textarea>
    <p>After saving in Railway, redeploy the service. Then close this tab.</p>
    </body></html>
    """)


@app.get("/api/google/status")
async def google_status():
    creds = get_google_credentials()
    return {"connected": creds is not None and creds.valid}


# ── Microsoft OAuth ────────────────────────────────────────────────────────────

@app.get("/auth/outlook")
async def outlook_auth_start():
    redirect_uri = f"{BASE_URL}/auth/outlook/callback"
    auth_url = build_ms_auth_url(redirect_uri)
    return RedirectResponse(auth_url)


@app.get("/auth/outlook/callback")
async def outlook_auth_callback(code: str = Query(...)):
    redirect_uri = f"{BASE_URL}/auth/outlook/callback"
    try:
        token_data = exchange_ms_code(code, redirect_uri)
    except Exception as e:
        raise HTTPException(400, str(e))
    return HTMLResponse(f"""
    <html><body style="font-family:sans-serif;padding:40px">
    <h2>Outlook connected ✓</h2>
    <p>Copy this token and add it as the <strong>OUTLOOK_TOKEN</strong> environment variable in Railway:</p>
    <textarea rows="6" style="width:100%;font-size:12px">{json.dumps(token_data)}</textarea>
    <p>After saving in Railway, redeploy the service. Then close this tab.</p>
    </body></html>
    """)


@app.get("/api/outlook/status")
async def outlook_status():
    token = get_ms_token()
    return {"connected": token is not None}


# ── Google Drive sync ──────────────────────────────────────────────────────────

@app.post("/api/drive/sync")
async def drive_sync(force: bool = False):
    creds = get_google_credentials()
    if not creds:
        raise HTTPException(401, "Google not connected. Visit /auth/google first.")
    try:
        result = sync_drive_to_knowledge_base(creds, document_store, chunk_text, force_full=force)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/drive/status")
async def drive_status():
    creds = get_google_credentials()
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
    return {
        "connected": creds is not None,
        "folder_id": folder_id,
        "docs_loaded": len(document_store),
    }


# ── Calendar endpoints ─────────────────────────────────────────────────────────

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


# ── Outlook email endpoints ────────────────────────────────────────────────────

def _require_outlook():
    token = get_ms_token()
    if not token:
        raise HTTPException(401, "Outlook not connected. Visit /auth/outlook first.")
    return token


@app.get("/api/email/inbox")
async def email_inbox(top: int = 20, unread_only: bool = False):
    token = _require_outlook()
    try:
        return list_inbox(token, top=top, unread_only=unread_only)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/email/message/{message_id}")
async def email_get(message_id: str):
    token = _require_outlook()
    try:
        return get_email(token, message_id)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/email/thread/{conversation_id}")
async def email_thread(conversation_id: str):
    token = _require_outlook()
    try:
        return get_thread(token, conversation_id)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/email/draft")
async def email_create_draft(req: DraftEmailRequest):
    """Create a draft in Outlook. Never sends automatically."""
    token = _require_outlook()
    try:
        return create_draft(token, req.to, req.subject, req.body_html,
                            req.reply_to_id, req.cc)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.patch("/api/email/draft")
async def email_update_draft(req: UpdateDraftRequest):
    token = _require_outlook()
    try:
        return update_draft(token, req.draft_id, req.body_html)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.delete("/api/email/draft/{draft_id}")
async def email_delete_draft(draft_id: str):
    token = _require_outlook()
    try:
        return delete_draft(token, draft_id)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/email/drafts")
async def email_list_drafts():
    token = _require_outlook()
    try:
        return list_drafts(token)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/email/search")
async def email_search(q: str, top: int = 10):
    token = _require_outlook()
    try:
        return search_emails(token, q, top)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/email/read/{message_id}")
async def email_mark_read(message_id: str):
    token = _require_outlook()
    try:
        return mark_read(token, message_id)
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "documents": len(document_store),
        "total_chunks": sum(d["chunk_count"] for d in document_store.values()),
        "google_connected": get_google_credentials() is not None,
        "outlook_connected": get_ms_token() is not None,
    }


# ── Entry ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
