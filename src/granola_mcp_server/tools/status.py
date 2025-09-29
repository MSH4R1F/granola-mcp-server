"""Cache status tool function."""

from __future__ import annotations

import os
from typing import Optional, Union

from ..config import AppConfig
from ..parser import GranolaParser
from ..sources.adapter import DocumentSourceAdapter
from ..schemas import CacheStatusOutput


def cache_status(
    config: AppConfig, parser: Optional[Union[GranolaParser, DocumentSourceAdapter]]
) -> CacheStatusOutput:
    """Report cache path, size, last load time, and active profile."""

    if parser is None:
        parser = GranolaParser(config.cache_path)
    info = parser.get_cache_info()
    
    # Determine path and profile based on source type
    if config.document_source == "remote":
        path = info.get("cache_dir", "N/A")
        profile = "stdlib"  # Remote uses stdlib (no sqlite)
    else:
        path = str(config.cache_path)
        profile = "sqlite" if config.use_sqlite else "stdlib"
    
    return CacheStatusOutput(
        path=str(path),
        size_bytes=int(info.get("size_bytes") or info.get("total_cache_size_bytes") or 0),
        last_loaded_ts=info.get("last_loaded_ts") or info.get("oldest_cache_ts"),
        profile=profile,  # type: ignore[arg-type]
    )
