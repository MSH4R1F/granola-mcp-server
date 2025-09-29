"""Refresh tool for manual cache updates."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..schemas import RefreshCacheInput, RefreshCacheOutput

if TYPE_CHECKING:
    from ..config import AppConfig
    from ..sources.adapter import DocumentSourceAdapter


def refresh_cache(
    config: AppConfig,
    adapter: DocumentSourceAdapter,
    params: RefreshCacheInput,
) -> RefreshCacheOutput:
    """Manually refresh the document cache.
    
    This tool forces a fresh fetch from the document source, bypassing
    any TTL or cache logic. Useful for ensuring you have the latest data.
    
    Args:
        config: Application configuration.
        adapter: Document source adapter.
        params: Refresh parameters.
        
    Returns:
        Status and metadata about the refresh operation.
    """
    try:
        # Clear and reload cache
        adapter.refresh_cache()
        adapter.reload()
        
        # Get updated cache info
        info = adapter.get_cache_info()
        
        return RefreshCacheOutput(
            success=True,
            message="Cache refreshed successfully",
            meeting_count=info.get("meeting_count", 0),
            cache_info=info,
        )
    except Exception as e:
        return RefreshCacheOutput(
            success=False,
            message=f"Failed to refresh cache: {str(e)}",
            meeting_count=0,
            cache_info={},
        )
