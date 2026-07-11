"""
RAG pipeline logic, adapted from pdf_to_vector.py.

Key differences from the original script:
- Everything is scoped to a session (no hardcoded "mahabharata.pdf" path).
- Embeddings / FAISS index live only in memory (session_store dict).
- Nothing is ever written to disk (no faiss.write_index call).
- Progress is reported via a callback so the API layer can expose it.
- Embedding + reranker models are loaded once at module import and reused
  across sessions (loading them per-session would be slow and wasteful).
"""
from typing import Callable, List, Optional
import re
import os

import numpy as np
import faiss
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer, CrossEncoder
from huggingface_hub import InferenceClient

ProgressCB = Optional[Callable[[int, str], None]]

# Loaded once, shared (read-only at inference time) across all sessions.
_embed_model: Optional[SentenceTransformer] = None
_reranker: Optional[CrossEncoder] = None

HF_MODEL = "moonshotai/Kimi-K2.5"


def get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _embed_model


def get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _reranker


def get_llm_client() -> InferenceClient:
    return InferenceClient(model=HF_MODEL, token=os.getenv("HF_TOKEN"))


def extract_pdf_text(pdf_path: str, progress_cb: ProgressCB = None) -> str:
    reader = PdfReader(pdf_path)
    total = len(reader.pages)
    content = ""
    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text()
        if text:
            content += " " + text
        if progress_cb:
            # Extraction spans 0-20%
            pct = int((page_num / max(total, 1)) * 20)
            progress_cb(pct, f"Extracting text: page {page_num}/{total}")
    return re.sub(r"\s+", " ", content).strip()


def chunk_text(content: str, chunk_size: int) -> List[str]:
    chunks = []
    skip_size = (chunk_size * 90) // 100
    for start in range(0, len(content), skip_size):
        chunks.append(content[start:start + chunk_size])
    return chunks


def embed_chunks(chunks: List[str], progress_cb: ProgressCB = None) -> np.ndarray:
    model = get_embed_model()
    batch_size = 16
    vectors = []
    total = len(chunks)
    for i in range(0, total, batch_size):
        batch = chunks[i:i + batch_size]
        vectors.append(model.encode(batch))
        if progress_cb:
            done = min(i + batch_size, total)
            # Embedding spans 20-85%
            pct = 20 + int((done / max(total, 1)) * 65)
            progress_cb(pct, f"Embedding chunks: {done}/{total}")
    return np.vstack(vectors).astype("float32")


def build_index(vectors: np.ndarray) -> faiss.IndexFlatL2:
    dimension = vectors.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(vectors)
    return index


def process_pdf(pdf_path: str, chunk_size: int, progress_cb: ProgressCB = None):
    """Runs the full pipeline for one session and returns (chunks, index).
    Nothing here is persisted to disk."""
    if progress_cb:
        progress_cb(0, "Reading PDF")
    text = extract_pdf_text(pdf_path, progress_cb)

    if progress_cb:
        progress_cb(20, "Splitting into chunks")
    chunks = chunk_text(text, chunk_size)

    vectors = embed_chunks(chunks, progress_cb)

    if progress_cb:
        progress_cb(90, "Building vector index")
    index = build_index(vectors)

    if progress_cb:
        progress_cb(100, "Ready")
    return chunks, index


def retrieve(query: str, chunks: List[str], index: faiss.IndexFlatL2, top_k: int = 3) -> List[str]:
    model = get_embed_model()
    query_vector = model.encode([query]).astype("float32")
    _, indices = index.search(query_vector, min(top_k, len(chunks)))
    return [chunks[i] for i in indices[0]]


def rerank(query: str, retrieved_chunks: List[str]) -> List[str]:
    reranker = get_reranker()
    pairs = [[query, chunk] for chunk in retrieved_chunks]
    scores = reranker.predict(pairs)
    reranked = sorted(zip(retrieved_chunks, scores), key=lambda x: x[1], reverse=True)
    return [chunk for chunk, _score in reranked]


def answer_query(query: str, context_chunks: List[str]) -> str:
    client = get_llm_client()
    response = client.chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert assistant. Use ONLY the provided context. "
                    "If the answer cannot be found in the context, say "
                    "'Information not found in the knowledge base.' Do not make up facts."
                ),
            },
            {"role": "user", "content": f"Context:{context_chunks} Question:{query}"},
        ],
        max_tokens=500,
        stream=False,
        extra_body={"thinking": {"type": "disabled"}},
    )
    return response.choices[0].message.content
