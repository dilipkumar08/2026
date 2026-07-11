# Data Insights Copilot

A dataset Q&A + visualization assistant. Upload an Excel file, get bar/line
charts, ask natural-language questions grounded in real SQL queries and a
RAG'd business-rules doc, export findings as a Word doc — all orchestrated
by LangGraph, traced in LangSmith, with 4 real MCP tools.

## 1. Architecture

```
Angular frontend (upload, chart controls, chat, export)
        |
        v
FastAPI (api/main.py) — 3 roles:
   - hosts the LangGraph agent (chat)
   - a direct MCP client itself (chart, export — deterministic, no LLM)
   - owns the DuckDB write path (upload)
        |
   +----+-----------------------------+
   |                                  |
   v                                  v
LangGraph agent                MCP client (direct calls)
(agent/graph.py)                      |
   |                                  |
   +---------------+------------------+
                    v
        Data Insights MCP Server (Streamable HTTP, mcp_server/server.py)
                    |
        +-----------+-----------+-----------+
        v           v           v           v
   search_dataset  run_sql   create_chart  export_summary
   _docs (RAG)     _query    (DuckDB agg)  _doc (.docx)
        |           |
        v           v
   Postgres      DuckDB
   +pgvector    (dataset.duckdb —
   (doc_chunks)  the uploaded Excel)

Postgres also holds LangGraph's checkpoint tables (separate from doc_chunks).
LangSmith traces every LLM call, tool call, and node — passively via env
vars, and actively via the /feedback endpoint and eval script.
```

**Why 3 separate MCP clients?** This is deliberate, not accidental
complexity — it's the actual proof that Streamable HTTP does what STDIO
can't:
1. The **LangGraph agent** — for open-ended chat, lets the LLM decide which
   tool(s) to call.
2. **FastAPI's `/chart` and `/export` endpoints** — call MCP tools directly,
   no LLM involved, because a chart button click should be deterministic,
   not something an LLM might phrase a slightly different SQL query for
   each time.
3. **`client_demo.py`** (optional, same pattern as the simpler notes
   project) — a totally separate process you can run alongside everything
   else to prove the server serves concurrent, unrelated clients.

## 2. Setup

### Postgres (RAG store + LangGraph checkpoints)
```bash
docker run --name insights-pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d pgvector/pgvector:pg16
psql "postgresql://postgres:postgres@localhost:5432/postgres" -f db/schema.sql
```
(Using the `pgvector/pgvector` image instead of plain `postgres` — it ships
with the extension pre-installed.)

### Python env
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

