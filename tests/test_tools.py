"""Tests for tool functions using an in-memory parser setup."""

from __future__ import annotations

import json
from pathlib import Path

from granola_mcp_server.config import AppConfig
from granola_mcp_server.parser import GranolaParser
from granola_mcp_server.schemas import (
    ExportMarkdownInput,
    GetMeetingInput,
    ListMeetingsInput,
    SearchMeetingsInput,
    StatsInput,
)
from granola_mcp_server.tools import (
    export_markdown,
    get_meeting,
    list_meetings,
    meetings_stats,
    search_meetings,
)


def _mk_cache(tmp_path: Path) -> Path:
    inner = {
        "state": {
            "documents": {
                "e1": {
                    "id": "e1",
                    "title": "Interview Structure Overview",
                    "created_at": "2025-08-29T10:52:02Z",
                    "people": [{"name": "Alice"}, {"name": "Bob"}],
                    "notes_plain": "Notes",
                    "type": "meeting",
                },
                "e2": {
                    "id": "e2",
                    "title": "Another Meeting",
                    "created_at": "2025-08-30T10:00:00Z",
                    "people": [{"name": "Carol"}],
                    "type": "meeting",
                },
            },
            "meetingsMetadata": {
                "e1": {"conference": {"provider": "google_meet"}},
                "e2": {"conference": {"provider": "zoom"}},
            },
            "transcripts": {
                "e1": [
                    {"ts": "2025-08-29T10:52:05Z", "source": "Alice", "text": "Welcome"}
                ]
            },
        }
    }
    outer = {"cache": json.dumps(inner)}
    path = tmp_path / "cache-v3.json"
    path.write_text(json.dumps(outer), encoding="utf-8")
    return path


def test_list_and_get_and_export(tmp_path: Path) -> None:
    path = _mk_cache(tmp_path)
    config = AppConfig(cache_path=path)
    parser = GranolaParser(path)

    out = list_meetings(config, parser, ListMeetingsInput(limit=10))
    assert len(out.items) == 2

    got = get_meeting(config, parser, GetMeetingInput(id="e1", include=["transcript"]))
    assert got.meeting.id == "e1"
    assert got.transcript and len(got.transcript) == 1

    md = export_markdown(config, parser, ExportMarkdownInput(id="e1")).markdown
    assert "Interview Structure Overview" in md


def test_search_and_stats(tmp_path: Path) -> None:
    path = _mk_cache(tmp_path)
    config = AppConfig(cache_path=path)
    parser = GranolaParser(path)

    res = search_meetings(config, parser, SearchMeetingsInput(q="Interview"))
    assert len(res.items) == 1

    stats = meetings_stats(config, parser, StatsInput(group_by="day"))
    assert "by_period" in stats.counts
    assert len(stats.counts["by_period"]) >= 1
