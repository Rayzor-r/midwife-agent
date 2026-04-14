"""
Midwife AI Agent — Backend
FastAPI server · Anthropic streaming · In-memory RAG · Document upload
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
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(title="Midwife AI Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ── Document store (in-memory) ─────────────────────────────────────────────────
# { doc_id: { id, name, chunks: [...], chunk_count, char_count, uploaded_at } }
document_store: dict = {}

CHUNK_SIZE    = 650   # characters per chunk
CHUNK_OVERLAP = 120   # overlap between chunks


# ── Document processing ────────────────────────────────────────────────────────

def chunk_text(text: str, doc_id: str, doc_name: str) -> list[dict]:
    """Split text into overlapping chunks, breaking at sentence boundaries."""
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
            chunks.append({
                "id":        f"{doc_id}_{idx}",
                "doc_id":    doc_id,
                "doc_name":  doc_name,
                "text":      snippet,
                "chunk_idx": idx,
            })
            idx += 1
        start = end - CHUNK_OVERLAP
    return chunks


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract plain text from PDF, DOCX, or TXT."""
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        import pdfplumber
        parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    parts.append(t)
        return "\n\n".join(parts)

    if ext == ".docx":
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())

    if ext in (".txt", ".md"):
        return file_bytes.decode("utf-8", errors="replace")

    raise ValueError(f"Unsupported file type: {ext}")


# ── RAG search ─────────────────────────────────────────────────────────────────

def search_documents(query: str, top_k: int = 10) -> list[dict]:
    """Keyword + phrase search across all indexed chunks."""
    clean  = lambda s: re.sub(r"[^\w\s]", "", s.lower())
    q_words = set(clean(query).split())
    if not q_words:
        return []

    scored = []
    for doc in document_store.values():
        for chunk in doc["chunks"]:
            c_words    = set(clean(chunk["text"]).split())
            word_score = len(q_words & c_words)
            phrase_bonus = 3 if clean(query) in clean(chunk["text"]) else 0
            score = word_score + phrase_bonus
            if score > 0:
                scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]


# ── System prompt ──────────────────────────────────────────────────────────────

def build_system_prompt(chunks: list[dict]) -> str:
    base = (
        "You are a clinical support assistant for a Licensed Maternity Carer (LMC) midwifery practice "
        "in Northland, New Zealand.\n\n"
        "You help with three things:\n"
        "1. Clinical policy and guideline questions — answered from uploaded documents\n"
        "2. Professional email drafting — on behalf of the midwife\n"
        "3. Scheduling and referral support\n\n"
        "How to respond:\n"
        "• Be concise and direct. No filler phrases, no enthusiastic openers.\n"
        "• Use plain, professional language a midwife can copy straight into clinical notes or an email.\n"
        "• Structure responses with clear headings and short paragraphs. Use tables where helpful.\n"
        "• Cite the source document name whenever drawing from loaded guidelines.\n"
        "• If information is not in the loaded documents, say so plainly — do not guess.\n"
        "• Flag urgent or transfer-level clinical situations clearly at the top of your response.\n"
        "• Never ask unnecessary follow-up questions — answer fully, then stop.\n"
        "• You are NOT a clinical decision tool. State this briefly if relevant, then give the information.\n"
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
            f"Sources: {', '.join(seen_docs)}\n\n"
            f"{context_block}\n\n"
            f"── END OF DOCUMENT CONTEXT ───────────────────────────────────\n"
            "Use the excerpts above to ground your answer. Always cite which document you draw from."
        )
    else:
        base += (
            "\n\nNote: No documents are currently loaded. For policy questions, ask the user "
            "to upload their hospital guidelines or NZ College of Midwives documents in the sidebar."
        )

    return base


# ── Models ─────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role:    str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    html = static_dir / "index.html"
    if html.exists():
        return HTMLResponse(html.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>index.html not found in static/</h1>", status_code=404)


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Streaming chat via Server-Sent Events."""
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

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload, extract, and index a document."""
    allowed = {".pdf", ".docx", ".txt", ".md"}
    ext = Path(file.filename).suffix.lower()

    if ext not in allowed:
        raise HTTPException(400, f"'{ext}' not supported. Use PDF, DOCX, or TXT.")

    data = await file.read()

    try:
        text = extract_text(data, file.filename)
    except Exception as e:
        raise HTTPException(422, f"Text extraction failed: {e}")

    if not text.strip():
        raise HTTPException(422, "No text could be extracted from this file.")

    doc_id = str(uuid.uuid4())[:8]
    chunks = chunk_text(text, doc_id, file.filename)

    document_store[doc_id] = {
        "id":          doc_id,
        "name":        file.filename,
        "chunks":      chunks,
        "chunk_count": len(chunks),
        "char_count":  len(text),
        "uploaded_at": datetime.now().isoformat(),
    }

    return {
        "doc_id":  doc_id,
        "name":    file.filename,
        "chunks":  len(chunks),
        "message": f"Indexed {len(chunks)} sections from '{file.filename}'",
    }


@app.get("/api/documents")
async def list_documents():
    return [
        {
            "id":          d["id"],
            "name":        d["name"],
            "chunks":      d["chunk_count"],
            "uploaded_at": d["uploaded_at"],
        }
        for d in document_store.values()
    ]


@app.delete("/api/documents/{doc_id}")
async def delete_document(doc_id: str):
    if doc_id not in document_store:
        raise HTTPException(404, "Document not found")
    name = document_store.pop(doc_id)["name"]
    return {"message": f"Removed '{name}' from knowledge base"}


@app.get("/api/health")
async def health():
    return {
        "status":       "ok",
        "documents":    len(document_store),
        "total_chunks": sum(d["chunk_count"] for d in document_store.values()),
    }


# ── Entry ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
