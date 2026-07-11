"""
Minimal FastAPI backend for the Angular PDF-RAG frontend.

Sessions are kept entirely in memory (a plain dict). Nothing about a
session - the uploaded PDF, its chunks, or its embeddings - is written
to disk for longer than it takes to process it, and everything for a
session is deleted as soon as the user closes the session (or the
process restarts).
"""
import os
import shutil
import tempfile
import threading
import uuid
from typing import Dict

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import rag_pipeline as rag

MAX_FILE_BYTES = 1 * 1024 * 1024  # 1 MB
DEFAULT_CHUNK_SIZE = 500

app = FastAPI(title="PDF RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# session_id -> { status, progress, message, chunks, index, tmp_dir }
sessions: Dict[str, dict] = {}
sessions_lock = threading.Lock()


class QueryRequest(BaseModel):
    query: str


def _process_in_background(session_id: str, pdf_path: str, chunk_size: int):
    def progress_cb(pct: int, message: str):
        with sessions_lock:
            if session_id in sessions:
                sessions[session_id]["progress"] = pct
                sessions[session_id]["message"] = message

    try:
        chunks, index = rag.process_pdf(pdf_path, chunk_size, progress_cb)
        with sessions_lock:
            if session_id in sessions:
                sessions[session_id]["chunks"] = chunks
                sessions[session_id]["index"] = index
                sessions[session_id]["status"] = "ready"
                sessions[session_id]["progress"] = 100
                sessions[session_id]["message"] = "Ready"
    except Exception as exc:  # noqa: BLE001
        with sessions_lock:
            if session_id in sessions:
                sessions[session_id]["status"] = "error"
                sessions[session_id]["message"] = str(exc)


@app.post("/api/session/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if file.content_type != "application/pdf" and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    contents = await file.read()
    if len(contents) > MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="File must be smaller than 1 MB.")
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    session_id = str(uuid.uuid4())
    tmp_dir = tempfile.mkdtemp(prefix=f"rag_{session_id}_")
    pdf_path = os.path.join(tmp_dir, "upload.pdf")
    with open(pdf_path, "wb") as f:
        f.write(contents)

    with sessions_lock:
        sessions[session_id] = {
            "status": "processing",
            "progress": 0,
            "message": "Starting",
            "chunks": None,
            "index": None,
            "tmp_dir": tmp_dir,
        }

    thread = threading.Thread(
        target=_process_in_background,
        args=(session_id, pdf_path, DEFAULT_CHUNK_SIZE),
        daemon=True,
    )
    thread.start()

    return {"session_id": session_id}


@app.get("/api/session/{session_id}/progress")
async def get_progress(session_id: str):
    with sessions_lock:
        session = sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")
        return {
            "status": session["status"],
            "progress": session["progress"],
            "message": session["message"],
        }


@app.post("/api/session/{session_id}/query")
async def query_session(session_id: str, body: QueryRequest):
    with sessions_lock:
        session = sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")
        if session["status"] != "ready":
            raise HTTPException(status_code=409, detail="Session is not ready yet.")
        chunks = session["chunks"]
        index = session["index"]

    retrieved = rag.retrieve(body.query, chunks, index, top_k=3)
    reranked = rag.rerank(body.query, retrieved)
    answer = rag.answer_query(body.query, reranked)
    return {"answer": answer}


def _cleanup_session(session_id: str):
    with sessions_lock:
        session = sessions.pop(session_id, None)
    if session:
        tmp_dir = session.get("tmp_dir")
        if tmp_dir and os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        # Explicitly drop references so embeddings/index are freed immediately.
        session["chunks"] = None
        session["index"] = None


@app.post("/api/session/{session_id}/close")
async def close_session(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found.")
    _cleanup_session(session_id)
    return {"status": "closed"}


@app.get("/api/health")
async def health():
    return {"status": "ok"}
        