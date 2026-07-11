from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver
from graph import init_graph

DB_URL = (
    "postgresql://postgres:dilip123@localhost:5432/langchain?sslmode=disable"
)

def get_db():
    try:
        """Compile the graph with a Postgres-backed checkpointer.
        Call checkpointer.setup() once ever (creates the schema/tables)."""
        pool = ConnectionPool(conninfo=DB_URL, max_size=20, kwargs={"autocommit": True})
        checkpointer = PostgresSaver(pool)
        checkpointer.setup()  
        return init_graph().compile(checkpointer=checkpointer)

    finally:
        pool.close()