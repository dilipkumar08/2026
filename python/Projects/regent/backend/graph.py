from langgraph.graph import StateGraph, START, END
from state import  agentState
from node import *


def check_finalize(state:agentState)->str:
    if state.get("iterations",0)>3 or "no"==state["critique"].get("sufficient","no").lower():
        return "not enough"
    else:
        return "enough"

def human_approval(state:agentState)->str:
    if state.get("approved",False)==True:
        return "finalize"
    else:
        return "search"
    
def init_graph():
    graph=StateGraph(agentState)

    graph.add_node("search",search_node)
    graph.add_node("draft",draft_node)
    graph.add_node("critique",critique_node)
    graph.add_node("finalize",finalize_node)
    graph.add_node("human",human_node)

    graph.add_edge(START,"search")
    graph.add_edge("search","draft")
    graph.add_edge("draft","critique")
    graph.add_conditional_edges("critique",check_finalize,{"enough":"human","not enough":"search"})
    graph.add_conditional_edges("human",human_approval,{"finalize":"finalize","search":"search"})
    graph.add_edge("finalize",END)

    return graph

