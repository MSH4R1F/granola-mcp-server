"""Meetings-related tool functions.

These functions implement the read-only meetings surface:
list, get, search, export markdown, and basic stats.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Union

from ..config import AppConfig
from ..errors import BadRequestError, NotFoundError
from ..parser import GranolaParser
from ..sources.adapter import DocumentSourceAdapter
from ..schemas import (
    ExportMarkdownInput,
    ExportMarkdownOutput,
    GetMeetingInput,
    GetMeetingOutput,
    ListMeetingsInput,
    ListMeetingsOutput,
    Meeting,
    MeetingSummary,
    SearchMeetingsInput,
    SearchMeetingsOutput,
    StatsByPeriod,
    StatsInput,
    StatsOutput,
)
from ..utils import ensure_iso8601, render_meeting_markdown, to_date_key


def _paginate(
    items: List[MeetingSummary], *, limit: int, cursor: Optional[str]
) -> (List[MeetingSummary], Optional[str]):
    start = int(cursor or 0)
    end = start + limit
    next_cursor = str(end) if end < len(items) else None
    return items[start:end], next_cursor


def _to_summary(item: Dict[str, object]) -> MeetingSummary:
    return MeetingSummary(
        id=str(item.get("id")),
        title=str(item.get("title") or "Untitled Meeting"),
        start_ts=str(item.get("start_ts") or ""),
        end_ts=item.get("end_ts") if isinstance(item.get("end_ts"), str) else None,
        participants=[str(p) for p in (item.get("participants") or [])],
        platform=(
            item.get("platform") if isinstance(item.get("platform"), str) else None
        ),
        metadata=None,
    )


def _to_meeting(item: Dict[str, object]) -> Meeting:
    base = _to_summary(item).model_dump()
    return Meeting(
        **base,
        notes=item.get("notes") if isinstance(item.get("notes"), str) else None,
        overview=(
            item.get("overview") if isinstance(item.get("overview"), str) else None
        ),
        summary=item.get("summary") if isinstance(item.get("summary"), str) else None,
        folder_id=(
            item.get("folder_id") if isinstance(item.get("folder_id"), str) else None
        ),
        folder_name=(
            item.get("folder_name")
            if isinstance(item.get("folder_name"), str)
            else None
        ),
    )


def list_meetings(
    config: AppConfig,
    parser: Optional[Union[GranolaParser, DocumentSourceAdapter]],
    params: ListMeetingsInput,
) -> ListMeetingsOutput:
    """List meetings with basic filtering and pagination."""

    if parser is None:
        parser = GranolaParser(config.cache_path)
    raw_items = parser.get_meetings()

    # Filters
    def matches(item: Dict[str, object]) -> bool:
        if params.q:
            q = params.q.lower()
            hay = f"{item.get('title','')} {item.get('notes','')} {' '.join(item.get('participants') or [])}".lower()
            if q not in hay:
                return False
        if params.participants:
            want = {p.lower() for p in params.participants}
            have = {str(p).lower() for p in (item.get("participants") or [])}
            if not want.intersection(have):
                return False
        if params.from_ts:
            try:
                if str(item.get("start_ts") or "") < ensure_iso8601(params.from_ts):
                    return False
            except Exception:
                pass
        if params.to_ts:
            try:
                if str(item.get("start_ts") or "") > ensure_iso8601(params.to_ts):
                    return False
            except Exception:
                pass
        return True

    summaries = [_to_summary(i) for i in raw_items if matches(i)]
    limit = params.limit or 50
    page, next_cursor = _paginate(summaries, limit=limit, cursor=params.cursor)
    return ListMeetingsOutput(items=page, next_cursor=next_cursor)


def get_meeting(
    config: AppConfig,
    parser: Optional[Union[GranolaParser, DocumentSourceAdapter]],
    params: GetMeetingInput,
) -> GetMeetingOutput:
    """Get a full meeting by id."""

    if not params.id:
        raise BadRequestError("'id' is required")
    if parser is None:
        parser = GranolaParser(config.cache_path)
    item = parser.get_meeting_by_id(params.id)
    if not item:
        raise NotFoundError("Meeting not found", {"id": params.id})

    meeting = _to_meeting(item)
    return GetMeetingOutput(meeting=meeting)


def search_meetings(
    config: AppConfig,
    parser: Optional[Union[GranolaParser, DocumentSourceAdapter]],
    params: SearchMeetingsInput,
) -> SearchMeetingsOutput:
    """Linear search across titles, notes, participants (stdlib path)."""

    if parser is None:
        parser = GranolaParser(config.cache_path)
    raw_items = parser.get_meetings()

    q = (params.q or "").lower()

    def matches(item: Dict[str, object]) -> bool:
        hay = f"{item.get('title','')} {item.get('notes','')} {' '.join(item.get('participants') or [])}".lower()
        if q not in hay:
            return False
        if params.filters:
            if params.filters.participants:
                want = {p.lower() for p in params.filters.participants}
                have = {str(p).lower() for p in (item.get("participants") or [])}
                if not want.intersection(have):
                    return False
            if (
                params.filters.platform
                and str(item.get("platform") or "").lower()
                != params.filters.platform.lower()
            ):
                return False
            if params.filters.after:
                try:
                    if str(item.get("start_ts") or "") < ensure_iso8601(
                        params.filters.after
                    ):
                        return False
                except Exception:
                    pass
            if params.filters.before:
                try:
                    if str(item.get("start_ts") or "") > ensure_iso8601(
                        params.filters.before
                    ):
                        return False
                except Exception:
                    pass
        return True

    summaries = [_to_summary(i) for i in raw_items if matches(i)]
    limit = params.limit or 50
    page, next_cursor = _paginate(summaries, limit=limit, cursor=params.cursor)
    return SearchMeetingsOutput(items=page, next_cursor=next_cursor)


def export_markdown(
    config: AppConfig,
    parser: Optional[Union[GranolaParser, DocumentSourceAdapter]],
    params: ExportMarkdownInput,
) -> ExportMarkdownOutput:
    """Export meeting as Markdown with optional sections."""

    if not params.id:
        raise BadRequestError("'id' is required")
    if parser is None:
        parser = GranolaParser(config.cache_path)
    item = parser.get_meeting_by_id(params.id)
    if not item:
        raise NotFoundError("Meeting not found", {"id": params.id})
    meeting = _to_meeting(item)
    md = render_meeting_markdown(meeting, sections=params.sections)
    return ExportMarkdownOutput(markdown=md)


def meetings_stats(
    config: AppConfig,
    parser: Optional[Union[GranolaParser, DocumentSourceAdapter]],
    params: StatsInput,
) -> StatsOutput:
    """Compute simple counts grouped by day or week over a time window."""

    if parser is None:
        parser = GranolaParser(config.cache_path)
    items = parser.get_meetings()

    group_by = params.group_by or "day"
    week = group_by == "week"

    # TODO: Implement time window filtering per `window`; for now include all.
    counts: Dict[str, int] = {}
    for it in items:
        key = to_date_key(str(it.get("start_ts") or ""), week=week)
        counts[key] = counts.get(key, 0) + 1

    series = [StatsByPeriod(period=k, meetings=v) for k, v in sorted(counts.items())]
    return StatsOutput(counts={"by_period": series}, participants=None)
