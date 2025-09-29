# Changelog

All notable changes to the Granola MCP Server project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-09-29

### Added - Remote Document Source Feature

**Major new feature enabling web deployment and API-backed document fetching!**

#### Core Features
- **Remote Document Source**: New `RemoteApiDocumentSource` that fetches documents directly from Granola API
- **Document Source Abstraction**: Pluggable interface supporting both local and remote sources
- **Intelligent Caching**: TTL-based caching (24h default) with automatic expiry and refresh
- **Manual Refresh Tool**: New `granola.cache.refresh` tool for on-demand cache updates
- **Error Handling**: Comprehensive handling for 401/403/429/5xx with exponential backoff retry

#### New Components
- `document_source.py` - Abstract `DocumentSource` interface
- `sources/local_file.py` - Local file implementation (wraps existing parser)
- `sources/remote_api.py` - Remote API implementation with gzip decompression
- `sources/adapter.py` - Adapter bridging document sources to parser interface
- `sources/factory.py` - Factory for creating sources based on config
- `tools/refresh.py` - Manual cache refresh tool

#### Configuration
- `GRANOLA_DOCUMENT_SOURCE` - Choose 'local' or 'remote' (default: local)
- `GRANOLA_API_TOKEN` - Bearer token for API authentication
- `GRANOLA_API_BASE` - API base URL (default: https://api.granola.ai)
- `GRANOLA_CACHE_ENABLED` - Enable caching (default: true)
- `GRANOLA_CACHE_DIR` - Cache directory (default: ~/.granola/remote_cache)
- `GRANOLA_CACHE_TTL_SECONDS` - Cache TTL (default: 86400 = 24h)

#### Documentation
- `REMOTE_SOURCE_GUIDE.md` - Comprehensive 400+ line guide covering configuration, deployment, security, and troubleshooting
- `IMPLEMENTATION_SUMMARY.md` - Technical implementation details and architecture
- `examples/remote_source_example.py` - Usage example demonstrating remote source
- Updated `README.md` with integrated remote mode quick start guide

#### Tools Updated
- `granola.cache.status` - Now supports both local and remote sources
- `granola.cache.refresh` - New tool for manual cache refresh
- All meeting tools - Accept both parser and adapter types

#### Benefits
- ✅ Deploy to web browsers, edge functions, serverless platforms
- ✅ No local file system required
- ✅ Always up-to-date data from API
- ✅ Backward compatible (local mode unchanged)
- ✅ Zero new dependencies (stdlib only)

#### Technical Details
- Gzip decompression using Python stdlib
- Automatic retry with exponential backoff (max 3 attempts)
- Cache keyed by request parameters (limit, offset, etc.)
- Non-blocking cache writes
- Token redaction in errors/logs
- Type-safe with full type hints

### Migration
No breaking changes! Existing local mode works unchanged. To use remote mode:
```bash
export GRANOLA_DOCUMENT_SOURCE=remote
export GRANOLA_API_TOKEN=your_token_here
```

See `REMOTE_SOURCE_GUIDE.md` for detailed migration instructions.

## [0.1.0] - 2025-09-29

### Added

#### Core Architecture
- **MCP Server Implementation**: FastMCP-based server exposing Granola meetings via Model Context Protocol
- **Local-First Design**: Read-only access to local Granola cache with no external dependencies in default mode
- **Double-JSON Parser**: Robust parser for Granola's double-encoded JSON cache format
- **Type-Safe Schemas**: Pydantic models for all tool inputs and outputs ensuring contract stability

#### Tools (MCP Endpoints)
- `granola.conversations.list` / `granola.meetings.list`: List meetings with filtering and pagination
  - Query search, date range filtering, participant filtering
  - Configurable limit (1-500, default: 50) with cursor-based pagination
- `granola.conversations.get` / `granola.meetings.get`: Retrieve detailed meeting information
  - Optional field inclusion for notes and metadata
- `granola.meetings.search`: Advanced search with multi-field queries
  - Full-text search across titles, notes, and participants
  - Advanced filters: participants, platform, date ranges
- `granola.meetings.export_markdown`: Export meetings to markdown format
  - Customizable sections: header, notes, attendees, links
- `granola.meetings.stats`: Meeting analytics and statistics
  - Time window support: 7d, 30d, 90d
  - Grouping by day or week
- `granola.cache.status`: Cache health and status information

#### Configuration System
- **Environment-based Configuration**: All settings via `GRANOLA_*` environment variables
- **Path Expansion**: Automatic expansion of `~` and environment variables in paths
- **Immutable Settings**: Frozen configuration prevents runtime mutations
- **Validation**: Pydantic-based validation with clear error messages
- **Configurable Settings**:
  - `GRANOLA_CACHE_PATH`: Path to Granola cache file (default: `~/Library/Application Support/Granola/cache-v3.json`)
  - `GRANOLA_STDLIB_ONLY`: Force stdlib-only mode (default: `true`)
  - `GRANOLA_USE_SQLITE`: Enable SQLite indexing (default: `false`)
  - Network and timeout settings for future hybrid mode

#### Parser Features
- **Robust Double-Decoding**: Handles both string-encoded and direct object cache formats
- **Meeting Normalization**: Extracts and normalizes meeting data from complex nested structures
- **Participant Deduplication**: Smart participant extraction with order preservation
- **Platform Detection**: Automatic platform identification (Zoom, Google Meet, Teams)
- **Folder Support**: Extracts folder/collection associations
- **Timestamp Normalization**: Handles epoch seconds, milliseconds, and ISO 8601 formats
- **Cache State Management**: Memoization and force-reload capabilities
- **Health Checks**: Validation and diagnostic methods for cache integrity

#### Error Handling
- **Structured Exceptions**: Typed error classes with consistent payloads
- **Error Categories**: `BAD_REQUEST`, `NOT_FOUND`, `IO_ERROR`, `TIMEOUT`
- **Detailed Context**: Errors include structured details for debugging
- **Serialization**: Automatic conversion to MCP-compatible error responses

#### Utilities
- **Date Parsing**: Flexible ISO 8601 timestamp parsing and normalization
- **Markdown Export**: Clean meeting-to-markdown rendering with customizable sections
- **Date Grouping**: Helper functions for stats aggregation by day/week

#### Testing
- **Parser Tests**: Comprehensive unit tests for double-JSON parsing
- **Tool Tests**: Mock-based tests for all MCP tools
- **Edge Case Coverage**: Tests for malformed data, missing fields, and error conditions
- **Test Configuration**: pytest integration with coverage support

#### Development Infrastructure
- **Package Structure**: Modern src-layout with proper namespace isolation
- **Entry Point**: `granola-mcp` command-line entry point
- **Code Quality Tools**: Black, isort, mypy configuration
- **Type Hints**: Full type coverage with Python 3.10+ type hints
- **Documentation**: Comprehensive docstrings with Google-style format

#### Documentation
- **README**: Complete quickstart, installation, and usage guide
- **MCP Inspector Integration**: Detailed guide for testing with MCP Inspector tool
- **Tool Documentation**: JSON parameter examples for all tools
- **Configuration Examples**: Sample config files for MCP Inspector
- **Development Guide**: Testing and formatting instructions

### Technical Details

#### Dependencies
- **Core**: `pydantic>=2.7`, `typing-extensions>=4.7`
- **MCP Runtime** (optional): `fastmcp>=0.3.0`, `mcp>=1.2.0`
- **Development**: `pytest>=8.0`, `pytest-cov>=5.0`, `black>=24.0`, `isort>=5.12`, `mypy>=1.8`

#### Architecture Principles
- **Separation of Concerns**: Tool logic decoupled from MCP runtime
- **Testability**: All business logic testable without MCP dependencies
- **Type Safety**: Pydantic models enforce contracts at runtime
- **Immutability**: Configuration and cache state are immutable
- **Lazy Loading**: FastMCP imported only when needed
- **Local-First**: No network calls in default stdlib-only mode

### Fixed
- **FastMCP Tool Registration**: Fixed decorator stacking issue where multiple `@app.tool()` decorators on the same function caused `TypeError`. Now each tool name has its own dedicated function while sharing underlying implementation.

### Security
- **Read-Only**: Server never modifies Granola cache or data
- **Local-Only**: No network access in default configuration
- **Path Validation**: Proper path expansion and validation
- **Error Sanitization**: Error messages avoid leaking sensitive paths

### Performance
- **Cache Memoization**: In-memory caching of parsed data
- **Efficient Filtering**: Linear search optimized with early returns
- **Lazy Evaluation**: Data loaded only when needed
- **Minimal Allocations**: Efficient list/dict operations

---

## [Unreleased]

### Planned Features
- **SQLite FTS**: Full-text search index for large meeting collections
- **Incremental Updates**: Delta parsing for cache changes
- **Resource Support**: MCP resources for browsing folder hierarchies
- **Prompt Support**: Pre-built prompts for common meeting queries
- **Streaming**: Support for streaming large result sets
- **Filtering DSL**: Advanced query language for complex filters
- **Export Formats**: Additional export formats (PDF, JSON, CSV)
- **Time Zone Support**: Explicit timezone handling in date filters
- **Meeting Duration**: Calculate and expose meeting duration
- **Participant Analytics**: Enhanced participant statistics and trends

### Known Limitations
- **Linear Search**: Search is O(n) in stdlib-only mode; use SQLite for large datasets
- **No Incremental Parsing**: Full cache re-parse on each reload
- **Limited Date Filtering**: Stats window filtering not fully implemented
- **No Streaming**: Large result sets returned in single response
- **Platform Detection**: Limited to known providers (Zoom, Meet, Teams)

---

## Version History

- **0.1.0** (2025-09-29): Initial release with core MCP server functionality
