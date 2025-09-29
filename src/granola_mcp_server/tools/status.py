"""Cache status tool function."""

from __future__ import annotations

import os
from typing import Optional

from ..config import AppConfig
from ..parser import GranolaParser
from ..schemas import CacheStatusOutput


def cache_status(
    config: AppConfig, parser: Optional[GranolaParser]
) -> CacheStatusOutput:
    """Report cache path, size, last load time, and active profile."""

    parser = parser or GranolaParser(config.cache_path)
    info = parser.get_cache_info()
    profile = "sqlite" if config.use_sqlite else "stdlib"
    return CacheStatusOutput(
        path=str(config.cache_path),
        size_bytes=int(info.get("size_bytes") or 0),
        last_loaded_ts=info.get("last_loaded_ts"),
        profile=profile,  # type: ignore[arg-type]
    )
