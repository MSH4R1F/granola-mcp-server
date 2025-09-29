# Granola AI MCP Server — Design Document (FastMCP, Poke, ChatGPT)

**Owner:** Mohamed Sharif
**Status:** Draft v0.5 (meetings‑only, read‑only, stdlib‑first)
**Last updated:** 28 Sep 2025 (Europe/London)

---

## 0) Executive Summary

Granola has **no public API**. We will ship a **local‑first, read‑only MCP server** that treats Granola’s on‑device cache as the system of record and exposes **meetings/conversations** via MCP tools. No writes to any local store are required for v1. We support two profiles:

* **Stdlib‑only (default):** live‑parse the cache JSON (double‑JSON decoding), stitch transcripts on demand, and serve queries — zero external deps.
* **SQLite+FTS (optional):** if you need fast full‑text search across large corpora, build a local index (still read‑only).

FastMCP clients (Poke, ChatGPT) call tools that read from the cache; optional adapters (later) can enrich data.

---

## 1) Goals & Non‑Goals

### 1.1 Goals

* Provide a stable MCP interface for **meetings** (list, get, search, export, stats).

* Be drop‑in with FastMCP clients; minimize adapter glue for Poke + ChatGPT.

* Production concerns: structured errors and predictable latency.

* First‑class observability: logs, metrics, optional OpenTelemetry spans.

* Secure by default: no secrets in logs; local‑only by default.

* Secure by default: no secrets in logs; least‑privileged scopes where supported.

---

## 2) High‑Level Architecture

```
Poke / ChatGPT / other MCP clients
           │
           ▼
      FastMCP runtime  ── (MCP Tools) ──►  granola-mcp-server
                                               │
                                               ▼
                            Local Datastore (JSON/SQLite + FTS index)
                                               │
                    ┌───────────────┬─────────────────┬───────────────────┐
                    ▼               ▼                 ▼
             Granola Cache     Notion Adapter     CRM Adapters (future)
             (file watcher)    (pull/merge)       (HubSpot, etc.)
```

**Edge contracts:**

* **Inbound (MCP):** JSON‑serializable tool calls; deterministic, validated schemas.
* **Outbound (v1 local):** file I/O into a structured **cache directory**; no network required.
* **Outbound (v1.x integrations):** adapter pull/merge into local store via normalized upserts.

**Key design choices:**

* Local **SQLite + FTS5** as canonical store (with JSON import/export for portability).
* Pluggable **Source Adapters** (Granola cache, Notion, CRM) that emit normalized records.
* Background **indexer** builds/updates FTS tables; optional embeddings later.

### 2.1 Operating Modes

* **Local‑Only (default):** No network calls; all reads/writes stay on device. (v1)
* **Hybrid (experimental, sidelined):** Optional **Supabase token** read from `supabase.json` to query Granola’s private API for pull‑only sync; local store remains the source of truth. Disabled by default. (v1.x)

---

## 3) Components

