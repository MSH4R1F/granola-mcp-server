"""Granola cache parser (stdlib-only profile).

Implements the double-JSON parsing flow and utilities to extract
meetings and related metadata without any external dependencies.
The parser is read-only and does not modify the cache.

Public API:
    - GranolaParser

Usage example:
    parser = GranolaParser(cache_path="/path/to/cache-v3.json")
    meetings = parser.get_meetings()
    one = parser.get_meeting_by_id(meetings[0]["id"])  # dict form
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, TypedDict

from .errors import GranolaParseError
from .utils import ensure_iso8601

Platform = Literal["meet", "zoom", "teams", "other"]


class MeetingDict(TypedDict, total=False):
    """TypedDict for normalized meeting records."""

    id: str
    title: str
    start_ts: str
    end_ts: Optional[str]
    participants: List[str]
    platform: Optional[Platform]
    notes: Optional[str]
    overview: Optional[str]
    summary: Optional[str]
    folder_id: Optional[str]
    folder_name: Optional[str]


def _normalize_ts(value: Any) -> Optional[str]:
    """Normalize timestamp to ISO 8601 string.

    Handles strings, numbers (epoch seconds/ms), and None.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # Assume epoch seconds if reasonable, otherwise milliseconds
        if value > 1e10:  # milliseconds
            value = value / 1000
        dt = datetime.fromtimestamp(value, tz=timezone.utc)
        return dt.isoformat()
    if isinstance(value, str):
        try:
            return ensure_iso8601(value)
        except Exception:
            return value  # Return as-is if parsing fails
    return str(value)


@dataclass
class CacheState:
    state: Dict[str, Any]
    loaded_at: datetime

    @property
    def loaded_at_iso(self) -> str:
        """ISO 8601 formatted timestamp of when cache was loaded."""
        return self.loaded_at.isoformat()


