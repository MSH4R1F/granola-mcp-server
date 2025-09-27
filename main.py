from mcp.server.fastmcp import FastMCP
from pydantic import Field
import dotenv
import os

dotenv.load_dotenv()

MCP_HOST = os.getenv("MCP_HOST")
MCP_PORT = os.getenv("MCP_PORT")


mcp = FastMCP(
    name = "Granola MCP Server",
    host = MCP_HOST,
    port = MCP_PORT,
    stateless_http=True
)
print(f"Granola MCP Server is running on {MCP_HOST}:{MCP_PORT}")


@mcp.tool(title="Welcome a user",
    description="Return a friendly welcome message for the user.",
)
def welcome_user(name: str) -> str:
    return f"Welcome {name} to the Granola MCP Server!"


if __name__ == "__main__":
    mcp.run(transport="stdio")