1. **server.py** — FastMCP entry point; registers tools and starts the server.
2. **tools/** — MCP tool definitions and handlers mapping to cache readers / optional indexes.
3. **schemas.py** — Pydantic models for inputs/outputs; stable JSON schemas.
4. **datastore/** *(optional)* — Local index abstraction:

   * `sqlite.py` (Tables for meetings/transcripts; FTS5 views) — **optional**
   * `json_io.py` (import/export; migration) — **optional**
5. **adapters/** — Future sources (Notion, CRM) — **later**
6. **watcher.py** *(optional)* — File watcher to auto‑refresh indexes.
7. **config/** — Environment parsing + defaults.
8. **utils/** — `date_parser.py`, `timezone.py`, stitching helpers.
9. **tests/** — Unit + contract tests; golden fixtures.

---

## 4) Tool Surface (v1 — local‑first, read‑only)

> Namespaces use `granola.*`. Primary surface is **meetings**; conversations === meetings in this context.

### 4.1 `granola.conversations.list` (alias: `granola.meetings.list`)

* **Input:** `{ q?: string, from?: iso8601, to?: iso8601, participants?: string[], limit?: int, cursor?: str }`
* **Output:** `{ items: MeetingSummary[], next_cursor?: str }`
* **Backed by:** stdlib live‑parse; optional FTS index for speed.

### 4.2 `granola.conversations.get` (alias: `granola.meetings.get`)

* **Input:** `{ id: string, include?: ('transcript'|'notes'|'metadata')[] }`
* **Output:** `{ meeting: Meeting, transcript?: TranscriptTurn[] }`
* **Semantics:** stitched transcript on demand (lazy); no writes.

### 4.3 `granola.meetings.search`

* **Input:** `{ q: string, filters?: {participants?: string[], platform?: string, before?: iso8601, after?: iso8601}, limit?: int, cursor?: str }`
* **Output:** `{ items: MeetingSummary[], next_cursor?: str }`

### 4.4 `granola.meetings.export_markdown`

* **Input:** `{ id: string, sections?: ('header'|'notes'|'transcript'|'attendees'|'links')[] }`
* **Output:** `{ markdown: string }`

### 4.5 `granola.meetings.stats`

* **Input:** `{ window?: '7d'|'30d'|'90d', group_by?: 'day'|'week' }`
* **Output:** `{ counts: { by_period: Array<{period: string, meetings: number}> }, participants?: Array<{name: string, count: number}> }`

### 4.6 `granola.cache.status`

* **Purpose:** report cache path, size, last load time.
* **Output:** `{ path, size_bytes, last_loaded_ts, profile: 'stdlib'|'sqlite' }`

### (removed)

* `granola.list_channels`, `granola.send_message`, `granola.list_threads`, `granola.get_thread`, `granola.search_messages` — **dropped** for meetings‑only v1.

---

## 5) Data Models

```ts
// Meeting (summary)
{ id: string; title: string; start_ts: string; end_ts?: string; participants: string[]; platform?: 'zoom'|'meet'|'teams'|'other'; has_transcript?: boolean; metadata?: object }

// TranscriptTurn (stitched)
{ start_ts: string; end_ts?: string; speaker: string; text: string }
```

### 5.1 Cache Mapping (read‑only)

* Double‑JSON: top‑level `{ cache: "{...}" }` → decode twice.
* Collections → structures:

  * `documents` → Meeting core (title, notes, created/updated).
  * `meetingsMetadata` → participants, organizer, conference details.
  * `transcripts` → segment list → stitched `TranscriptTurn[]`.
* Unknown fields → `metadata` bag.

### 5.2 Optional Local Index (SQLite + FTS)

* Purely **performance**; never authoritative.
* Suggested tables: `meetings`, `transcripts`, `meetings_fts`, `transcripts_fts`.

---

## 6) Key Flows

### 6.1 List conversations/meetings

1. Parse cache (or query FTS index if enabled).
2. Apply filters (time window, participants, free‑text `q`).
3. Return paginated `MeetingSummary[]`.

### 6.2 Get a specific conversation/meeting

1. Locate meeting by `id` (prefer `iCalUID`/document id; fallback to hash).
2. Build `Meeting` object; stitch transcript turns lazily.
3. Optionally render Markdown for export.

### 6.3 Search

1. Stdlib path: scan title/notes/participants; simple ranking.
2. SQLite path: FTS query across `meetings_fts` + `transcripts_fts` with filters.

---

## 7) Error Model

```json
{
  "code": "BAD_REQUEST" | "NOT_FOUND" | "IO_ERROR" | "TIMEOUT",
  "message": "human readable",
  "details": {"path": "...", "hint": "..."}
}
```

* `IO_ERROR`: cache file missing/corrupt; include recovery hint.
* `NOT_FOUND`: meeting id not present.

---

## 8) Security & Compliance

* **Local only (v1):** no network calls required.
* **Read‑only:** we never modify the cache; no writes to local index unless opted‑in for performance.
* **File permissions:** restrict cache path to user (0700). Redact secrets on export.
* **PII:** field allowlist for logs; default redact transcript text.

---

## 9) Performance & Limits

* **Stdlib‑only default:** good up to ~2–5k meetings; sub‑second list/get; search is linear.
* **Optional FTS index:** enables sub‑second full‑text search on large corpora; adds one‑time index build and small disk usage.
* **Lazy transcript stitching:** only compute when requested; cache per‑id with small LRU.
* **Watcher (optional):** trigger index refresh on cache updates with debounce.

---

## 10) Observability

* **Logging:** structured JSON; `event`, `tool`, `rows_upserted`, `latency_ms`, `db_busy_retries`.
* **Metrics:** counters for ingests, FTS queries; histograms for latency.
* **Tracing:** local spans around tool execution and DB ops.
* **CLI UX:** pretty tables/colors for local inspection; deterministic MD exports (good for diffs).

---

## 11) Configuration

### Where the cache actually lives

Granola itself writes its working cache under the user’s application‑support directory. On macOS, this is typically:

```
~/Library/Application Support/Granola/cache-v3.json
```

We do **not** assume `~/.granola` is authoritative. The `~/.granola/` directory in this design is only a **convention for our MCP server** (to hold optional SQLite indexes, export snapshots, or a symlink to the real cache). The true source of record is always the `cache-v3.json` file managed by the Granola desktop app.

---

| Env Var               | Default                                               | Notes                              |
| --------------------- | ----------------------------------------------------- | ---------------------------------- |
| `GRANOLA_CACHE_PATH`  | `~/Library/Application Support/Granola/cache-v3.json` | Path to Granola cache (macOS)      |
| `GRANOLA_STDLIB_ONLY` | `true`                                                | Default profile (no SQLite)        |
| `GRANOLA_USE_SQLITE`  | `false`                                               | Enable optional FTS index          |
| `GRANOLA_DB_PATH`     | `~/.granola/granola.db`                               | SQLite index location (if enabled) |
| `GRANOLA_WATCH`       | `false`                                               | Watch cache for changes            |
| `GRANOLA_LOG_LEVEL`   | `INFO`                                                | `DEBUG` for dev                    |

**Hybrid (experimental; disabled by default)**

| Env Var                   | Default                           | Notes                               |
| ------------------------- | --------------------------------- | ----------------------------------- |
| `GRANOLA_NET_ENABLED`     | `false`                           | Master switch for Hybrid mode       |
| `GRANOLA_SUPABASE_CONFIG` | `~/.granola/supabase.json`        | Path to Supabase config (read‑only) |
| `GRANOLA_BASE_URL`        | `https://api.granola.example.com` | Private API base URL                |
| `GRANOLA_TIMEOUT_SECONDS` | `15`                              | Per‑request timeout                 |
| `GRANOLA_MAX_RETRIES`     | `3`                               | Retry on 429/5xx                    |

--------------------- | ----------------------------------------------------- | ---------------------------------- |
| `GRANOLA_CACHE_PATH`  | `~/Library/Application Support/Granola/cache-v3.json` | Path to Granola cache (macOS)      |
| `GRANOLA_CACHE_DIR`   | `~/.granola/`                                         | Directory for watched cache files  |
| `GRANOLA_DB_PATH`     | `~/.granola/granola.db`                               | SQLite primary store               |
| `GRANOLA_WATCH`       | `true`                                                | Enable file watcher                |
| `GRANOLA_PAGE_SIZE`   | `50`                                                  | Pagination hint                    |
| `GRANOLA_LOG_LEVEL`   | `INFO`                                                | `DEBUG` for dev                    |
| `GRANOLA_FTS`         | `true`                                                | Enable FTS5 index                  |
| `GRANOLA_EXPORT_JSON` | `false`                                               | Emit JSON snapshots after writes   |
| `GRANOLA_STDLIB_ONLY` | `false`                                               | If `true`, skip SQLite; live‑parse |

**Hybrid (experimental; disabled by default)**

| Env Var                   | Default                           | Notes                               |
| ------------------------- | --------------------------------- | ----------------------------------- |
| `GRANOLA_NET_ENABLED`     | `false`                           | Master switch for Hybrid mode       |
| `GRANOLA_SUPABASE_CONFIG` | `~/.granola/supabase.json`        | Path to Supabase config (read‑only) |
| `GRANOLA_BASE_URL`        | `https://api.granola.example.com` | Private API base URL                |
| `GRANOLA_TIMEOUT_SECONDS` | `15`                              | Per‑request timeout                 |
| `GRANOLA_MAX_RETRIES`     | `3`                               | Retry on 429/5xx                    |

--------------------- | ----------------------- | ---------------------------------- |
| `GRANOLA_CACHE_PATH`  | `~/.granola/cache.json` | Path to raw cache JSON (your file) |
| `GRANOLA_CACHE_DIR`   | `~/.granola/`           | Directory for watched cache files  |
| `GRANOLA_DB_PATH`     | `~/.granola/granola.db` | SQLite primary store               |
| `GRANOLA_WATCH`       | `true`                  | Enable file watcher                |
| `GRANOLA_PAGE_SIZE`   | `50`                    | Pagination hint                    |
| `GRANOLA_LOG_LEVEL`   | `INFO`                  | `DEBUG` for dev                    |
| `GRANOLA_FTS`         | `true`                  | Enable FTS5 index                  |
| `GRANOLA_EXPORT_JSON` | `false`                 | Emit JSON snapshots after writes   |

**Hybrid (experimental; disabled by default)**

| Env Var                   | Default                           | Notes                               |
| ------------------------- | --------------------------------- | ----------------------------------- |
| `GRANOLA_NET_ENABLED`     | `false`                           | Master switch for Hybrid mode       |
| `GRANOLA_SUPABASE_CONFIG` | `~/.granola/supabase.json`        | Path to Supabase config (read‑only) |
| `GRANOLA_BASE_URL`        | `https://api.granola.example.com` | Private API base URL                |
| `GRANOLA_TIMEOUT_SECONDS` | `15`                              | Per‑request timeout                 |
| `GRANOLA_MAX_RETRIES`     | `3`                               | Retry on 429/5xx                    |

---------------------------------|------------------------------|-------|
| `GRANOLA_CACHE_PATH`            | `~/.granola/cache.json`      | Path to raw cache JSON (your file) |
| `GRANOLA_CACHE_DIR`             | `~/.granola/`                | Directory for watched cache files |
| `GRANOLA_DB_PATH`               | `~/.granola/granola.db`      | SQLite primary store |
| `GRANOLA_WATCH`                 | `true`                       | Enable file watcher |
| `GRANOLA_PAGE_SIZE`             | `50`                         | Pagination hint |
| `GRANOLA_LOG_LEVEL`             | `INFO`                       | `DEBUG` for dev |
| `GRANOLA_FTS`                   | `true`                       | Enable FTS5 index |
| `GRANOLA_EXPORT_JSON`           | `false`                      | Emit JSON snapshots after writes |

------------------------- | ---------- | --------------------------------------- |
| `GRANOLA_BASE_URL`        | (required) | e.g., `https://api.granola.example.com` |
| `GRANOLA_API_KEY`         | —          | or `GRANOLA_API_KEY_FILE`               |
| `GRANOLA_TIMEOUT_SECONDS` | `15`       | per‑request timeout                     |
| `GRANOLA_MAX_RETRIES`     | `3`        | 429/5xx only                            |
| `GRANOLA_LOG_LEVEL`       | `INFO`     | `DEBUG` for dev                         |
| `GRANOLA_PAGE_SIZE`       | `50`       | server side hint if supported           |

---

## 12) Deployment

* **Packaging:** `pyproject.toml` with console script `granola-mcp` → `server:main`.
* **Profiles:**

  * **Stdlib‑only (default):** live JSON parse; zero external deps; simplest install.
  * **SQLite+FTS (optional):** add local index for fast search; still read‑only.
* **Modes:**

  * Local dev: `granola-mcp --dev`.
  * Headless agent: run as a user service with cache path access.
* **CI:** lint, typecheck, tests; fixture cache JSON for reproducible runs.

---

## 13) Testing Strategy

* **Unit tests:** ingest parser for your cache schema; upsert logic; FTS queries; cursor pagination.
* **Contract tests:** golden I/O for each MCP tool with seeded SQLite.
* **E2E (local):** mutate a fixture cache file and assert watcher ingests changes.
* **Load smoke:** bulk import 100k messages; search P95 < 200ms on laptop.

---

## 14) Backward/Forward Compatibility

* Version tools via semantic version in `package.json`/env banner.
* Avoid breaking output shapes; only additive changes in v1.x.
* Introduce new tools for new features; deprecate with sunset warnings.

---

## 15) Risks & Mitigations

* **Upstream instability:** Implement circuit breaker; cache failures briefly.
* **Schema drift:** Freeze JSON Schemas; CI diff check; publish changelog.
* **Secret leakage:** Centralized redaction; transport tests.
* **Overfetch:** Enforce server caps; expose `next_cursor` religiously.

---

## 16) Roadmap

* **v1.0:** stdlib‑only meetings surface (`list/get/search/export/stats`).
* **v1.1:** optional SQLite+FTS index + watcher; simple analytics tools.
* **v1.2:** semantic search/embeddings (local); Notion/CRM adapters (pull‑only).

---

## 17) Open Questions

* Canonical meeting IDs from cache (document id vs iCalUID) — pick one and normalize.
* Participant identity normalization (emails vs display names).
* Minimum fields required for useful `MeetingSummary` (title+start? title+attendees?).

---

## 18) Cache Structure & Example

Granola’s cache file is a **double‑JSON** structure. The outer file is a JSON object with a `cache` field whose value is **itself** a JSON string. After decoding twice, we work with an object shaped roughly like:

```jsonc
{
  "state": {
    // 1) Calendar mirrors (optional)
    "events": [
      {
        "id": "o8kbm8m3...",
        "iCalUID": "o8kbm8m3...@google.com",
        "summary": "Meet First Year Tutees with Dr. Ahmed Fetit",
        "start": { "dateTime": "2025-09-29T15:30:00+01:00", "timeZone": "Europe/London" },
        "end":   { "dateTime": "2025-09-29T16:00:00+01:00",  "timeZone": "Europe/London" },
        "organizer": { "email": "<redacted>" },
        "htmlLink": "https://www.google.com/calendar/event?..."
      },
      { /* more events */ }
    ],

    // 2) Core meeting records (documents)
    "documents": {
      "e03cdf26-899c-45b7-a208-6e0dc2b244c3": {
        "id": "e03cdf26-...",
        "title": "Interview Structure Overview",
        "created_at": "2025-08-29T10:52:02.971Z",
        "people": [ { "name": "Alice" }, { "name": "Bob" } ],
        "notes_plain": "Free‑text notes (if present)",
        "notes_markdown": "...",              // fallback if no plain
        "notes": { "type": "doc", "content": [ /* rich tree */ ] },
        "overview": "…",                       // optional summary
        "summary": "…",                        // optional summary
        "type": "meeting"                      // or other kinds
      }
      // more document IDs → objects
    },

    // 3) Meeting metadata (attendees, platform, permissions, etc.)
    "meetingsMetadata": {
      "e03cdf26-...": {
        "organizer": { "name": "Alice", "email": "<redacted>" },
        "attendees": [ { "name": "Bob", "responseStatus": "accepted" } ],
        "conference": { "provider": "google_meet", "url": "https://meet.google.com/..." }
      }
    },

    // 4) Transcripts (two shapes observed)
    "transcripts": {
      // a) List of segments (preferred)
      "e03cdf26-...": [
        { "ts": "2025-08-29T10:52:05Z", "source": "Alice", "text": "Welcome…" },
        { "ts": "2025-08-29T10:52:12Z", "source": "Bob",   "text": "Thanks…" }
      ],
      // b) Legacy object with content/speakers
      "76da3e41-...": {
        "content": "Flattened transcript text…",
        "speakers": ["Alice", "Bob"]
      }
    },

    // 5) AI panels (summaries/structured sections)
    "documentPanels": {
      "e03cdf26-...": {
        "6e487d05-9f05-4ae6-b320-628e457ff136": {
          "title": "Summary",
          "created_at": "2025-08-29T10:52:02.971Z",
          "original_content": "<p>HTML summary…</p>",  // may include <hr>
          "content": { "type": "doc", "content": [ /* rich tree */ ] }
        }
      }
    },

    // 6) Folders/Lists (organization)
    "documentLists": {
      "list_id_A": ["e03cdf26-...", "76da3e41-..."]
    },
    "documentListsMetadata": {
      "list_id_A": { "title": "Recruiting", "created_at": "…" }
    }
  }
}
```

### Parsing rules we use (v1)

* **Double‑decode**: `outer = json.load(file)` → `state = json.loads(outer['cache'])['state']`.
* **Meetings** come from `state.documents` (title, created_at, people, notes).
* **Participants**: prefer `documents[*].people[].name`; otherwise check `meetingsMetadata` attendees.
* **Transcripts**: support both list‑of‑segments and legacy dict. Coalesce consecutive turns per speaker when stitching.
* **Notes**: prefer `notes_plain` → `notes_markdown` → walk the rich `notes.content` tree.
* **Panels**: collect non‑trivial `original_content` and the first structured `content` block as a fallback for notes.
* **Folders**: build `meeting_id → {folder_id, folder_name}` from `documentLists*`.
* **Timestamps**: normalize `'Z'` to `+00:00` and return ISO 8601.

> **Safety note:** The cache can include PII (names, emails, links). Our tools are **read‑only** and redact sensitive fields in logs/exports unless explicitly requested.

---

## 20) Concrete Parser Class API (stdlib‑only)

### 20.1 Public interface

* `GranolaParser(cache_path: Optional[str])`

  * `load_cache(force_reload: bool = False) -> Dict[str, Any]` — **double‑JSON** parse with strict validation; raises `GranolaParseError`.
  * `get_meetings(debug: bool = False) -> List[Dict[str, Any]]` — combine `documents` + `meetingsMetadata` + `transcripts` + `documentPanels` and folder lists.
  * `get_meeting_by_id(meeting_id: str) -> Optional[Dict[str, Any]]` — try common id fields (`id|meeting_id|session_id|uuid`).
  * `validate_cache_structure() -> bool` — quick health check.
  * `get_cache_info() -> Dict[str, Any]` — path/exists/readable/size/meeting_count/valid_structure.
  * `reload() -> Dict[str, Any]` — force reload from disk.

### 20.2 Implementation notes

* Validate cache path readability before open; emit helpful errors.
* Handle `documentPanels`:

  * `ai_summary_html`: collect non‑link `original_content` (skip `<hr>`‑only) and join.
  * `panel_content`: store first structured panel (`content` dict) as fallback for notes.
* Folder mapping: build `meeting_id → {folder_id, folder_name}` from `documentLists` + `documentListsMetadata`.
* Transcript variants: list (segments) vs dict (legacy); aggregate speakers; support missing/empty gracefully.
* Keep everything **read‑only**; no writes to cache or disk.

### 20.3 Error types

* `GranolaParseError(Exception)` — raised on invalid/missing fields, unreadable file, or JSON errors.

---
