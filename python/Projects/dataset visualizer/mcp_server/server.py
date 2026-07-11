"""
Data Insights MCP Server — Streamable HTTP
---------------------------------------------
4 real tools:
  - search_dataset_docs : RAG (pgvector similarity + cross-encoder rerank)
  - run_sql_query        : read-only SQL against the uploaded dataset (DuckDB)
  - create_chart          : GROUP BY aggregation, returns chart-ready JSON
  - export_summary_doc    : writes an actual .docx with python-docx

Embeddings are BAAI/bge-m3, run locally via sentence-transformers (same
approach as the reranker below) — no HF token, no network call per
request. See EMBEDDING_MODEL / EMBEDDING_DEVICE below.

Run:
    export RAG_DB_URI="postgresql://postgres:postgres@localhost:5432/postgres"
    export DUCKDB_PATH="./dataset.duckdb"
    export EXPORT_DIR="./exports"
    python mcp_server/server.py
    # listening on http://localhost:9000/mcp
"""

import os
import re
import json
import math
from pathlib import Path

import duckdb
import psycopg
from mcp.server.fastmcp import FastMCP
from langchain_huggingface import HuggingFaceEmbeddings
from sentence_transformers import CrossEncoder
from docx import Document

RAG_DB_URI = os.environ.get(
    "RAG_DB_URI", "postgresql://postgres:postgres@localhost:5432/postgres"
)
DUCKDB_PATH = os.environ.get("DUCKDB_PATH", "./dataset.duckdb")
EXPORT_DIR = Path(os.environ.get("EXPORT_DIR", "./exports"))
EXPORT_DIR.mkdir(exist_ok=True)

mcp = FastMCP("data-insights", host="0.0.0.0", port=9000)

# BGE-M3 outputs 1024-dim vectors — make sure doc_chunks.embedding is
# vector(1024) in schema.sql, and re-run ingest_docs.py, since the old
# 768-dim nomic-embed-text vectors aren't compatible with this model.
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-m3")
# CPU by default so this works with no GPU setup out of the box. Set
# EMBEDDING_DEVICE=cuda if you have a GPU and want faster queries.
EMBEDDING_DEVICE = os.environ.get("EMBEDDING_DEVICE", "cpu")

# Loaded once at process startup, same lifecycle as the reranker below -
# both are local sentence-transformers models, no API calls, no token.
embeddings = HuggingFaceEmbeddings(
    model_name=EMBEDDING_MODEL,
    model_kwargs={"device": EMBEDDING_DEVICE},
    encode_kwargs={"normalize_embeddings": True},
)

# Loaded once at process startup — a cross-encoder scores a (query, chunk)
# pair directly, which is more accurate than pure embedding similarity but
# too slow to run over an entire corpus, hence: embed-search first, then
# rerank only the top candidates.
reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

ALLOWED_AGG = {"sum", "avg", "count", "min", "max"}
# Only SELECT statements are allowed. This is a blunt guard, not a parser —
# see README "Edge cases" for why this needs to be hardened before any real
# deployment (the honest answer is: a real system uses a read-only DB role,
# not string matching).
FORBIDDEN_SQL_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|COPY|PRAGMA|EXPORT|IMPORT)\b",
    re.IGNORECASE,
)


def get_duckdb_conn(read_only: bool = True):
    return duckdb.connect(DUCKDB_PATH, read_only=read_only)


def _json_safe(value):
    """Replace NaN/Infinity with None. Standard JSON has no representation
    for these (Python's json.dumps will happily emit the literal token
    'NaN', which is NOT valid JSON per spec — Starlette's stricter response
    encoder rejects it outright with ValueError: Out of range float values
    are not JSON compliant). NaN shows up here whenever a GROUP BY includes
    a NULL in the aggregated column."""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


# ---------------------------------------------------------------------------
# TOOL 1 — RAG: pgvector similarity search + cross-encoder rerank
# ---------------------------------------------------------------------------

