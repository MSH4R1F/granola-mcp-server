# Granola MCP Server

Read-only MCP server exposing Granola meetings via MCP tools. Supports both local file cache and remote API sources.

## Features

- ✅ **Local & Remote Sources**: Use local cache files or fetch directly from Granola API
- ✅ **Web Deployment Ready**: Deploy to browsers, edge functions, or serverless platforms
- ✅ **Intelligent Caching**: TTL-based caching with manual refresh support
- ✅ **Automatic Retries**: Built-in retry logic with exponential backoff
- ✅ **Zero Dependencies**: Stdlib-only core (optional FastMCP for MCP runtime)

## Quickstart

### Local Mode (Default)

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

### Remote Mode (Web Deployment)

Get up and running with remote mode in under 5 minutes!

#### Step 1: Get Your Token

Visit [Granola settings](https://granola.ai/settings) and copy your API token.

#### Step 2: Configure Environment

Create a `.env` file in your project root:

```bash
# Enable remote mode
GRANOLA_DOCUMENT_SOURCE=remote

# Add your token
GRANOLA_API_TOKEN=your_actual_token_here

# Optional: customize cache (defaults shown)
# GRANOLA_CACHE_TTL_SECONDS=86400  # 24 hours
# GRANOLA_CACHE_DIR=~/.granola/remote_cache
```

Or export environment variables:

```bash
export GRANOLA_DOCUMENT_SOURCE=remote
export GRANOLA_API_TOKEN=your_token_here
```

#### Step 3: Run the Server

```bash
granola-mcp
```

#### Verify It's Working

**Using the Example Script:**
```bash
python examples/remote_source_example.py
```

**Using MCP Inspector:**
```bash
npx @modelcontextprotocol/inspector
```
Then test the `granola.meetings.list` tool.

**Check Cache Status:**
Use the `granola.cache.status` tool to verify remote mode is active.

#### Common Configurations

```bash
# Remote mode with custom cache TTL (1 hour)
export GRANOLA_DOCUMENT_SOURCE=remote
export GRANOLA_API_TOKEN=your_token
export GRANOLA_CACHE_TTL_SECONDS=3600
granola-mcp
```

#### Troubleshooting

**Error: "API token is required"**  
→ Set the `GRANOLA_API_TOKEN` environment variable

**Error: "Invalid or expired token"**  
→ Get a fresh token from [Granola settings](https://granola.ai/settings)

**Documents not updating**  
→ Call the `granola.cache.refresh` tool or wait for cache TTL to expire

📖 **See [REMOTE_SOURCE_GUIDE.md](REMOTE_SOURCE_GUIDE.md) for comprehensive documentation on deployment scenarios, security, and advanced configuration.**

## Testing with MCP Inspector

The [MCP Inspector](https://github.com/modelcontextprotocol/inspector) is a visual testing tool that provides a web-based interface for interacting with MCP servers. It's perfect for testing and debugging your Granola MCP server.

### Installation

```bash
npx @modelcontextprotocol/inspector
```

### Usage

1. **Start your Granola MCP server:**
   ```bash
   granola-mcp
   ```

2. **Launch the Inspector:**
   ```bash
   npx @modelcontextprotocol/inspector
   ```

3. **Configure the connection:**
   - Open http://localhost:6274 in your browser
   - Set the transport to "STDIO"
   - Set the command to `granola-mcp`
   - Click "Connect"

### Inspector Features

- **Visual Tool Testing**: Test all available tools with a user-friendly interface
- **Resource Exploration**: Browse and read resources interactively
- **Real-time Debugging**: See request/response details and error messages
- **Configuration Management**: Save and load server configurations
- **CLI Mode**: Use the inspector programmatically for automation

### Configuration File

You can create a configuration file for easier setup:

```json
{
  "mcpServers": {
    "granola": {
      "command": "granola-mcp",
      "args": [],
      "env": {
        "GRANOLA_CACHE_PATH": "~/Library/Application Support/Granola/cache-v3.json",
        "GRANOLA_STDLIB_ONLY": "true",
        "GRANOLA_USE_SQLITE": "false"
      }
    }
  }
}
```

Then run:
```bash
npx @modelcontextprotocol/inspector --config path/to/config.json --server granola
```

For more information, visit the [MCP Inspector repository](https://github.com/modelcontextprotocol/inspector).

## Tools

### granola.conversations.list / granola.meetings.list
List meetings with optional filtering and pagination.

**Input Parameters:**
```json
{
  "q": "search query string",
  "from_ts": "2024-01-01T00:00:00Z",
  "to_ts": "2024-12-31T23:59:59Z",
  "participants": ["John Doe", "Jane Smith"],
  "limit": 50,
  "cursor": "pagination_cursor_string"
}
```

**Parameter Details:**
- `q` (optional): Search query string
- `from_ts` (optional): ISO 8601 timestamp for lower bound filtering
- `to_ts` (optional): ISO 8601 timestamp for upper bound filtering  
- `participants` (optional): List of participant names to filter by
- `limit` (optional): Number of results to return (1-500, default: 50)
- `cursor` (optional): Pagination cursor for next page

**Returns:** List of meeting summaries with optional next_cursor for pagination

### granola.conversations.get / granola.meetings.get
Get detailed information about a specific meeting.

**Input Parameters:**
```json
{
  "id": "meeting_identifier_123",
  "include": ["notes", "metadata"]
}
```

**Parameter Details:**
- `id` (required): Meeting identifier
- `include` (optional): List of fields to include (`["notes", "metadata"]`)

**Returns:** Full meeting record with notes, overview, summary, and metadata

### granola.meetings.search
Search meetings with text query and advanced filtering.

**Input Parameters:**
```json
{
  "q": "search query string",
  "filters": {
    "participants": ["John Doe", "Jane Smith"],
    "platform": "zoom",
    "before": "2024-12-31T23:59:59Z",
    "after": "2024-01-01T00:00:00Z"
  },
  "limit": 50,
  "cursor": "pagination_cursor_string"
}
```

**Parameter Details:**
- `q` (required): Search query string
- `filters` (optional): Advanced filters object containing:
  - `participants` (optional): List of participant names
  - `platform` (optional): Platform filter (`"zoom"`, `"meet"`, `"teams"`, `"other"`)
  - `before` (optional): ISO 8601 timestamp for upper bound
  - `after` (optional): ISO 8601 timestamp for lower bound
- `limit` (optional): Number of results (1-500, default: 50)
- `cursor` (optional): Pagination cursor

**Returns:** List of matching meeting summaries with pagination

### granola.meetings.export_markdown
Export a meeting to markdown format.

**Input Parameters:**
```json
{
  "id": "meeting_identifier_123",
  "sections": ["header", "notes", "attendees", "links"]
}
```

**Parameter Details:**
- `id` (required): Meeting identifier
- `sections` (optional): List of sections to include (`["header", "notes", "attendees", "links"]`)

**Returns:** Markdown-formatted meeting content

### granola.meetings.stats
Get meeting statistics and analytics.

**Input Parameters:**
```json
{
  "window": "30d",
  "group_by": "day"
}
```

**Parameter Details:**
- `window` (optional): Time window (`"7d"`, `"30d"`, `"90d"`)
- `group_by` (optional): Grouping period (`"day"`, `"week"`)

**Returns:** Statistics including meeting counts by period and participant data

### granola.cache.status
Get information about the cache (local or remote).

**Input Parameters:**
```json
{}
```

**Returns:** Cache information including path, size, last loaded timestamp, and profile type

### granola.cache.refresh
Manually refresh the cache, bypassing TTL (useful for remote mode).

**Input Parameters:**
```json
{}
```

**Returns:** Refresh status, message, meeting count, and cache information

## Development

Run tests:

```bash
pytest -q
```

Format:

```bash
black . && isort .
```
