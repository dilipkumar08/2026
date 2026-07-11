from db import get_db
import uuid
from langgraph.types import Command


def run():
    app = get_db()

    raw_thread_id = input("Thread id to RESUME (leave blank to start a NEW session): ").strip()

    if raw_thread_id:
        thread_id = raw_thread_id
        config = {"configurable": {"thread_id": thread_id}}
        existing_state = app.get_state(config)

        if not existing_state.values:
            print(f"No saved state found for thread_id '{thread_id}'. Nothing to resume.")
            return

        print(f"\nResuming thread '{thread_id}' from its last checkpoint.")
        result = app.invoke(None, config=config)
    else:
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        print(f"\nStarting a new session. Save this thread_id to resume later: {thread_id}")

        query = input("Research question: ").strip()
        result = app.invoke(
            {"query": query, "iterations": 0, "search_results": [],
             "draft": "", "critique": {}, "approved": False},
            config=config,
        )

    # Handle interrupt loop (may need several rounds of revise -> re-review)
    while "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        print("\n--- PAUSED FOR HUMAN REVIEW ---")
        print("Draft:", payload["draft"])
        print("Critique:", payload["critique"])
        print("Iterations so far:", payload["iterations"])

        raw = input("\nType 'approve' or 'revise: <feedback>': ").strip()
        if raw.lower().startswith("approve"):
            decision = {"action": "approve"}
        else:
            decision = {"action": "revise", "feedback": raw.split(":", 1)[-1].strip()}

        # NOTE: original code called Command(resume=S) where `S` was never
        # defined. It should resume with the decision dict just built above.
        result = app.invoke(Command(resume=decision), config=config)

    print("\n--- DONE ---")
    print(result["draft"])


if __name__ == "__main__":
    run()