export RAG_DB_URI="postgresql://postgres:postgres@localhost:5432/postgres"
export AGENT_DB_URI="postgresql://postgres:postgres@localhost:5432/postgres?sslmode=disable"
export DUCKDB_PATH="./dataset.duckdb"
export EXPORT_DIR="./exports"
export OPENAI_API_KEY="sk-..."
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY="ls-..."
export LANGCHAIN_PROJECT="data-insights-agent"
```

### Ingest the RAG docs (once)
```bash
python mcp_server/ingest_docs.py
```

### Start the MCP server (terminal 1, leave running)
```bash
python mcp_server/server.py
```

### Start the API (terminal 2)
```bash
uvicorn api.main:app --reload --port 8000
```

### Frontend (terminal 3)
```bash
cd frontend
ng new . --standalone --routing=false --style=css   # if not scaffolded yet
# copy these files over the generated ones
ng serve
```

### Try it
1. Upload an Excel file matching the documented schema (`order_id`,
   `order_date`, `ship_date`, `category`, `sub_category`, `sales`,
   `quantity`, `discount`, `profit`, `region`) — the public Kaggle
   "Superstore" dataset is the standard one to grab for this.
2. Plot: pick `region` / `sales` / `sum` / bar.
3. Ask: *"what's our total profit by category, and which categories have
   any loss-making line items?"* — this should trigger both
   `search_dataset_docs` (to confirm what "loss-making" means) and
   `run_sql_query`.
4. Ask a follow-up like *"what about just the West region?"* — proves the
   thread_id/checkpointing keeps context.
5. Click Export — downloads a real `.docx`.

## 3. Edge cases (know these — they're the natural follow-up questions)

**No dataset uploaded yet, user asks a data question**
`run_sql_query` hits DuckDB with no `dataset` table — the query throws, the
tool catches `duckdb.Error` and returns a message the LLM can relay
("no dataset loaded yet"). Worth explicitly testing this path — an
unhandled `Error` here would crash the tool call and show up as a broken
trace in LangSmith, which is actually a *good* way to demonstrate you
understand tool-level error handling: show the trace, show the fix.

**SQL injection / destructive queries from the LLM**
`run_sql_query` only allows strings starting with `SELECT` and blocks a
keyword blacklist. **Be upfront in the interview that this is a blunt
guard, not real security** — the correct production answer is a database
role with `SELECT`-only grants (or, since this is DuckDB, opening the
connection in `read_only=True` mode, which is what the code actually does
as the real enforcement — the keyword check is defense in depth, not the
primary control). This is a great "what would you do differently in
production" answer to have ready.

**Malformed/empty Excel upload**
Checked for empty dataframe; wrong extension is rejected before reading.
Not handled: a file with the right extension but garbage content (e.g. a
renamed `.txt`) — `pd.read_excel` would raise and the request would 500.
A production version wraps that in a try/except and returns a clean 400.

**Column name mismatches**
The upload endpoint lowercases and underscores column names so `Order
Date` becomes `order_date`, matching the docs. If someone uploads a sheet
with genuinely different column names (e.g. `revenue` instead of `sales`),
the agent's SQL will fail against the real schema — `create_chart`
explicitly validates requested columns against `DESCRIBE dataset` before
querying and returns a clear rejection; `run_sql_query` doesn't pre-validate
and will just surface DuckDB's own error, which is survivable since the
error propagates back to the LLM to retry or explain.

**Reranker/embedding latency**
The cross-encoder runs on CPU by default and loads into memory once at
server startup — fine for a portfolio demo, but on a low-memory box this
is worth watching. At scale you'd move this to a dedicated
reranking service or a GPU-backed inference endpoint (see scaling below).

**Empty RAG retrieval**
If `doc_chunks` is empty (ingestion never ran), `search_dataset_docs`
returns an explicit message rather than an empty string the LLM might
silently hallucinate around.

**Long conversations**
Handled explicitly by `condense_memory_node` — verify it actually works by
asking 5-6 follow-up questions and checking in LangSmith that a
`[Earlier conversation summary]` system message appears and the older raw
messages are gone from the trace.

**Concurrent uploads**
This project uses a single global `dataset.duckdb` file — a second upload
overwrites the first (`CREATE OR REPLACE TABLE`). Fine for one-user demo;
explicitly a multi-tenancy gap (see scaling).

## 4. How to scale this for real usage

**Multi-tenancy / many users at once**
Right now there's exactly one dataset (`dataset.duckdb`) and one doc
corpus, shared by everyone. To support many users:
- Key everything by a `dataset_id`/`user_id`: separate DuckDB files (or,
  better, migrate off DuckDB-as-shared-file to a real warehouse — see
  below) and a `dataset_id` column on `doc_chunks` filtered in every RAG
  query.
- `thread_id` already gives you per-conversation isolation for chat state —
  that part scales as-is.

**DuckDB at scale**
DuckDB is excellent for a single-node, single-writer analytical workload,
but it's not a concurrent multi-writer database. At real scale you'd swap
it for a proper warehouse (Snowflake, BigQuery, or a Postgres read
replica with the data loaded in) and keep the same tool interface —
`run_sql_query`'s contract to the agent doesn't need to change, just its
implementation.

**pgvector at scale**
The `ivfflat` index in `db/schema.sql` needs the `lists` parameter tuned to
row count (roughly `sqrt(row_count)`) once the corpus grows past a few
thousand chunks, or recall degrades. Beyond a few million vectors, most
teams move to a dedicated vector store (Pinecone, Qdrant, Weaviate) —
worth knowing pgvector's ceiling is a real thing, not just theoretical.

**Reranker throughput**
Running a cross-encoder synchronously in the tool call is fine at low QPS.
At higher load, batch multiple pending rerank requests together, or run
the reranker as its own horizontally-scaled service behind a queue.

**Stateless API pods**
Because all state (chat history, uploaded data reference, doc chunks) is
in Postgres/DuckDB rather than in-process memory, you can run multiple
FastAPI pods behind a load balancer with no sticky-session requirement —
any pod can serve any request as long as it has the `thread_id`. The one
exception in this exact codebase is the single shared `dataset.duckdb`
file, which doesn't horizontally scale until you externalize it as
described above.

**Cost control**
Embedding calls are cached implicitly by only running ingestion once, not
per-query. LLM calls are the main ongoing cost — worth mentioning
`gpt-4o-mini` was chosen deliberately over a larger model for this
workload, and that you'd track token spend per thread via LangSmith's
metadata.

**Large file uploads**
Currently synchronous — a huge Excel file blocks the request. At scale,
move upload processing to a background task/queue (Celery, or FastAPI's
`BackgroundTasks` for something lighter) and let the frontend poll a
status endpoint.

## 5. Questions an interviewer might actually ask

**"Why hierarchical chunking instead of just fixed-size chunks?"**
Fixed-size chunking can split a definition mid-sentence or separate a term
from its section context. Splitting by header first preserves that a
chunk about "delayed shipment" is understood as living under "Business
rules and definitions," which the reranker and LLM both benefit from
seeing in the chunk's context.

**"Why rerank instead of just retrieving more chunks (higher k)?"**
Embedding similarity is a cheap, approximate signal — it can rank a
topically-adjacent-but-wrong chunk above the truly relevant one,
especially with short/ambiguous queries. A cross-encoder reads the query
and chunk together and scores relevance directly, which is more accurate
but too slow to run over the whole corpus — hence two stages: cheap wide
net, then precise narrow cut.

**"Why DuckDB instead of just querying Postgres for the tabular data?"**
DuckDB is purpose-built for exactly this: fast, in-process analytical SQL
over a file/dataframe, no server to run, reads pandas/CSV/Excel-derived
data natively. Postgres is the right tool for durable transactional state
(chat checkpoints, RAG vectors) but is comparatively heavier for
ad-hoc analytical aggregation over a dataset that changes on every upload.

**"How do you keep the LLM from hallucinating a wrong SQL query?"**
The system prompt tells it to always ground numeric answers in an actual
`run_sql_query` call rather than estimating, and `create_chart` validates
columns against the real schema before running anything. It's not
foolproof — a good honest answer is that you'd add an eval (see the
notes-project's `eval/run_eval.py` pattern) checking that data questions
always produce a `run_sql_query` tool call in the trace, not just a
plausible-sounding text answer.

**"Walk me through what happens if two users ask about different datasets
at the same time."**
Today, they'd collide — one shared `dataset.duckdb`. This is the honest
gap to name proactively (see Scaling), and naming it unprompted is a much
stronger answer than waiting to be caught not having thought about it.

**"How would you evaluate whether the RAG retrieval itself is any good,
separate from the final answer?"**
Build a small labeled set of (question, expected section) pairs and check
whether `search_dataset_docs` returns a chunk from the expected section in
its top-k — a retrieval-level metric, independent of what the LLM does
with it afterward. This is a natural extension of the eval-dataset pattern
from LangSmith you'd already be using for end-to-end answer quality.

**"What's the difference between the memory summarization here and
checkpointing?"**
Checkpointing persists full state so a *crashed process* can resume
exactly where it left off — nothing is lost. Summarization is a
deliberate, lossy compression of *old conversation turns* so a *long-running
conversation* doesn't grow context/cost unboundedly — it's an intentional
tradeoff (older detail for lower cost), not a reliability mechanism.
