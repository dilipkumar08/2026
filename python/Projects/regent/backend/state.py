from typing import TypedDict, Annotated
from operator import add

class Critique(TypedDict):
    sufficient: str
    missing: str


class agentState(TypedDict):
    query: str
    search_results: Annotated[list[str], add]
    draft: str
    critique: Critique
    iterations: int
    approved: bool

