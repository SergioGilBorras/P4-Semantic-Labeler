"""Official Python MCP SDK, stdio transport. Install package with [mcp] extra."""

from __future__ import annotations

from p4_semantic_labeler.config import Settings
from p4_semantic_labeler.core.service import Labeler
from p4_semantic_labeler.interfaces.mcp_tools import MCPTools


def create_mcp_server(settings: Settings | None = None, labeler: Labeler | None = None):
    try:
        from mcp.server import MCPServer
    except ImportError as exc:
        raise RuntimeError("Install the MCP extra: pip install '.[mcp]'") from exc
    settings = settings or Settings.from_env()
    handlers = MCPTools(labeler or Labeler(settings=settings), settings)
    mcp = MCPServer("P4-Semantic-Labeler")
    mcp.tool(name="generate_label")(handlers.generate_label)
    mcp.tool(name="generate_summary")(handlers.generate_summary)
    mcp.tool(name="generate_labels_batch")(handlers.generate_labels_batch)
    mcp.tool(name="summarize_file")(handlers.summarize_file)
    return mcp


def main() -> None:
    create_mcp_server().run(transport="stdio")


if __name__ == "__main__":
    main()
