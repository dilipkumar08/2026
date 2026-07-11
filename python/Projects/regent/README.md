# Research Desk

A human-in-the-loop research agent (search → draft → critique → review → finalize),
with a FastAPI layer over your existing LangGraph app and a clean Angular UI on top.

Your original code was a CLI script (`main.py`) that talked to the graph directly —
there was no HTTP API for a frontend to call. I added one (`backend/api.py`) rather
than reinvent the pipeline, and fixed a few bugs I hit along the way (details below).

## What's in here

```
backend/
  db.py         # fixed: connection pool no longer closes itself right after opening
  graph.py      # unchanged
  llm.py        # unchanged
  node.py       # fixed: critique prompt + a text-slicing bug (see below)
  state.py      # unchanged
  main.py       # fixed: the CLI script's undefined-variable bug
  api.py        # NEW: FastAPI wrapper exposing the graph over HTTP
  requirements.txt
frontend/
  (Angular app — start form, pipeline rail, review screen, decision controls)
```

## Bugs fixed

1. **`db.py`** — `pool.close()` was in a `finally` block, so it ran immediately after
   the pool was created (right as the function returned), closing the connections the
   checkpointer needs for every later call. The pool now stays open for the process
   lifetime; call `close_db()` on shutdown instead.
2. **`node.py` → `critique_node`** — the instruction lines ("Reply in this exact
   format...") were written as separate string literals, not appended to `prompt`, so
   the LLM never actually saw the format instructions. Also, `result[missing_start:-1]`
   chopped the last character off the "missing" text — changed to `result[missing_start:]`.
3. **`main.py`** — `Command(resume=S)` referenced an undefined variable `S` instead of
   the `decision` dict built two lines above.

## Running it

### 1. Backend

You'll need Postgres running locally (matching the `DB_URL` in `db.py`) and Ollama
running with the `gemma2:2b` model pulled (per `llm.py`).

```bash
cd backend
pip install -r requirements.txt
uvicorn api:app --reload --port 8000
```

This starts the API at `http://localhost:8000`. Endpoints:

- `POST /api/sessions` `{ query }` → starts a new session, runs it until the first
  human-review pause (or completion), returns the state.
- `GET /api/sessions/{thread_id}` → fetch a session's current saved state.
- `POST /api/sessions/{thread_id}/resume` → resume a session from its last checkpoint.
- `POST /api/sessions/{thread_id}/decision` `{ action: "approve" | "revise", feedback }`
  → send the human's decision and continue the graph.

### 2. Frontend

```bash
cd frontend
npm install
npm start
```

Open `http://localhost:4200`. The app is pre-configured to call the API at
`http://localhost:8000/api` (see `src/app/services/agent.service.ts` if you need to
change that).

## Using the UI

1. **New question** — type a research question and submit. The agent searches,
   drafts, and critiques its own answer, then pauses for your review.
2. **Review screen** — shows the current draft, a sufficient/needs-more-support
   badge, the iteration count, and (if flagged) what the critique thinks is missing.
   Approve to finalize, or send it back with feedback for another pass.
3. **Resume a session** — paste a thread ID from an earlier run to pick up exactly
   where you left off, thanks to the Postgres checkpointer.
4. **Final screen** — shows the finished answer and a button to start a new question.

The left-hand rail tracks progress through the pipeline (Search → Draft → Critique →
Review → Final) so it's always clear where a session stands.