class GranolaParser:
    """Parser for the Granola double-encoded JSON cache file.

    The outer file is a JSON object with a field `cache` that itself is
    a JSON string. This class performs double-decoding and exposes
    helper methods to extract normalized meeting records.

    Args:
        cache_path: Path to the cache file. If None, must be provided in
            `load_cache`.
    """

    def __init__(self, cache_path: Optional[str | Path] = None) -> None:
        self._cache_path: Optional[Path] = Path(cache_path) if cache_path else None
        self._cache: Optional[CacheState] = None

    @classmethod
    def from_path(cls, path: str | Path) -> GranolaParser:
        """Alternative constructor from a path."""
        return cls(cache_path=path)

    # ---------------------- Cache management ----------------------

    def load_cache(self, force_reload: bool = False) -> Dict[str, Any]:
        """Load and parse the cache file with double-JSON decoding.

        Args:
            force_reload: If true, bypass memoization and reload from disk.

        Returns:
            The inner decoded object (expected to contain `state`).

        Raises:
            GranolaParseError: If the file is unreadable or malformed.
        """

        if self._cache is not None and not force_reload:
            return self._cache.state

        if self._cache_path is None:
            raise GranolaParseError("Cache path not provided")

        path = self._cache_path
        if not path.exists() or not os.access(path, os.R_OK):
            raise GranolaParseError(
                f"Cache file not readable: {path}", {"path": str(path)}
            )

        try:
            with path.open("r", encoding="utf-8") as f:
                outer = json.load(f)
        except Exception as exc:  # pragma: no cover - filesystem errors
            raise GranolaParseError(
                "Failed to read outer JSON", {"path": str(path), "reason": str(exc)}
            ) from exc

        try:
            cache_field = outer["cache"]
            if isinstance(cache_field, str):
                inner = json.loads(cache_field)
            elif isinstance(cache_field, dict):
                inner = cache_field
            else:
                raise GranolaParseError(
                    f"Cache field is neither string nor dict: {type(cache_field)}",
                    {"path": str(path), "outer_keys": list(outer.keys())},
                )
        except KeyError as exc:
            raise GranolaParseError(
                "Missing 'cache' field in outer JSON",
                {"path": str(path), "outer_keys": list(outer.keys())},
            ) from exc
        except Exception as exc:
            raise GranolaParseError(
                "Failed to decode cache field", {"path": str(path), "reason": str(exc)}
            ) from exc

        if not isinstance(inner, dict):
            raise GranolaParseError(
                "Inner cache is not a dict",
                {"path": str(path), "inner_type": type(inner).__name__},
            )
        if "state" not in inner:
            raise GranolaParseError(
                "Inner JSON missing 'state' field",
                {"path": str(path), "inner_keys": list(inner.keys())},
            )

        self._cache = CacheState(state=inner, loaded_at=datetime.now(timezone.utc))
        return inner

    def reload(self) -> Dict[str, Any]:
        """Force reload the cache from disk."""

        return self.load_cache(force_reload=True)

    def validate_cache_structure(self) -> bool:
        """Quick health check for the cache structure.

        Returns:
            True if required keys exist.
        """
        try:
            inner = self.load_cache()
            state = inner.get("state", {})
            return isinstance(state, dict) and any(
                key in state for key in ("documents", "meetingsMetadata")
            )
        except Exception:
            return False

    def get_cache_info(self) -> Dict[str, Any]:
        """Return path, exists/readable, size, meeting_count, valid_structure."""

        if self._cache_path is None:
            raise GranolaParseError("Cache path not provided")
        path = self._cache_path
        exists = path.exists()
        size = path.stat().st_size if exists else 0
        valid = False
        meeting_count = 0
        last_loaded = None
        try:
            inner = self.load_cache()
            state = inner.get("state", {})
            valid = self.validate_cache_structure()
            if isinstance(state, dict):
                documents = state.get("documents", {})
                meeting_count = len(documents) if isinstance(documents, dict) else 0
            if self._cache is not None:
                last_loaded = self._cache.loaded_at_iso
        except Exception:
            pass

        return {
            "path": str(path),
            "exists": exists,
            "readable": os.access(path, os.R_OK),
            "size_bytes": size,
            "meeting_count": meeting_count,
            "valid_structure": valid,
            "last_loaded_ts": last_loaded,
        }

    # ---------------------- Meeting extraction ----------------------

    def get_meetings(self, debug: bool = False) -> List[MeetingDict]:
        """Extract normalized meetings from the cache.

        This combines `documents`, `meetingsMetadata`, `documentPanels`,
        and folder lists.

        Args:
            debug: If true, include select raw fields for troubleshooting.

        Returns:
            List of meeting dictionaries suitable for conversion to
            `MeetingSummary`/`Meeting` Pydantic models.
        """

        inner = self.load_cache()
        state = inner.get("state", {})
        if not isinstance(state, dict):
            return []

        documents = state.get("documents", {})
        metadata_map = state.get("meetingsMetadata", {})
        panels_map = state.get("documentPanels", {})
        lists_map = state.get("documentLists", {})
        lists_meta = state.get("documentListsMetadata", {})

        # Build reverse folder mapping: meeting_id -> (folder_id, folder_name)
        folder_map: Dict[str, Tuple[str, str]] = {}
        if isinstance(lists_map, dict) and isinstance(lists_meta, dict):
            for folder_id, ids in lists_map.items():
                if not isinstance(ids, list):
                    continue
                folder_meta = lists_meta.get(folder_id, {})
                folder_name = (
                    folder_meta.get("title") if isinstance(folder_meta, dict) else None
                )
                for meeting_id in ids:
                    folder_map[meeting_id] = (folder_id, folder_name)

        items: List[MeetingDict] = []
        if not isinstance(documents, dict):
            return items

        for doc_key, doc in documents.items():
            if not isinstance(doc, dict):
                continue
            if doc.get("type") and doc["type"] != "meeting":
                # Only surface meetings
                continue

            meeting_id = str(doc.get("id") or doc_key)
            title = doc.get("title") or "Untitled Meeting"
            created = doc.get("created_at")
            start_ts = _normalize_ts(created)

            # Participants: prefer documents[*].people[].name, de-dupe and preserve order
            participants: List[str] = []
            people = doc.get("people", [])
            if isinstance(people, list):
                seen = set()
                for person in people:
                    if isinstance(person, dict):
                        name = person.get("name")
                        if name and name not in seen:
                            participants.append(name)
                            seen.add(name)

            # Fallback to metadata attendees if no people found
            if not participants and isinstance(metadata_map, dict):
                meta = metadata_map.get(meeting_id, {})
                if isinstance(meta, dict):
                    attendees = meta.get("attendees", [])
                    if isinstance(attendees, list):
                        seen = set(participants)
                        for attendee in attendees:
                            if isinstance(attendee, dict):
                                name = attendee.get("name")
                                if name and name not in seen:
                                    participants.append(name)
                                    seen.add(name)

            # Platform detection
            platform: Optional[Platform] = None
            if isinstance(metadata_map, dict):
                meta = metadata_map.get(meeting_id, {})
                if isinstance(meta, dict):
                    conf = meta.get("conference")
                    if isinstance(conf, dict):
                        provider = conf.get("provider")
                        if provider == "google_meet":
                            platform = "meet"
                        elif provider in {"zoom", "teams"}:
                            platform = provider  # type: ignore[assignment]
                        elif provider:
                            platform = "other"

            notes = doc.get("notes_plain") or doc.get("notes_markdown")
            overview = doc.get("overview")
            summary = doc.get("summary")

            # Panels: capture first non-trivial original_content
            if not notes and isinstance(panels_map, dict):
                meeting_panels = panels_map.get(meeting_id, {})
                if isinstance(meeting_panels, dict):
                    for panel in meeting_panels.values():
                        if isinstance(panel, dict):
                            original = panel.get("original_content")
                            if original and isinstance(original, str):
                                original = original.strip()
                                if original and original != "<hr>":
                                    notes = original
                                    break

            folder_info = folder_map.get(meeting_id)
            folder_id = folder_info[0] if folder_info else None
            folder_name = folder_info[1] if folder_info else None

            item: MeetingDict = {
                "id": meeting_id,
                "title": title,
                "start_ts": start_ts or "",
                "end_ts": None,
                "participants": participants,
                "platform": platform,
                "notes": notes,
                "overview": overview,
                "summary": summary,
                "folder_id": folder_id,
                "folder_name": folder_name,
            }

            if debug:
                item["_raw_doc_keys"] = list(doc.keys())  # type: ignore[typeddict-item]

            items.append(item)

        # Sort by start_ts descending if available
        items.sort(key=lambda x: x.get("start_ts") or "", reverse=True)
        return items

    def get_meeting_by_id(self, meeting_id: str) -> Optional[MeetingDict]:
        """Return a single meeting dictionary by id, or None if not found."""

        for item in self.get_meetings():
            if item.get("id") == meeting_id:
                return item
        return None
