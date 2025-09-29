"""MCP tools for listing, retrieving, searching, exporting, and stats.

Each tool is exposed as a plain Python function to facilitate testing.
An MCP runtime adapter (see `server.py`) registers these with the
FastMCP runtime. The tool functions return Pydantic models.
"""

from .meetings import (
    export_markdown,
    get_meeting,
    list_meetings,
    meetings_stats,
    search_meetings,
)
from .status import cache_status

__all__ = [
    "list_meetings",
    "get_meeting",
    "search_meetings",
    "export_markdown",
    "meetings_stats",
    "cache_status",
]
