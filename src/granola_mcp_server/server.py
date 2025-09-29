"""FastMCP server entrypoint.

Registers tools for the Granola MCP Server. This module intentionally
keeps the tool implementations decoupled so they can be unit-tested
without the runtime.

Note: We import FastMCP lazily to keep stdlib-only profile lightweight
until the MCP runtime is actually used.
"""

from __future__ import annotations

import sys
from typing import Optional

from .config import load_config
from .parser import GranolaParser
from .schemas import (
    CacheStatusOutput,
    ExportMarkdownInput,
    ExportMarkdownOutput,
    GetMeetingInput,
    GetMeetingOutput,
    ListMeetingsInput,
    ListMeetingsOutput,
    SearchMeetingsInput,
    SearchMeetingsOutput,
    StatsInput,
    StatsOutput,
)
from .tools import (
    cache_status,
    export_markdown,
    get_meeting,
    list_meetings,
    meetings_stats,
    search_meetings,
)


def _register_fastmcp_tools(app, config, parser):
    # Namespace: granola.*

    @app.tool("granola.conversations.list")
    @app.tool("granola.meetings.list")
    def meetings_list(params: ListMeetingsInput) -> ListMeetingsOutput:
        return list_meetings(config, parser, params)

    @app.tool("granola.conversations.get")
    @app.tool("granola.meetings.get")
    def meetings_get(params: GetMeetingInput) -> GetMeetingOutput:
        return get_meeting(config, parser, params)

    @app.tool("granola.meetings.search")
    def meetings_search(params: SearchMeetingsInput) -> SearchMeetingsOutput:
        return search_meetings(config, parser, params)

    @app.tool("granola.meetings.export_markdown")
    def meetings_export_md(params: ExportMarkdownInput) -> ExportMarkdownOutput:
        return export_markdown(config, parser, params)

    @app.tool("granola.meetings.stats")
    def meetings_stats_tool(params: StatsInput) -> StatsOutput:
        return meetings_stats(config, parser, params)

    @app.tool("granola.cache.status")
    def cache_status_tool() -> CacheStatusOutput:
        return cache_status(config, parser)


def main(argv: Optional[list[str]] = None) -> None:
    """Run the FastMCP application.

    This function loads configuration, creates a parser instance, and
    registers all tools with the FastMCP runtime. It is safe to import
    and call `main()` from other entrypoints.
    """

    argv = argv if argv is not None else sys.argv[1:]
    config = load_config()
    parser = GranolaParser(config.cache_path)

    try:
        from fastmcp import FastMCP
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "fastmcp is not installed. Install with 'pip install granola-mcp-server[mcp]'"
        ) from exc

    app = FastMCP("granola-mcp-server")
    _register_fastmcp_tools(app, config, parser)

    # Run the FastMCP app (serves until interrupted)
    app.run()


if __name__ == "__main__":  # pragma: no cover
    main()
