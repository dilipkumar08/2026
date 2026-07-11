import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langgraph.types import Command

from db import get_db, close_db

app = FastAPI(title="Research Agent API")

# Allow the local Angular dev server to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_graph = None


def graph():
    global _graph
    if _graph is None:
        _graph = get_db()
    return _graph


@app.on_event("shutdown")
def shutdown():
    close_db()


class NewSessionRequest(BaseModel):
    query: str


class DecisionRequest(BaseModel):
    action: str  # "approve" | "revise"
    feedback: Optional[str] = ""


def _format(thread_id: str, result: dict) -> dict:
    if "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        return {
            "thread_id": thread_id,
            "status": "paused",
            "draft": payload["draft"],
            "critique": payload["critique"],
            "iterations": payload["iterations"],
        }
    return {
        "thread_id": thread_id,
        "status": "done",
        "draft": result["draft"],
        "critique": result.get("critique", {}),
        "iterations": result.get("iterations", 0),
    }


@app.post("/api/sessions")
def create_session(req: NewSessionRequest):
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    result = graph().invoke(
        {
            "query": req.query,
            "iterations": 0,
            "search_results": [],
            "draft": "",
            "critique": {},
            "approved": False,
        },
        config=config,
    )
    return _format(thread_id, result)


@app.get("/api/sessions/{thread_id}")
def get_session(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    state = graph().get_state(config)
    if not state.values:
        raise HTTPException(status_code=404, detail="No saved session with that id.")
    values = state.values
    return {
        "thread_id": thread_id,
        "status": "paused" if state.next else "done",
        "query": values.get("query", ""),
        "draft": values.get("draft", ""),
        "critique": values.get("critique", {}),
        "iterations": values.get("iterations", 0),
    }


@app.post("/api/sessions/{thread_id}/resume")
def resume_session(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    existing = graph().get_state(config)
    if not existing.values:
        raise HTTPException(status_code=404, detail="No saved session with that id.")
    result = graph().invoke(None, config=config)
    return _format(thread_id, result)


@app.post("/api/sessions/{thread_id}/decision")
def decide(thread_id: str, req: DecisionRequest):
    config = {"configurable": {"thread_id": thread_id}}
    existing = graph().get_state(config)
    if not existing.values:
        raise HTTPException(status_code=404, detail="No saved session with that id.")

    if req.action == "approve":
        decision = {"action": "approve"}
    else:
        decision = {"action": "revise", "feedback": req.feedback or ""}

    result = graph().invoke(Command(resume=decision), config=config)
    return _format(thread_id, result)
