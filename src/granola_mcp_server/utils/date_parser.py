"""Date/time parsing helpers.

Provides tolerant ISO 8601 parsing and normalization, including support
for 'Z' suffix normalization to '+00:00' and British timezone conversion.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo


def _replace_z_suffix(value: str) -> str:
    if value.endswith("Z"):
        return value[:-1] + "+00:00"
    return value


def parse_iso8601(value: str) -> datetime:
    """Parse an ISO 8601 string into a timezone-aware datetime.

    Accepts values ending with 'Z' by converting to '+00:00'.

    Raises:
        ValueError: If the timestamp cannot be parsed.
    """

    normalized = _replace_z_suffix(value)
    # Try fromisoformat which supports offsets like +00:00
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def ensure_iso8601(value: str) -> str:
    """Return a normalized ISO 8601 string with explicit offset.

    Example:
        >>> ensure_iso8601("2025-09-01T10:00:00Z")
        '2025-09-01T10:00:00+00:00'
    """

    return parse_iso8601(value).isoformat()


def to_british_time(value: str) -> datetime:
    """Convert ISO 8601 timestamp to British timezone (Europe/London).

    Automatically handles GMT/BST transitions based on the date.

    Args:
        value: ISO 8601 timestamp string.

    Returns:
        datetime object in British timezone.

    Example:
        >>> dt = to_british_time("2025-07-01T10:00:00Z")  # Summer (BST)
        >>> dt.strftime("%Y-%m-%d %H:%M:%S %Z")
        '2025-07-01 11:00:00 BST'
        >>> dt = to_british_time("2025-01-01T10:00:00Z")  # Winter (GMT)
        >>> dt.strftime("%Y-%m-%d %H:%M:%S %Z")
        '2025-01-01 10:00:00 GMT'
    """
    dt = parse_iso8601(value)
    british_tz = ZoneInfo("Europe/London")
    return dt.astimezone(british_tz)


def to_date_key(value: str, *, week: bool = False) -> str:
    """Convert ISO 8601 timestamp to a date or week key.

    Args:
        value: ISO 8601 timestamp.
        week: If true, returns YYYY-Www; otherwise YYYY-MM-DD.

    Returns:
        Aggregation key string for stats grouping.
    """

    dt = parse_iso8601(value).astimezone(timezone.utc)
    if week:
        iso_year, iso_week, _ = dt.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    return dt.date().isoformat()
