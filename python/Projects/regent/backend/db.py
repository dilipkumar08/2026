from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver
from graph import init_graph

DB_URL = (
    "postgresql://postgres:postgres@localhost:5432/langchain?sslmode=disable"
)

# The pool and compiled app are kept alive for the lifetime of the process.
# (The original version closed the pool in a `finally` block right after
# creating it, which killed the connections the checkpointer needed on
# every later call.)
_pool = None
_app = None


def get_db():
    """Compile the graph with a Postgres-backed checkpointer.

    Safe to call repeatedly - the pool/app are created once and reused.
    """
    global _pool, _app
    if _app is not None:
        return _app

    _pool = ConnectionPool(conninfo=DB_URL, max_size=20, kwargs={"autocommit": True})
    checkpointer = PostgresSaver(_pool)
    checkpointer.setup()

    _app = init_graph().compile(checkpointer=checkpointer)
    return _app


def close_db():
    """Call this on app shutdown to release the connection pool."""
    global _pool, _app
    if _pool is not None:
        _pool.close()
    _pool = None
    _app = None
