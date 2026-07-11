"""
Bypass the agent entirely and call search_dataset_docs directly against
the running MCP server. No LLM involved, no API tokens spent - this
tells us definitively whether the bug is in retrieval (embeddings/SQL)
or in the agent's tool-selection.

Usage:
    export MCP_SERVER_URL="http://localhost:9000/mcp"   # adjust if different
    python test_search_docs.py "explain the dataset"
"""
import asyncio
import os
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:9000/mcp")


async def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "explain the dataset"
    print(f"Connecting to {MCP_SERVER_URL} ...")
    async with streamablehttp_client(MCP_SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print(f"Calling search_dataset_docs(query={query!r}) ...\n")
            result = await session.call_tool(
                "search_dataset_docs", {"query": query, "top_k": 3}
            )
            print("--- RAW TOOL RESULT ---")
            print(result.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())