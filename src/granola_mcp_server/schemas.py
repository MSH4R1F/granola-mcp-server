"""Pydantic schemas for tool inputs and outputs.

These models define the stable JSON contracts used by the MCP tools.
They are designed to be backward-compatible for v1.x and include
docstring examples for clarity.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class MeetingSummary(BaseModel):
    """Summary view of a meeting.

    Attributes:
        id: Stable meeting identifier.
        title: Meeting title.
        start_ts: ISO 8601 start timestamp.
        end_ts: Optional ISO 8601 end timestamp.
        participants: List of participant display names.
        platform: Optional platform, e.g. 'zoom'|'meet'|'teams'|'other'.
        metadata: Bag for unknown/extra fields.
    """

    id: str
    title: str
    start_ts: str
    end_ts: Optional[str] = None
    participants: List[str] = Field(default_factory=list)
    platform: Optional[Literal["zoom", "meet", "teams", "other"]] = None
    metadata: Optional[Dict[str, object]] = None


class Meeting(MeetingSummary):
    """Full meeting record.

    Attributes:
        notes: Plaintext meeting notes if available.
        overview: Optional overview text.
        summary: Optional summary text.
        folder_id: Optional folder identifier.
        folder_name: Optional folder title.
    """

    notes: Optional[str] = None
    overview: Optional[str] = None
    summary: Optional[str] = None
    folder_id: Optional[str] = None
    folder_name: Optional[str] = None


# Inputs


class ListMeetingsInput(BaseModel):
    q: Optional[str] = None
    from_ts: Optional[str] = Field(default=None, description="ISO 8601 lower bound")
    to_ts: Optional[str] = Field(default=None, description="ISO 8601 upper bound")
    participants: Optional[List[str]] = None
    limit: Optional[int] = Field(default=50, ge=1, le=500)
    cursor: Optional[str] = None


class ListMeetingsOutput(BaseModel):
    items: List[MeetingSummary]
    next_cursor: Optional[str] = None


class GetMeetingInput(BaseModel):
    id: str
    include: Optional[List[Literal["notes", "metadata"]]] = None


class GetMeetingOutput(BaseModel):
    meeting: Meeting


class SearchFilters(BaseModel):
    participants: Optional[List[str]] = None
    platform: Optional[str] = None
    before: Optional[str] = None
    after: Optional[str] = None


class SearchMeetingsInput(BaseModel):
    q: str
    filters: Optional[SearchFilters] = None
    limit: Optional[int] = Field(default=50, ge=1, le=500)
    cursor: Optional[str] = None


class SearchMeetingsOutput(BaseModel):
    items: List[MeetingSummary]
    next_cursor: Optional[str] = None


class ExportMarkdownInput(BaseModel):
    id: str
    sections: Optional[List[Literal["header", "notes", "attendees", "links"]]] = None


class ExportMarkdownOutput(BaseModel):
    markdown: str


class StatsInput(BaseModel):
    window: Optional[Literal["7d", "30d", "90d"]] = None
    group_by: Optional[Literal["day", "week"]] = None


class StatsByPeriod(BaseModel):
    period: str
    meetings: int


class StatsOutput(BaseModel):
    counts: Dict[str, List[StatsByPeriod]]
    participants: Optional[List[Dict[str, object]]] = None


class CacheStatusOutput(BaseModel):
    path: str
    size_bytes: int
    last_loaded_ts: Optional[str] = None
    profile: Literal["stdlib", "sqlite"]
