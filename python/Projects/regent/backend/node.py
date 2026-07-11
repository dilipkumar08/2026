from state import agentState
from langchain_community.tools import DuckDuckGoSearchRun
from langgraph.types import interrupt
from llm import llm


def search_node(state: agentState) -> dict:
    search = DuckDuckGoSearchRun()
    if state["critique"].get("sufficient", "no").lower() == "no":
        search_query = state["critique"].get("missing", False) or state["query"]
    else:
        search_query = state["query"]
    result = search.invoke(search_query)
    return {"search_results": [result]}


def draft_node(state: agentState) -> dict:
    context = "\n".join(state["search_results"])
    prompt = (
        f"Question: {state['query']}\n\n"
        f"Research notes: {context}\n"
        "your role: write a clear, well supported summarized answer using only the notes above"
    )
    response = llm.invoke(prompt).content
    return {"draft": response}


def critique_node(state: agentState) -> dict:
    # NOTE: the original version built these instruction lines as separate,
    # unused string literals instead of appending them to `prompt`, so the
    # LLM never actually saw the required output format. Fixed below.
    prompt = (
        f"question:{state['query']}\n"
        f"Draft answer:{state['draft']}\n\n"
        "Is this draft complete and well-supported? Reply in this exact format below, "
        "do not change the format or add anything extra:\n"
        "sufficient: yes/no\n"
        "missing: missing points in the draft (or 'none')"
    )

    result = llm.invoke(prompt).content

    if "sufficient: no" in result.lower():
        missing_start = result.lower().index("missing")
        sufficient = "no"
        # NOTE: original did result[missing_start:-1], which chopped off
        # the last character of the response. Fixed to keep the full tail.
        missing = result[missing_start:].strip()
    else:
        sufficient = "yes"
        missing = ""

    return {
        "critique": {"sufficient": sufficient, "missing": missing},
        "iterations": state["iterations"] + 1,
    }


def human_node(state: agentState) -> dict:
    approval = interrupt(
        {
            "draft": state["draft"],
            "critique": state["critique"],
            "iterations": state["iterations"],
            "provide this to user as instructions as it is": (
                "Respond with {'action':'approve'} to finalize or "
                "{'action': 'revise','feedback':'your feedback'} to reiterate"
            ),
        }
    )
    if approval.get("action", "").lower() == "approve":
        return {"approved": True}
    else:
        return {
            "approved": False,
            "critique": {
                "sufficient": "no",
                "missing": state["critique"].get("missing", "") + " " + approval.get("feedback", ""),
            },
        }


def finalize_node(state: agentState) -> dict:
    return {"draft": f"FINAL ANSWER:\n{state['draft']}"}
