"""Granola MCP Server package.

This package provides a local-first, read-only MCP server exposing
Granola meetings via a set of tools. The default profile uses only the
Python standard library to parse a double-encoded JSON cache file.

Profiles:
- Stdlib-only (default): no external services.
- Optional SQLite+FTS (future): indexing for faster search.

Usage example:
    from granola_mcp_server.server import main
    if __name__ == "__main__":
        main()

Note: Tools can also be imported and registered by an external MCP runtime.
"""

__all__ = [
    "__version__",
]

__version__ = "0.1.0"
