"""
Ingest the fixed dataset documentation into the RAG store.
------------------------------------------------------------
Two-level hierarchical chunking:
  Level 1: split by Markdown headers (# and ##) — each chunk knows which
           section it belongs to.
  Level 2: within each section, split further by character count so no
           single chunk is too large to embed/retrieve meaningfully.

Each stored chunk keeps its parent section name as metadata, so a
retrieved chunk always carries its context (e.g. "Business rules and
definitions > Delayed shipment") instead of being an orphaned paragraph.

Embeddings come from BAAI/bge-m3, run locally via sentence-transformers
(through langchain_huggingface's HuggingFaceEmbeddings) — no HF token and
no network calls at embed time. The model weights (~2GB) are downloaded
once from the Hugging Face Hub the first time this runs and then cached
locally (default cache: ~/.cache/huggingface), so you still need internet
access for that one-time download, just not an API token.

Run once:
    export RAG_DB_URI="postgresql://postgres:postgres@localhost:5432/postgres"
    python mcp_server/ingest_docs.py

NOTE: this requires db/schema.sql to have been applied with vector(1024),
matching bge-m3's output dimension — NOT vector(768), which was sized for
nomic-embed-text instead. If you ran an older version of schema.sql, drop
and recreate doc_chunks before re-running this:
    DROP TABLE IF EXISTS doc_chunks;
    -- then re-apply the corrected schema.sql
"""

import os
from pathlib import Path

import psycopg
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings

DB_URI = os.environ.get(
    "RAG_DB_URI", "postgresql://postgres:postgres@localhost:5432/postgres"
)
DOCS_PATH = Path(os.environ.get("DOCS_PATH", "/media/storage/python/projects/langgraph/dataset visualizer/docs/dataset_docs.md"))

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-m3")
# CPU by default so this works with no GPU setup out of the box. Set
# EMBEDDING_DEVICE=cuda if you have a GPU and want faster ingestion.
EMBEDDING_DEVICE = os.environ.get("EMBEDDING_DEVICE", "cpu")

# Level 1: split by headers, keep hierarchy in metadata
HEADER_SPLITTER = MarkdownHeaderTextSplitter(
    headers_to_split_on=[("#", "h1"), ("##", "h2")]
)

# Level 2: split each section further if it's still large
CHAR_SPLITTER = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

embeddings = HuggingFaceEmbeddings(
    model_name=EMBEDDING_MODEL,
    model_kwargs={"device": EMBEDDING_DEVICE},
    encode_kwargs={"normalize_embeddings": True},
)


def build_chunks() -> list[dict]:
    text = DOCS_PATH.read_text()
    header_docs = HEADER_SPLITTER.split_text(text)  # level 1: by section

    chunks = []
    for doc in header_docs:
        section = doc.metadata.get("h2") or doc.metadata.get("h1") or "General"
        sub_chunks = CHAR_SPLITTER.split_text(doc.page_content)  # level 2: by size
        for sub in sub_chunks:
            chunks.append({"section": section, "content": sub})
    return chunks


def main():
    chunks = build_chunks()
    print(f"Built {len(chunks)} hierarchical chunks from {DOCS_PATH}")

    vectors = embeddings.embed_documents([c["content"] for c in chunks])

    with psycopg.connect(DB_URI, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM doc_chunks")  # idempotent re-run
            for chunk, vector in zip(chunks, vectors):
                cur.execute(
                    "INSERT INTO doc_chunks (section, content, embedding) VALUES (%s, %s, %s)",
                    (chunk["section"], chunk["content"], vector),
                )
    print("Ingestion complete.")


if __name__ == "__main__":
    main()