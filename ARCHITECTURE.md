# Architecture Documentation

This document describes the technical architecture, design decisions, and implementation details of the Granola MCP Server.

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Component Design](#component-design)
4. [Data Flow](#data-flow)
5. [Design Principles](#design-principles)
6. [Implementation Details](#implementation-details)
7. [Testing Strategy](#testing-strategy)
8. [Future Enhancements](#future-enhancements)

---

## Overview

The Granola MCP Server is a **local-first, read-only Model Context Protocol (MCP) server** that exposes Granola meeting data through a standardized interface. It enables AI assistants and other MCP clients to query, search, and export meeting information without requiring network access or API credentials.

### Key Characteristics

- **Local-First**: Reads directly from Granola's local cache file
- **Read-Only**: Never modifies source data
- **Zero-Network**: No external API calls in default mode
- **Type-Safe**: Pydantic models enforce data contracts
- **Testable**: Business logic decoupled from MCP runtime
- **Extensible**: Designed for future SQLite indexing and hybrid modes

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        MCP Client                            │
│              (Claude, Cursor, Custom Tools)                  │
└─────────────────────┬───────────────────────────────────────┘
                      │ MCP Protocol (stdio/sse/http)
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastMCP Runtime                            │
│              (Protocol Handler & Router)                     │
└─────────────────────┬───────────────────────────────────────┘
                      │ Tool Invocations
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              Granola MCP Server (server.py)                  │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Tool Registration Layer                           │    │
│  │  • meetings_list                                   │    │
│  │  • meetings_get                                    │    │
│  │  • meetings_search                                 │    │
│  │  • meetings_export_md                              │    │
│  │  • meetings_stats_tool                             │    │
│  │  • cache_status_tool                               │    │
│  └──────────────────┬─────────────────────────────────┘    │
│                     │                                        │
│  ┌──────────────────▼─────────────────────────────────┐    │
│  │  Tool Implementation Layer (tools/meetings.py)     │    │
│  │  • list_meetings()                                 │    │
│  │  • get_meeting()                                   │    │
│  │  • search_meetings()                               │    │
│  │  • export_markdown()                               │    │
│  │  • meetings_stats()                                │    │
│  │  • cache_status()                                  │    │
│  └──────────────────┬─────────────────────────────────┘    │
│                     │                                        │
│  ┌──────────────────▼─────────────────────────────────┐    │
│  │  Data Layer (parser.py)                            │    │
│  │  • GranolaParser                                   │    │
│  │  • Double-JSON decoding                            │    │
│  │  • Meeting extraction & normalization              │    │
│  │  • Cache state management                          │    │
│  └──────────────────┬─────────────────────────────────┘    │
│                     │                                        │
└─────────────────────┼────────────────────────────────────────┘
                      │ File I/O
                      ▼
              ┌──────────────────┐
              │  Granola Cache   │
              │  cache-v3.json   │
              │  (Double-JSON)   │
              └──────────────────┘
```

### Module Structure

```
src/granola_mcp_server/
├── __init__.py              # Package metadata
├── server.py                # FastMCP entry point & tool registration
├── parser.py                # Cache parsing & meeting extraction
├── schemas.py               # Pydantic models for API contracts
├── errors.py                # Structured exception classes
├── config/
│   ├── __init__.py
│   └── env.py               # Environment-based configuration
├── tools/
│   ├── __init__.py
│   ├── meetings.py          # Meeting-related tool implementations
│   └── status.py            # Cache status tool
└── utils/
    ├── __init__.py
    ├── date_parser.py       # Date/timestamp utilities
    └── markdown_export.py   # Markdown rendering utilities
```

---

## Component Design

### 1. Server Layer (`server.py`)

**Responsibility**: FastMCP integration and tool registration

**Key Functions**:
- `main()`: Entry point that initializes config, parser, and FastMCP runtime
- `_register_fastmcp_tools()`: Registers all tool handlers with FastMCP

**Design Notes**:
- Lazy imports FastMCP to keep stdlib-only path lightweight
- Each tool name gets its own function (no decorator stacking)
- Dual tool names for backward compatibility (`conversations.*` and `meetings.*`)

```python
@app.tool("granola.meetings.list")
def meetings_list(params: ListMeetingsInput) -> ListMeetingsOutput:
    return list_meetings(config, parser, params)
```

### 2. Tool Layer (`tools/meetings.py`)

**Responsibility**: Business logic for meeting operations

**Key Functions**:
- `list_meetings()`: Filtering, pagination, and list generation
- `get_meeting()`: Single meeting retrieval by ID
- `search_meetings()`: Full-text search with advanced filters
- `export_markdown()`: Meeting-to-markdown conversion
- `meetings_stats()`: Aggregation and statistics
- `cache_status()`: Cache health information

**Design Pattern**: Pure functions that take `(config, parser, params)` and return typed outputs

**Filtering Strategy**:
```python
def matches(item: Dict[str, object]) -> bool:
    # Query search
    if params.q:
        q = params.q.lower()
        hay = f"{item.get('title','')} {item.get('notes','')} ...".lower()
        if q not in hay:
            return False
    
    # Participant filter
    if params.participants:
        want = {p.lower() for p in params.participants}
        have = {str(p).lower() for p in (item.get("participants") or [])}
        if not want.intersection(have):
            return False
    
    # Date range filters
    # ...
    return True
```

### 3. Parser Layer (`parser.py`)

**Responsibility**: Cache file parsing and meeting extraction

**Key Classes**:
- `GranolaParser`: Main parser with cache management
- `CacheState`: Dataclass holding parsed cache and metadata
- `MeetingDict`: TypedDict for normalized meeting records

**Parsing Flow**:
```
1. Read outer JSON file
2. Extract `cache` field (string or dict)
3. If string, parse inner JSON
4. Validate structure (must have `state` field)
5. Extract meetings from `state.documents`
6. Enrich with metadata from `state.meetingsMetadata`
7. Add participant data from `state.documents[*].people`
8. Map to folders using `state.documentLists`
9. Normalize timestamps and platform identifiers
10. Sort by start_ts descending
```

**Double-JSON Handling**:
```python
# Outer JSON
outer = json.load(f)

# Cache field can be string (double-encoded) or dict (direct)
cache_field = outer["cache"]
if isinstance(cache_field, str):
    inner = json.loads(cache_field)  # Second decode
else:
    inner = cache_field  # Already decoded
```

**Meeting Normalization**:
- Timestamps → ISO 8601
- Participants → deduplicated list preserving order
- Platform → normalized to `"zoom"`, `"meet"`, `"teams"`, or `"other"`
- Notes → from `notes_plain`, `notes_markdown`, or `documentPanels`

### 4. Schema Layer (`schemas.py`)

**Responsibility**: Type-safe data contracts

**Key Models**:
- **Input Schemas**: `ListMeetingsInput`, `GetMeetingInput`, `SearchMeetingsInput`, etc.
- **Output Schemas**: `ListMeetingsOutput`, `GetMeetingOutput`, `SearchMeetingsOutput`, etc.
- **Data Models**: `MeetingSummary`, `Meeting`, `SearchFilters`, `StatsByPeriod`

**Design Principles**:
- Backward-compatible field additions only
- Optional fields with sensible defaults
- Field-level validation (e.g., `limit: int = Field(ge=1, le=500)`)
- Comprehensive docstrings for API documentation

**Example**:
```python
class ListMeetingsInput(BaseModel):
    q: Optional[str] = None
    from_ts: Optional[str] = Field(default=None, description="ISO 8601 lower bound")
    to_ts: Optional[str] = Field(default=None, description="ISO 8601 upper bound")
    participants: Optional[List[str]] = None
    limit: Optional[int] = Field(default=50, ge=1, le=500)
    cursor: Optional[str] = None
```

### 5. Configuration Layer (`config/env.py`)

**Responsibility**: Environment-based settings management

**Key Classes**:
- `AppConfig`: Pydantic Settings model with validation

**Features**:
- Automatic `GRANOLA_*` prefix for env vars
- Path expansion (`~` and `${VAR}` resolution)
- `.env` file support
- Immutable (frozen) configuration
- Derived properties (e.g., `effective_use_sqlite`)

**Configuration Fields**:
```python
cache_path: Path        # ~/Library/Application Support/Granola/cache-v3.json
use_sqlite: bool        # false (future)
db_path: Path           # ~/.granola/granola.db (future)
stdlib_only: bool       # true (forces pure Python mode)
net_enabled: bool       # false (experimental hybrid)
timeout_seconds: int    # 15
max_retries: int        # 3
```

### 6. Error Layer (`errors.py`)

**Responsibility**: Structured exception handling

**Error Classes**:
- `AppError`: Base class with code, message, details
- `BadRequestError`: Invalid input (`BAD_REQUEST`)
- `NotFoundError`: Resource not found (`NOT_FOUND`)
- `IOErrorApp`: File I/O issues (`IO_ERROR`)
- `TimeoutErrorApp`: Operation timeout (`TIMEOUT`)
- `GranolaParseError`: Cache parsing errors (`IO_ERROR`)

**Error Payload Format**:
```json
{
  "code": "NOT_FOUND",
  "message": "Meeting not found",
  "details": {
    "id": "meeting_123"
  }
}
```

### 7. Utilities Layer (`utils/`)

**Modules**:

**`date_parser.py`**:
- `ensure_iso8601()`: Flexible timestamp normalization
- `to_date_key()`: Date grouping for stats (day/week)

**`markdown_export.py`**:
- `render_meeting_markdown()`: Clean markdown generation
- Section customization (header, notes, attendees, links)

---

## Data Flow

### Tool Invocation Flow

```
1. MCP Client sends tool request
   ↓
2. FastMCP deserializes JSON to Pydantic input model
   ↓
3. Tool handler function called with typed params
   ↓
4. Tool function validates input (Pydantic automatic)
   ↓
5. Parser loads/retrieves cached meetings
   ↓
6. Tool applies filtering logic
   ↓
7. Results converted to Pydantic output models
   ↓
8. FastMCP serializes output to JSON
   ↓
9. Response sent to MCP client
```

### Cache Loading Flow

```
1. First tool invocation triggers parser.load_cache()
   ↓
2. Check if cache already loaded (memoization)
   ↓
3. If not loaded:
   a. Read file from disk
   b. Parse outer JSON
   c. Extract and parse inner JSON (if string)
   d. Validate structure
   e. Store in CacheState with timestamp
   ↓
4. Return cached state for subsequent calls
   ↓
5. Optional: force_reload=True bypasses memoization
```

### Meeting Extraction Flow

```
1. Parser accesses state.documents
   ↓
2. For each document:
   a. Filter to type="meeting" (or no type)
   b. Extract id, title, created_at
   c. Normalize timestamp to ISO 8601
   ↓
3. Enrich from state.meetingsMetadata:
   a. Add platform (conference.provider)
   b. Add attendees if not in documents[*].people
   ↓
4. Extract participants:
   a. From documents[*].people[].name
   b. Deduplicate preserving order
   c. Fallback to meetingsMetadata[*].attendees
   ↓
5. Extract notes:
   a. From documents[*].notes_plain or notes_markdown
   b. Fallback to documentPanels[*].original_content
   ↓
6. Map folders:
   a. Scan documentLists for meeting_id
   b. Add folder_id and folder_name
   ↓
7. Sort by start_ts descending
   ↓
8. Return List[MeetingDict]
```

---

## Design Principles

### 1. Local-First Architecture

**Principle**: All data operations use local cache files without network dependencies.

**Benefits**:
- No latency from API calls
- Works offline
- Privacy-preserving (no data leaves machine)
- No rate limits or quotas

**Implementation**:
- Direct file I/O via `pathlib`
- Stdlib JSON parsing
- Optional SQLite for indexing (future)

### 2. Read-Only Philosophy

**Principle**: Server never modifies source data.

**Benefits**:
- Safe to run alongside Granola app
- No data corruption risk
- Simplifies concurrency model
- Clear separation of concerns

**Guarantees**:
- No write/delete operations on cache file
- Parser uses read-only file handles
- Cache state stored in memory only

### 3. Type Safety

**Principle**: Strong typing at all boundaries.

**Implementation**:
- Pydantic models for all inputs/outputs
- Type hints throughout codebase
- TypedDict for internal data structures
- Runtime validation automatic

**Benefits**:
- Catches errors early
- Clear API contracts
- Better IDE support
- Self-documenting code

### 4. Separation of Concerns

**Principle**: Decouple business logic from MCP runtime.

**Layers**:
1. **Runtime Layer** (FastMCP): Protocol handling
2. **Registration Layer** (server.py): Tool wiring
3. **Business Logic** (tools/): Pure functions
4. **Data Access** (parser.py): Cache operations

**Benefits**:
- Testable without MCP server
- Reusable in other contexts
- Clear responsibility boundaries
- Easy to reason about

### 5. Lazy Evaluation

**Principle**: Load data only when needed.

**Examples**:
- FastMCP imported only when `main()` called
- Cache parsed on first tool invocation
- Meetings extracted on demand
- Results paginated to avoid large allocations

### 6. Immutability

**Principle**: Configuration and cache state are immutable after creation.

**Implementation**:
- `AppConfig` uses `frozen=True`
- `CacheState` is a frozen dataclass
- No in-place mutations of parsed data

**Benefits**:
- Thread-safe by default
- Easier to reason about state
- Prevents accidental modifications
- Cache invalidation is explicit

---

## Implementation Details

### Double-JSON Parsing

**Problem**: Granola stores cache as JSON with a string-encoded JSON field.

**Solution**:
```python
# Two-stage decode
outer = json.load(file)           # {"cache": "{...}"}
inner = json.loads(outer["cache"]) # {state: {...}}
```

**Robustness**:
- Handles both string and dict cache formats
- Validates structure at each stage
- Detailed error messages with context

### Participant Extraction

**Strategy**: Multiple fallbacks with deduplication

```python
# 1. Primary: documents[*].people[].name
for person in doc.get("people", []):
    if person.get("name") not in seen:
        participants.append(person["name"])

# 2. Fallback: meetingsMetadata[*].attendees[].name
if not participants:
    for attendee in metadata.get("attendees", []):
        if attendee.get("name") not in seen:
            participants.append(attendee["name"])
```

### Timestamp Normalization

**Handles**:
- ISO 8601 strings
- Unix epoch seconds
- Unix epoch milliseconds
- Invalid/missing values

```python
def _normalize_ts(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if value > 1e10:  # milliseconds
            value = value / 1000
        dt = datetime.fromtimestamp(value, tz=timezone.utc)
        return dt.isoformat()
    if isinstance(value, str):
        return ensure_iso8601(value)
    return str(value)
```

### Platform Detection

**Mapping**:
- `google_meet` → `"meet"`
- `zoom` → `"zoom"`
- `teams` → `"teams"`
- Other values → `"other"`
- Missing → `None`

### Pagination

**Strategy**: Cursor-based with numeric offsets

```python
def _paginate(items, *, limit, cursor):
    start = int(cursor or 0)
    end = start + limit
    next_cursor = str(end) if end < len(items) else None
    return items[start:end], next_cursor
```

**Benefits**:
- Simple implementation
- Efficient for moderate datasets
- Consistent with O(n) search

**Future**: Keyset pagination for SQLite mode

### Markdown Export

**Sections**:
- **header**: Title, date, platform
- **attendees**: Formatted participant list
- **notes**: Meeting notes/transcript
- **links**: Conference URLs (future)

**Format**:
```markdown
# Meeting Title

**Date**: 2024-01-15 10:00 AM UTC
**Platform**: Zoom

## Attendees
- Alice
- Bob
- Carol

## Notes
[Meeting notes content...]
```

---

## Testing Strategy

### Unit Tests

**Parser Tests** (`tests/test_parser.py`):
- Double-JSON decoding
- Meeting extraction
- Participant deduplication
- Timestamp normalization
- Error cases (malformed JSON, missing fields)

**Tool Tests** (`tests/test_tools.py`):
- All tool functions with mock parser
- Filtering logic
- Pagination
- Error handling (not found, bad request)
- Edge cases (empty results, boundary values)

### Test Patterns

**Mock-Based Testing**:
```python
def test_list_meetings():
    parser = MockParser(meetings=[...])
    config = AppConfig()
    params = ListMeetingsInput(limit=10)
    
    result = list_meetings(config, parser, params)
    
    assert len(result.items) == 10
```

**Fixture-Based Testing**:
```python
@pytest.fixture
def sample_cache():
    return {
        "cache": json.dumps({
            "state": {
                "documents": {...}
            }
        })
    }
```

### Coverage Goals

- **Parser**: >90% coverage
- **Tools**: >85% coverage
- **Schemas**: Validated through usage
- **Integration**: Manual testing with MCP Inspector

---

## Future Enhancements

### 1. SQLite Full-Text Search

**Design**:
```
┌─────────────────────────────┐
│  SQLite Database            │
│  ┌─────────────────────┐   │
│  │  meetings (FTS5)    │   │
│  │  - id               │   │
│  │  - title            │   │
│  │  - notes_content    │   │
│  │  - participants     │   │
│  └─────────────────────┘   │
│  ┌─────────────────────┐   │
│  │  indexes            │   │
│  │  - by_date          │   │
│  │  - by_participant   │   │
│  │  - by_platform      │   │
│  └─────────────────────┘   │
└─────────────────────────────┘
```

**Benefits**:
- Sub-millisecond search for large datasets
- Ranking and relevance scoring
- Complex boolean queries
- Phrase matching

### 2. MCP Resources

**Proposal**: Expose folder hierarchy as MCP resources

```
granola://folders/
  ├── Work Meetings
  │   └── meeting_123
  ├── 1:1s
  │   └── meeting_456
  └── All Hands
      └── meeting_789
```

**Use Cases**:
- Browse meetings by folder
- Hierarchical navigation
- Context-aware retrieval

### 3. MCP Prompts

**Pre-built Prompts**:
- "Summarize this week's meetings"
- "Find action items from meeting X"
- "List meetings with person Y"
- "Generate weekly report"

**Benefits**:
- Faster assistant interactions
- Consistent query patterns
- Discoverability

### 4. Incremental Updates

**Design**:
- Watch cache file for changes
- Parse only delta since last load
- Invalidate affected meetings
- Emit change notifications

**Benefits**:
- Faster reloads
- Real-time updates
- Lower memory footprint

### 5. Streaming Responses

**Design**:
- Server-sent events for large result sets
- Chunk meetings as they're processed
- Progress indicators

**Benefits**:
- Better UX for large queries
- Lower memory pressure
- Interruptible operations

---

## Performance Characteristics

### Time Complexity

| Operation | Stdlib Mode | SQLite Mode (Future) |
|-----------|-------------|---------------------|
| Load cache | O(n) file size | O(n) file size |
| List meetings | O(n) meetings | O(1) with indexes |
| Get meeting | O(n) meetings | O(1) with primary key |
| Search | O(n × m) notes length | O(log n) with FTS |
| Filter | O(n) meetings | O(log n) with indexes |
| Stats | O(n) meetings | O(1) with aggregates |

### Memory Usage

- **Cache in Memory**: ~1-5 MB per 1000 meetings (parsed)
- **Meeting List**: ~500 bytes per meeting (summary)
- **Full Meeting**: ~2-10 KB per meeting (with notes)

### Optimization Strategies

1. **Memoization**: Cache parsed data across tool calls
2. **Lazy Loading**: Don't extract notes unless requested
3. **Early Returns**: Short-circuit filters on first mismatch
4. **Pagination**: Limit memory for large result sets
5. **SQLite (Future)**: Offload search/filter to database

---

## Security Considerations

### Threat Model

**In Scope**:
- Local file system access
- User-controlled cache path
- Malformed cache data

**Out of Scope** (v1):
- Network attacks (no network layer)
- Multi-user access (single-user assumption)
- Authentication/authorization (local-only)

### Mitigations

1. **Path Traversal**: Use `Path.resolve()` to canonicalize
2. **Malformed JSON**: Structured error handling with try/except
3. **Resource Exhaustion**: Pagination limits, file size checks
4. **Error Leakage**: Sanitize paths in error messages

### Privacy

- **No Telemetry**: Zero network calls in default mode
- **Local-Only**: Data never leaves machine
- **Read-Only**: No modifications to source data
- **Transparent**: Open-source, auditable code

---

## Conclusion

The Granola MCP Server is architected for **simplicity, safety, and extensibility**. Its local-first, read-only design ensures privacy and reliability, while its modular structure enables future enhancements like SQLite indexing and hybrid modes.

The separation of concerns between MCP runtime, business logic, and data access makes the codebase testable, maintainable, and easy to extend. Type safety through Pydantic models ensures robust API contracts and clear documentation.

For questions or contributions, see the README and CONTRIBUTING guidelines.
