"""Tests for the stdlib-only GranolaParser."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from granola_mcp_server.parser import GranolaParser


def make_double_json_cache(tmp_path: Path) -> Path:
    inner = {
        "state": {
            "documents": {
                "e1": {
                    "id": "e1",
                    "title": "Test Meeting",
                    "created_at": "2025-09-01T10:00:00Z",
                    "people": [{"name": "Alice"}, {"name": "Bob"}],
                    "notes_plain": "Notes here",
                    "type": "meeting",
                }
            },
            "meetingsMetadata": {
                "e1": {
                    "conference": {
                        "provider": "google_meet",
                        "url": "https://meet.google.com/x",
                    }
                }
            },
            "transcripts": {
                "e1": [
                    {"ts": "2025-09-01T10:00:05Z", "source": "Alice", "text": "Hello"},
                    {"ts": "2025-09-01T10:00:06Z", "source": "Alice", "text": "World"},
                    {"ts": "2025-09-01T10:00:10Z", "source": "Bob", "text": "Reply"},
                ]
            },
            "documentLists": {"L1": ["e1"]},
            "documentListsMetadata": {"L1": {"title": "Folder A"}},
        }
    }
    outer = {"cache": json.dumps(inner)}
    path = tmp_path / "cache-v3.json"
    path.write_text(json.dumps(outer), encoding="utf-8")
    return path


def test_load_and_list_meetings(tmp_path: Path) -> None:
    path = make_double_json_cache(tmp_path)
    parser = GranolaParser(path)
    meetings = parser.get_meetings()
    assert len(meetings) == 1
    m = meetings[0]
    assert m["id"] == "e1"
    assert m["title"] == "Test Meeting"
    assert m["participants"] == ["Alice", "Bob"]
    assert m["platform"] == "meet"
    assert m["folder_name"] == "Folder A"
    assert m["has_transcript"] is True


def test_get_meeting_by_id_and_transcript(tmp_path: Path) -> None:
    path = make_double_json_cache(tmp_path)
    parser = GranolaParser(path)
    m = parser.get_meeting_by_id("e1")
    assert m and m["id"] == "e1"
    turns = parser.build_transcript_turns("e1")
    # Alice's two adjacent segments should be coalesced
    assert len(turns) == 2
    assert turns[0]["speaker"] == "Alice"
    assert "Hello World" in turns[0]["text"]