@mcp.tool()
def search_dataset_docs(query: str, top_k: int = 3) -> str:
    """Search the dataset documentation for column definitions, business
    rules, and terminology (e.g. "what counts as a delayed shipment",
    "what does profit margin mean"). Use this before writing SQL that
    depends on a business rule, not for questions about actual data values.

    Args:
        query: Natural-language question about the dataset's meaning/rules.
        top_k: How many chunks to return after reranking. Default 3.
    """
    query_vector = embeddings.embed_query(query)

    # Stage 1: cheap, approximate — pull a wider candidate set by embedding
    # similarity (top 10), since embeddings alone are noisy at the margins.
    with psycopg.connect(RAG_DB_URI) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT section, content
                FROM doc_chunks
                ORDER BY embedding <=> %s::vector
                LIMIT 10
                """,
                (query_vector,),
            )
            candidates = cur.fetchall()

    if not candidates:
        return "No documentation found. Has ingest_docs.py been run?"

    # Stage 2: expensive, precise — rerank the 10 candidates with a
    # cross-encoder that actually reads (query, chunk) together, then keep
    # only the true top_k. This is the step that fixes cases where
    # embedding similarity ranks a topically-similar-but-wrong chunk above
    # the actually relevant one.
    pairs = [(query, content) for _, content in candidates]
    scores = reranker.predict(pairs)
    ranked = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)[:top_k]

    results = [f"[{section}]\n{content}" for _, (section, content) in ranked]
    return "\n\n---\n\n".join(results)


# ---------------------------------------------------------------------------
# TOOL 2 — SQL query against the uploaded dataset
# ---------------------------------------------------------------------------

@mcp.tool()
def list_dataset_columns() -> str:
    """List the exact column names and types present in the currently
    uploaded dataset table. Call this before writing SQL whenever you are
    not 100% certain a column exists or how it's named/cased -
    dataset_docs.md only documents the primary business columns (category,
    sales, profit, etc.), not every column a given upload may contain
    (e.g. product name, customer name, city, state). If run_sql_query
    fails because of an unknown column, call this and retry with the
    correct name before giving up.
    """
    conn = get_duckdb_conn(read_only=True)
    try:
        rows = conn.execute("DESCRIBE dataset").fetchall()
    except duckdb.Error as exc:
        return f"SQL error: {exc}"
    finally:
        conn.close()
    return json.dumps([{"column": r[0], "type": r[1]} for r in rows])


@mcp.tool()
def run_sql_query(sql: str) -> str:
    """Run a read-only SQL query against the uploaded dataset. The table is
    called `dataset`. Use search_dataset_docs first if you're unsure what a
    column means or what business rule applies (e.g. how "delayed" is
    defined) before writing the query.

    Args:
        sql: A SELECT statement. Only SELECT is permitted.
    """
    stripped = sql.strip().rstrip(";")
    if not stripped.upper().startswith("SELECT"):
        return "Rejected: only SELECT statements are allowed."
    if FORBIDDEN_SQL_KEYWORDS.search(stripped):
        return "Rejected: query contains a disallowed keyword."

    try:
        conn = get_duckdb_conn(read_only=True)
        result = conn.execute(stripped).fetchdf()
        conn.close()
    except duckdb.Error as exc:
        return f"SQL error: {exc}"

    if result.empty:
        return "Query returned no rows."
    # NaN-safe here too: to_json's default_handler doesn't cover NaN, but
    # pandas' own to_json DOES correctly emit "null" for NaN (unlike the
    # stdlib json module used in create_chart below) — kept as-is
    # deliberately to show both cases, but noting it so it's not mistaken
    # for an oversight.
    return result.to_json(orient="records")


# ---------------------------------------------------------------------------
# TOOL 3 — chart data (bar/line), computed via a GROUP BY in DuckDB
# ---------------------------------------------------------------------------

@mcp.tool()
def create_chart(chart_type: str, x_column: str, y_column: str, agg: str = "sum") -> str:
    """Compute aggregated data for a bar or line chart from the uploaded
    dataset. Returns JSON the frontend renders directly — this does not
    render an image, it returns the numbers.

    Args:
        chart_type: "bar" or "line".
        x_column: Column to group by (the chart's x-axis / categories).
        y_column: Numeric column to aggregate (the chart's y-axis / values).
        agg: One of sum, avg, count, min, max. Default sum.
    """
    if chart_type not in ("bar", "line"):
        return "Rejected: chart_type must be 'bar' or 'line'."
    if agg not in ALLOWED_AGG:
        return f"Rejected: agg must be one of {sorted(ALLOWED_AGG)}."
    # Column names are validated against the actual schema below, not just
    # passed straight into SQL — this is what prevents injection through
    # x_column/y_column even though we're building the query with f-strings.
    conn = get_duckdb_conn(read_only=True)
    try:
        schema_cols = {r[0] for r in conn.execute("DESCRIBE dataset").fetchall()}
        if x_column not in schema_cols or y_column not in schema_cols:
            return f"Rejected: columns must be one of {sorted(schema_cols)}."

        query = (
            f'SELECT "{x_column}" AS label, {agg}("{y_column}") AS value '
            f'FROM dataset GROUP BY "{x_column}" ORDER BY "{x_column}"'
        )
        result = conn.execute(query).fetchdf()
    except duckdb.Error as exc:
        return f"SQL error: {exc}"
    finally:
        conn.close()

    # FIX: replace any NaN/Infinity (from NULLs in the source data) with
    # None before serializing — json.dumps would otherwise emit the
    # non-standard "NaN" token, which FastAPI's response encoder rejects
    # with "Out of range float values are not JSON compliant".
    values = [_json_safe(v) for v in result["value"].tolist()]

    return json.dumps(
        {
            "chart_type": chart_type,
            "labels": result["label"].astype(str).tolist(),
            "values": values,
        }
    )


# ---------------------------------------------------------------------------
# TOOL 4 — export a real .docx summary
# ---------------------------------------------------------------------------

@mcp.tool()
def export_summary_doc(title: str, summary_text: str) -> str:
    """Generate a Word document containing an analysis summary and save it
    to disk. Returns the filename, which the API serves back for download.

    Args:
        title: Document title.
        summary_text: The body content — findings, numbers, conclusions.
    """
    doc = Document()
    doc.add_heading(title, level=1)
    for paragraph in summary_text.split("\n\n"):
        if paragraph.strip():
            doc.add_paragraph(paragraph.strip())

    # Sanitize the filename — title comes from the LLM, don't trust it
    # blindly as a path component.
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", title)[:50] or "summary"
    filename = f"{safe_name}.docx"
    doc.save(EXPORT_DIR / filename)

    return filename


if __name__ == "__main__":
    mcp.run(transport="streamable-http")