import json
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
import duckdb
import pandas as pd
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from mcp import ClientSession
# FIX: the real function name in the mcp package is "streamablehttp_client"
# (no underscore between "streamable" and "http"). The previous import name
# "streamable_http_client" does not exist and raises ImportError, which
# would have crashed the whole app at startup before any request could
# even be handled.
from mcp.client.streamable_http import streamablehttp_client
from langsmith import Client as LangSmithClient
from agent.graph import load_mcp_tools, build_graph, AGENT_DB_URI, MCP_SERVER_URL
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

langsmith_client = LangSmithClient()

DUCKDB_PATH = os.environ.get("DUCKDB_PATH", "./dataset.duckdb")
EXPORT_DIR = Path(os.environ.get("EXPORT_DIR", "./exports"))


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None


class FeedbackRequest(BaseModel):
    run_id: str
    score: int
    comment: str | None = None


class ChartRequest(BaseModel):
    chart_type: str
    x_column: str
    y_column: str
    agg: str = "sum"


class ExportRequest(BaseModel):
    title: str
    summary_text: str


async def call_mcp_tool(tool_name: str, arguments: dict) -> str:
    """A direct MCP client call, bypassing the LangGraph agent entirely.
    This is the API acting as its OWN MCP client — a third client on top
    of the LangGraph agent and client_demo.py — used here for actions that
    should be deterministic (a chart button click) rather than left to the
    LLM's discretion (a chat question)."""
    async with streamablehttp_client(MCP_SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            return result.content[0].text


@asynccontextmanager
async def lifespan(app: FastAPI):
    tools = await load_mcp_tools()
    graph = build_graph(tools)
    pool = AsyncConnectionPool(conninfo=AGENT_DB_URI, max_size=20, kwargs={"autocommit": True})
    await pool.open()
    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()
    app.state.compiled_graph = graph.compile(checkpointer=checkpointer)
    app.state.pool = pool
    yield
    await pool.close()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="api/templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "api_url": "http://localhost:8000",
            "frontend_url": "http://localhost:4200",
        },
    )


@app.post("/upload")
async def upload_dataset(file: UploadFile = File(...)):
    """Load an uploaded Excel file into DuckDB as the `dataset` table.
    Opens a short-lived read-write connection, writes, and closes
    immediately — so the MCP server's read-only connections (which open
    fresh per query) never collide with this write."""
    if not file.filename.endswith((".xlsx", ".xls")):
        return {"error": "Only .xlsx/.xls files are supported."}

    df = pd.read_excel(file.file)
    if df.empty:
        return {"error": "The uploaded file has no rows."}

    # Normalize column names: lowercase, spaces -> underscores, so the
    # agent's SQL (which uses names like order_date) matches regardless of
    # how the source spreadsheet capitalized its headers.
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    conn = duckdb.connect(DUCKDB_PATH, read_only=False)
    conn.execute("CREATE OR REPLACE TABLE dataset AS SELECT * FROM df")
    row_count = conn.execute("SELECT COUNT(*) FROM dataset").fetchone()[0]
    columns = [r[0] for r in conn.execute("DESCRIBE dataset").fetchall()]
    conn.close()

    return {"status": "loaded", "rows": row_count, "columns": columns}


@app.get("/columns")
async def get_columns():
    """List the uploaded dataset's columns, for the frontend's chart dropdowns."""
    conn = duckdb.connect(DUCKDB_PATH, read_only=True)
    columns = [r[0] for r in conn.execute("DESCRIBE dataset").fetchall()]
    conn.close()
    return {"columns": columns}


@app.post("/chart")
async def chart(req: ChartRequest):
    """Deterministic chart generation — calls the create_chart MCP tool
    directly with the exact columns the user picked, no LLM in the loop."""
    text = await call_mcp_tool(
        "create_chart",
        {
            "chart_type": req.chart_type,
            "x_column": req.x_column,
            "y_column": req.y_column,
            "agg": req.agg,
        },
    )
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # The tool returned a plain-text rejection/error, not chart JSON
        # (e.g. "Rejected: columns must be one of [...]").
        return {"error": text}


@app.post("/export")
async def create_export(req: ExportRequest):
    """Deterministic doc export — calls export_summary_doc directly."""
    filename = await call_mcp_tool(
        "export_summary_doc", {"title": req.title, "summary_text": req.summary_text}
    )
    return {"filename": filename, "download_url": f"/export/{filename}"}


@app.post("/chat")
async def chat(req: ChatRequest):
    thread_id = req.thread_id or str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    config = {
        "configurable": {"thread_id": thread_id},
        "run_id": run_id,
        "run_name": "data-insights-turn",
        "tags": [f"thread:{thread_id}"],
        "metadata": {"thread_id": thread_id},
    }
    try:
        result = await app.state.compiled_graph.ainvoke(
            {"messages": [HumanMessage(content=req.message)]}, config=config
        )
    except Exception as exc:
        # FIX: without this, an agent-side exception (e.g. a model that
        # doesn't support tool calling) crashes past CORSMiddleware entirely,
        # so the browser can't even read the error — it just reports a bare
        # "status 0" network failure. Catching here returns a normal JSON
        # response with the real error message instead.
        return {
            "response": f"Agent error: {exc}",
            "thread_id": thread_id,
            "run_id": run_id,
        }

    return {
        "response": result["messages"][-1].content,
        "thread_id": thread_id,
        "run_id": run_id,
    }


@app.post("/feedback")
async def feedback(req: FeedbackRequest):
    # Guarded the same way /chat guards the graph call: if LangSmith
    # tracing isn't enabled (no LANGSMITH_API_KEY / LANGSMITH_TRACING) or
    # the run_id doesn't correspond to a real trace, create_feedback raises
    # - without this it would crash past CORSMiddleware just like the
    # agent exception case in /chat did before that fix.
    try:
        langsmith_client.create_feedback(
            run_id=req.run_id, key="user_score", score=req.score, comment=req.comment
        )
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}
    return {"status": "recorded"}


@app.get("/export/{filename}")
async def download_export(filename: str):
    """Serve a previously exported .docx. Path is constrained to EXPORT_DIR
    and the filename is re-sanitized here too — defense in depth on top of
    the sanitization already done in the MCP tool itself."""
    safe_filename = Path(filename).name  # strips any path traversal attempt
    file_path = EXPORT_DIR / safe_filename
    if not file_path.exists():
        return {"error": "File not found."}
    return FileResponse(file_path, filename=safe_filename)


@app.get("/health")
async def health():
    return {"status": "ok"}