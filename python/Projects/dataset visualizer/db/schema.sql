-- Run once: psql "$RAG_DB_URI" -f db/schema.sql
--
-- If you already ran the old version of this file (with vector(1536)),
-- drop and recreate the table — the dimension can't be altered in place:
--   DROP TABLE IF EXISTS doc_chunks;
-- then re-run this whole file, then re-run ingest_docs.py.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS doc_chunks (
    id          SERIAL PRIMARY KEY,
    section     TEXT NOT NULL,
    content     TEXT NOT NULL,
    -- FIX: nomic-embed-text (used via OllamaEmbeddings) produces 768-dim
    -- vectors, not 1536 — 1536 is OpenAI's text-embedding-3-small
    -- dimension. Inserting a 768-dim vector into a vector(1536) column
    -- fails immediately with a dimension mismatch error.
    embedding   vector(1024) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_doc_chunks_embedding
    ON doc_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);