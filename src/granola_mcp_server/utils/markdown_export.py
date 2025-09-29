"""Markdown export helpers.

Generates deterministic Markdown for meetings, suitable for diffs.
"""

from __future__ import annotations

from typing import List, Optional

from ..schemas import Meeting


def _format_attendees(attendees: List[str]) -> str:
    """Format attendees list as Markdown bullet points."""
    return "\n".join(f"- {name}" for name in attendees)


def render_meeting_markdown(
    meeting: Meeting,
    *,
    sections: Optional[List[str]] = None,
) -> str:
    """Render a meeting into Markdown.

    Args:
        meeting: Full meeting record.
        sections: Optional subset of sections to include.

    Returns:
        Markdown string.
    """
    selected = set(sections or ["header", "attendees", "notes"])  # default
    parts: List[str] = []

    if "header" in selected:
        parts.append(f"# {meeting.title}")
        parts.append("")
        parts.append(f"- ID: `{meeting.id}`")
        parts.append(
            f"- When: {meeting.start_ts}{' → ' + meeting.end_ts if meeting.end_ts else ''}"
        )
        if meeting.platform:
            parts.append(f"- Platform: {meeting.platform}")
        if meeting.folder_name:
            parts.append(f"- Folder: {meeting.folder_name}")
        parts.append("")

    if "attendees" in selected:
        parts.append("## Attendees")
        parts.append(_format_attendees(meeting.participants))
        parts.append("")

    if "notes" in selected and meeting.notes:
        parts.append("## Notes")
        parts.append(meeting.notes)
        parts.append("")

    return "\n".join(parts).strip() + "\n"
