import os
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, END
from langgraph.graph.message import RemoveMessage
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from agent.state import AgentState

AGENT_DB_URI = os.environ.get(
    "AGENT_DB_URI",
    "postgresql://postgres:postgres@localhost:5432/postgres?sslmode=disable",
)

MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:9000/mcp")

# Served through Groq's OpenAI-compatible inference API, so a plain
# ChatOpenAI client pointed at that base_url is all we need - no Groq-
# specific client, no local weights.
#
# Model choice matters here: this must be a model Groq serves with real
# native tool-calling (the OpenAI-style "tools" request param), not just
# a model that can be prompted into writing JSON. llama-3.3-70b-versatile
# is being deprecated by Groq and its tool-calling has always been
# unreliable (it will often just print the tool call as text instead of
# actually invoking it) - openai/gpt-oss-20b is one of Groq's current
# production models with solid native tool support and a lighter/cheaper
# footprint that's kinder to free-tier rate limits. Swap to
# openai/gpt-oss-120b if you want more reasoning power and have the quota.
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# The system prompt lives in its own text file instead of being inlined
# here, so it can be edited/reviewed without touching code.
SYSTEM_PROMPT_PATH = Path(
    os.environ.get("SYSTEM_PROMPT_PATH", Path(__file__).parent / "prompts" / "system_prompt.txt")
)


def _load_base_system_prompt() -> str:
    try:
        return SYSTEM_PROMPT_PATH.read_text().strip()
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"System prompt file not found at {SYSTEM_PROMPT_PATH} - set "
            "SYSTEM_PROMPT_PATH or make sure agent/prompts/system_prompt.txt "
            "exists."
        ) from exc


BASE_SYSTEM_PROMPT = _load_base_system_prompt()

SUMMARY_THRESHOLD = 8
KEEP_RECENT = 4

# Small/free-tier models are inconsistent about actually calling
# search_dataset_docs for a general "what is this dataset" style question
# vs. just reciting the Rule 5 fallback line from the system prompt as if
# a search had already happened and come up empty. Rather than depend on
# the model's judgment for this one common, easily-recognized case, force
# the tool call deterministically - same philosophy as the /chart and
# /export routes in main.py bypassing the LLM for actions that should be
# reliable rather than left to discretion. The system prompt's Rule 0
# still covers phrasings this regex doesn't catch.
OVERVIEW_TRIGGER = re.compile(
    r"\b(explain|describe|tell me about|overview|summarize|summarise|review|what is)\b.*\bdataset\b",
    re.IGNORECASE,
)


async def load_mcp_tools():
    client = MultiServerMCPClient(
        {"data-insights": {"url": MCP_SERVER_URL, "transport": "streamable_http"}}
    )
    return await client.get_tools()


def _build_llm() -> ChatOpenAI:
    """Chat model via Groq's OpenAI-compatible inference API.

    Kept at temperature=0, same as the original Ollama/HF setup - low
    temperature makes the model's tool-call JSON more consistent, which
    matters more here than creative variation in the final answer.
    """
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set - required to call Groq's inference "
            "API. Get a free key at https://console.groq.com/keys and:\n"
            '  export GROQ_API_KEY="gsk_..."'
        )
    if not GROQ_MODEL:
        raise RuntimeError(
            "GROQ_MODEL resolved to empty/None - check that the GROQ_MODEL "
            "env var (if set) contains a valid model id, e.g.:\n"
            '  export GROQ_MODEL="openai/gpt-oss-20b"'
        )
    return ChatOpenAI(
        model=GROQ_MODEL,
        base_url=GROQ_BASE_URL,
        api_key=GROQ_API_KEY,
        temperature=0,
    )


def build_graph(tools):
    llm = _build_llm()
    # Native tool binding: the model receives real JSON-schema tool
    # definitions via the API's "tools" param and returns proper
    # tool_calls on the AIMessage - no hand-written prompt instructions
    # or regex parsing needed, and no risk of the model just describing
    # the call in prose instead of invoking it.
    llm_with_tools = llm.bind_tools(tools)

    def agent_node(state: AgentState) -> dict:
        history = state["messages"]

        last_human_idx = max(
            (i for i, m in enumerate(history) if isinstance(m, HumanMessage)), default=None
        )

        if last_human_idx is not None:
            last_human = history[last_human_idx]
            already_searched_this_turn = any(
                isinstance(m, ToolMessage) and getattr(m, "name", None) == "search_dataset_docs"
                for m in history[last_human_idx + 1 :]
            )
            if not already_searched_this_turn and OVERVIEW_TRIGGER.search(last_human.content):
                return {
                    "messages": [
                        AIMessage(
                            content="",
                            tool_calls=[
                                {
                                    "name": "search_dataset_docs",
                                    "args": {"query": "dataset overview", "top_k": 5},
                                    "id": f"call_{uuid.uuid4().hex[:8]}",
                                    "type": "tool_call",
                                }
                            ],
                        )
                    ]
                }

        messages = [SystemMessage(content=BASE_SYSTEM_PROMPT)] + history
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def condense_memory_node(state: AgentState) -> dict:
        messages = state["messages"]
        if len(messages) <= SUMMARY_THRESHOLD:
            return {}

        to_summarize = messages[:-KEEP_RECENT]
        to_keep = messages[-KEEP_RECENT:]

        def _line(m) -> str | None:
            if getattr(m, "tool_calls", None):
                calls = ", ".join(f"{tc['name']}({tc['args']})" for tc in m.tool_calls)
                return f"{m.type}: [called tool] {calls}"
            if m.content:
                return f"{m.type}: {m.content}"
            return None

        transcript = "\n".join(line for m in to_summarize if (line := _line(m)))
        summary = llm.invoke(
            "Summarize this conversation in 2-3 sentences. Keep any concrete "
            f"numbers, filters, or column names mentioned:\n\n{transcript}"
        ).content

        removals = [RemoveMessage(id=m.id) for m in messages if m.id]
        summary_message = SystemMessage(content=f"[Earlier conversation summary]: {summary}")
        kept_copies = [m.model_copy(update={"id": str(uuid.uuid4())}) for m in to_keep]

        return {"messages": removals + [summary_message] + kept_copies}

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tools))
    graph.add_node("condense_memory", condense_memory_node)

    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: "condense_memory"})
    graph.add_edge("tools", "agent")
    graph.add_edge("condense_memory", END)

    return graph


@asynccontextmanager
async def get_compiled_app():
    tools = await load_mcp_tools()
    graph = build_graph(tools)
    async with AsyncConnectionPool(
        conninfo=AGENT_DB_URI, max_size=20, kwargs={"autocommit": True}
    ) as pool:
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()
        yield graph.compile(checkpointer=checkpointer)


async def _cli():
    async with get_compiled_app() as app:
        thread_id = str(uuid.uuid4())
        print(f"New session: {thread_id}  (type 'exit' to quit)")
        config = {
            "configurable": {"thread_id": thread_id},
            "run_name": "data-insights-turn",
            "tags": [f"thread:{thread_id}"],
        }

        while True:
            user_input = input("\nyou: ").strip()
            if user_input.lower() == "exit":
                break
            result = await app.ainvoke(
                {"messages": [HumanMessage(content=user_input)]}, config=config
            )
            print("agent:", result["messages"][-1].content)


if __name__ == "__main__":
    import asyncio
    asyncio.run(_cli())