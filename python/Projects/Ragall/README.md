# RAGALL 

Upload a PDF (< 1 MB), watch it get embedded with a live progress bar, then
chat with it. Everything is session-scoped and **kept only in memory** —
closing the session (or restarting the backend) discards the PDF, its
chunks, and its embeddings. Nothing is ever written to a `.index` file.

```
pdf-rag-app/
├── backend/          FastAPI server (wraps your original pdf_to_vector.py logic)
│   ├── main.py
│   ├── rag_pipeline.py
│   └── requirements.txt
└── frontend/         Angular 17 standalone app
    └── src/app/...
```

## 1. Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate   # optional but recommended
pip install -r requirements.txt
export HF_TOKEN=your_huggingface_token
uvicorn main:app --reload --port 8000
```

Endpoints exposed:
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/session/upload` | multipart PDF upload, starts embedding in a background thread |
| GET  | `/api/session/{id}/progress` | poll for `{status, progress, message}` |
| POST | `/api/session/{id}/query` | `{query}` → retrieve, rerank, ask the LLM |
| POST | `/api/session/{id}/close` | deletes the session's chunks/index/temp file from memory & disk |

## 2. Frontend

```bash
cd frontend
npm install
npm start
```

This runs `ng serve --proxy-config proxy.conf.json`, which forwards `/api/*`
calls to `http://localhost:8000` so the two apps can talk to each other
locally without CORS headaches. Open `http://localhost:4200`.

## How the "no stored embeddings" requirement is met

- The uploaded PDF is written to a per-session temp folder only so `pypdf`
  can read it; the folder is deleted the moment the session is closed.
- Chunks and the FAISS `IndexFlatL2` live in a plain in-memory dict
  (`sessions`) inside `main.py` — there's no `faiss.write_index(...)` call
  anywhere, unlike the original script.
- Clicking **Close session** in the UI calls `POST /close`, which pops the
  session out of that dict and `shutil.rmtree`s the temp folder. The next
  upload always starts a brand-new session id with a fresh index — old
  embeddings are never reused.
- Restarting the backend process also wipes everything, since nothing
  persists outside memory.

## Notes / things you may want to adjust

- `DEFAULT_CHUNK_SIZE` in `main.py` is hardcoded (500). The original script
  asked for chunk size via `input()`; you could expose this as an optional
  form field from the upload screen if you want it configurable per file.
- The embedding and reranker models are loaded once at process startup and
  shared across sessions (only the chunks/index are session-specific) —
  reloading a ~90MB model per upload would make the progress bar much slower
  than it needs to be.
- CORS is wide open (`allow_origins=["*"]`) for local development. Lock this
  down before deploying anywhere public.
