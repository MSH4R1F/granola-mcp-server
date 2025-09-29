"""Error classes and helpers for the Granola MCP Server.

Defines structured exceptions matching the design document's error
model and a function to convert exceptions to serializable error
payloads suitable for tool responses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, TypedDict


class ErrorPayload(TypedDict, total=False):
    code: str
    message: str
    details: Dict[str, Any]


@dataclass
class AppError(Exception):
    """Base application error with a code and optional details."""

    code: str
    message: str
    details: Optional[Dict[str, Any]] = None

    def to_payload(self) -> ErrorPayload:
        payload: ErrorPayload = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


class BadRequestError(AppError):
    """Raised when a request is invalid or missing required parameters."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__("BAD_REQUEST", message, details)


class NotFoundError(AppError):
    """Raised when a requested resource cannot be found."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__("NOT_FOUND", message, details)


class IOErrorApp(AppError):
    """Raised for I/O errors, such as unreadable or missing cache files."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__("IO_ERROR", message, details)


class TimeoutErrorApp(AppError):
    """Raised when an operation exceeds its allowed time budget."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__("TIMEOUT", message, details)


class GranolaParseError(AppError):
    """Raised on invalid/missing fields, unreadable file, or JSON errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__("IO_ERROR", message, details)


def to_error_payload(
    error: Exception, *, path_hint: Optional[str] = None
) -> ErrorPayload:
    """Convert an exception into a structured error payload.

    Args:
        error: The exception to convert.
        path_hint: Optional file path that might help with diagnosis.

    Returns:
        A dictionary matching the error model spec.

    Examples:
        >>> try:
        ...     raise NotFoundError("Meeting not found", {"id": "abc"})
        ... except Exception as e:
        ...     payload = to_error_payload(e)
        ...     assert payload["code"] == "NOT_FOUND"
    """

    if isinstance(error, AppError):
        return error.to_payload()
    # Fallback: wrap generic exceptions
    details: Dict[str, Any] = {}
    if path_hint:
        details["path"] = path_hint
    return {"code": "IO_ERROR", "message": str(error), "details": details}
