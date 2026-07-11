# RAG Chat — Backend + Angular Frontend

## What changed vs. your original scripts
- `main.py` (CLI) is replaced by `backend/main_api.py`, a FastAPI server exposing:
  - `GET  /api/status` — whether a vector DB / PDF already exists
  - `POST /api/upload` — upload a PDF, **rejected server-side if > 1 MB**
  - `POST /api/embed` — `{ "reembed": bool }`, streams progress via Server-Sent Events
  - `POST /api/chat` — `{ "question": str }`, streams answer tokens via SSE
  - `POST /api/session/end` — deletes the vector DB folder + uploaded PDF, clears in-memory state
- `backend/vectorize.py` — same logic as your original, but `create_vector` now takes a
  `pdf_path` argument and an optional `progress_cb(stage, current, total, message)` callback,
  called while reading pages, chunking, and embedding batches.
- `backend/rag_chain.py` — same logic, prompt directory is configurable via `RAG_PROMPT_DIR`
  env var (defaults to `backend/prompts/`).
- `frontend/` — a small Angular 17 (standalone components) app with a dark, sleek UI:
  1. Drag-and-drop PDF upload, blocked client-side if file > 1 MB (mirrors the server check).
  2. If a vector DB already exists, asks **"Re-embed from new PDF or reuse existing index?"**
  3. Live progress bar while pages are read / chunked / embedded (driven by the SSE stream).
  4. Chat view with streaming token-by-token answers.
  5. **"End session & delete embeddings"** button — calls `/api/session/end`, which deletes
     the FAISS index directory and the uploaded PDF.

## Requirements
- Ollama running locally with `gemma2:2b` and `nomic-embed-text` pulled (same as your original code).
- Python 3.10+, Node 18+, Angular CLI.

## Run the backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main_api:app --reload --port 8000
```

Note: `BASE_DIR` in `main_api.py` is currently set to your original path
(`/media/storage/python/projects/RAG/Langchain/project1`). Change it if needed — it's the
folder where the uploaded PDF and `vectorDB/` folder will live.

## Run the frontend
```bash
cd frontend
npm install
npm start
```
Then open http://localhost:4200. The frontend expects the backend at http://localhost:8000
(see `API_BASE` in `src/app/services/api.service.ts` if you need to change it).

## Notes / things you may want to tune
- The 1 MB limit lives in two places: `MAX_PDF_BYTES` in `backend/main_api.py` and
  `MAX_PDF_BYTES` in `frontend/src/app/services/api.service.ts` — keep them in sync.
- The embedding progress percentage is per-stage (reading pages, then chunking, then
  embedding batches) rather than one single global percentage — the UI just shows whatever
  the current stage reports, which is usually clearer than a single blended number.
- This is wired for single-user local use (in-memory state, no auth), matching your original
  CLI script's scope.
