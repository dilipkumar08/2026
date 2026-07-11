"""
FastAPI backend for a single-purpose RAG app pre-loaded with a fixed corpus
(The Adventures of Sherlock Holmes, public domain).

The index is NOT built by this server. It must already exist on disk,
produced ahead of time by running:
    python fetch_corpus.py
    python build_index.py

At server startup, this app just loads that existing index into memory
(fast) and builds the chat chain. There is no upload endpoint and no
chunking/embedding progress bar in the API — that work happens once at the
command line, not while the frontend is loading.

Endpoints:
  GET  /api/status  -> is the index built on disk? is chat ready in memory?
  POST /api/chat    -> SSE stream of answer tokens. Body: {"question": str}
"""
import asyncio
import json
import os
from contextlib import asynccontextmanager
from queue import Queue, Empty
from threading import Thread

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import vectorize
import rag_chain

BASE_DIR = os.path.dirname(__file__)
VECTOR_PATH = os.path.join(BASE_DIR, "vectorDB")
CORPUS_PATH = os.path.join(BASE_DIR, "data", "sherlock_holmes.txt")

state = {"vectorstore": None, "chain": None, "load_error": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once when the server starts. Only LOADS an existing index
    # (fast) — never builds one. If it's missing, we just record why,
    # and /api/status + /api/chat will report it clearly.
    if os.path.exists(VECTOR_PATH):
        try:
            vs = vectorize.load_index(VECTOR_PATH)
            state["vectorstore"] = vs
            state["chain"] = rag_chain.build_chain(vs, "v1")
            print(f"[startup] Loaded index from {VECTOR_PATH}. Chat is ready.")
        except Exception as e:
            state["load_error"] = str(e)
            print(f"[startup] Failed to load index: {e}")
    else:
        state["load_error"] = (
            "No index found. Run `python build_index.py` in the backend "
            "folder, then restart this server."
        )
        print(f"[startup] {state['load_error']}")
    yield


app = FastAPI(title="Sherlock Holmes RAG Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@app.get("/api/status")
def status():
    return {
        "index_exists": os.path.exists(VECTOR_PATH),
        "corpus_exists": os.path.exists(CORPUS_PATH),
        "chain_ready": state["chain"] is not None,
        "load_error": state["load_error"],
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    if state["chain"] is None:
        raise HTTPException(
            status_code=400,
            detail=state["load_error"] or "Index not ready.",
        )

    chain = state["chain"]

    async def token_stream():
        loop = asyncio.get_event_loop()
        q: Queue = Queue()

        def worker():
            try:
                for token in chain.stream(req.question):
                    q.put({"token": token})
            except Exception as e:
                q.put({"error": str(e)})
            finally:
                q.put(None)

        Thread(target=worker, daemon=True).start()

        while True:
            try:
                item = await loop.run_in_executor(None, q.get, True, 0.5)
            except Empty:
                continue
            if item is None:
                break
            yield _sse(item)

    return StreamingResponse(token_stream(), media_type="text/event-stream")
