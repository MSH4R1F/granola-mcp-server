# Granola MCP Server

Local-first, read-only MCP server exposing Granola meetings via MCP tools.

## Quickstart

1. Install (dev):

```bash
pip install -e .[dev,mcp]
```

2. Run server:

```bash
granola-mcp
```

3. Environment vars (defaults shown):

```bash
export GRANOLA_CACHE_PATH="~/Library/Application Support/Granola/cache-v3.json"
export GRANOLA_STDLIB_ONLY=true
export GRANOLA_USE_SQLITE=false
```

## Tools

- granola.conversations.list / granola.meetings.list
- granola.conversations.get / granola.meetings.get
- granola.meetings.search
- granola.meetings.export_markdown
- granola.meetings.stats
- granola.cache.status

## Development

Run tests:

```bash
pytest -q
```

Format:

```bash
black . && isort .
```
