from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document
from typing import Callable, Optional
import os
import re

ProgressCB = Optional[Callable[[str, int, int, str], None]]


def _noop(stage: str, current: int, total: int, message: str):
    pass


def build_index(vector_path: str, corpus_path: str, progress_cb: ProgressCB = None) -> FAISS:
    """
    Build the FAISS vector store from a fixed plain-text corpus file.
    Called once at startup if vector_path doesn't already exist.
    """
    cb = progress_cb or _noop

    if not os.path.exists(corpus_path):
        raise FileNotFoundError(
            f"Corpus file not found at {corpus_path}. Run `python fetch_corpus.py` first."
        )

    cb("reading", 0, 1, "Reading corpus file...")
    with open(corpus_path, "r", encoding="utf-8") as f:
        text = f.read()
    text = re.sub(r"\s+", " ", text).strip()
    cb("reading", 1, 1, f"Read {len(text):,} characters")

    source_doc = [Document(page_content=text)]

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    cb("chunking", 0, 1, "Splitting text into chunks...")
    chunks = splitter.split_documents(source_doc)
    total_chunks = len(chunks)
    cb("chunking", 1, 1, f"Created {total_chunks} chunks")

    vectorstore = None
    embeddings = OllamaEmbeddings(model="nomic-embed-text")

    batch_size = 50
    num_batches = (total_chunks + batch_size - 1) // batch_size
    for batch_idx, i in enumerate(range(0, total_chunks, batch_size)):
        batch = chunks[i:i + batch_size]
        if vectorstore is None:
            vectorstore = FAISS.from_documents(batch, embeddings)
        else:
            vectorstore.add_documents(batch)
        cb("embedding", batch_idx + 1, num_batches,
           f"Embedded batch {batch_idx + 1}/{num_batches}")

    vectorstore.save_local(vector_path)
    cb("done", 1, 1, "Embedding completed")
    return vectorstore


def load_index(vector_path: str) -> FAISS:
    """Load a previously built FAISS vector store from disk."""
    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    return FAISS.load_local(vector_path, embeddings, allow_dangerous_deserialization=True)
