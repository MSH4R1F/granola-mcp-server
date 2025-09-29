"""Environment configuration for the Granola MCP Server.

- Stdlib-first defaults; optional SQLite index.
- Local-only and read-only in v1.
Now when you run the server, you can use the following environment variables to configure the server:

```

```bash
export GRANOLA_CACHE_PATH="~/Library/Application Support/Granola/cache-v3.json"
export GRANOLA_STDLIB_ONLY=true
export GRANOLA_USE_SQLITE=false
```
these are rendered to the AppConfig class and can be accessed like this:
```python
from granola_mcp_server.config import load_config
cfg = load_config()
print(cfg.cache_path)
```



"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _expand_path(p: str | Path | None) -> Path | None:
    """Expand ~ and environment variables in a path-like value."""
    if p is None:
        return None
    if isinstance(p, Path):
        s = str(p)
    else:
        s = p
    return Path(os.path.expanduser(os.path.expandvars(s)))


class AppConfig(BaseSettings):
    """Application configuration settings loaded from environment variables.

    All environment variables are prefixed with GRANOLA_ (e.g., GRANOLA_CACHE_PATH).
    Paths are automatically expanded to resolve ~ and environment variables.
    """

    # ---- core storage / cache ----
    cache_path: Path = Field(
        default="~/Library/Application Support/Granola/cache-v3.json",
        description="Path to the Granola cache file containing meeting data",
    )
    use_sqlite: bool = Field(
        default=False,
        description="Enable SQLite database for indexing and search capabilities",
    )
    db_path: Path = Field(
        default="~/.granola/granola.db", description="Path to the SQLite database file"
    )

    # ---- behavior ----
    stdlib_only: bool = Field(
        default=True,
        description="Forces stdlib-only mode; disables SQLite usage when True",
    )

    # ---- experimental hybrid (disabled by default) ----
    net_enabled: bool = Field(
        default=False,
        description="Enable network features for hybrid mode (experimental)",
    )
    supabase_config: Optional[Path] = Field(
        default=None, description="Path to Supabase configuration file for hybrid mode"
    )
    base_url: Optional[str] = Field(
        default=None, description="Base URL for network requests in hybrid mode"
    )

    # ---- network tuning ----
    timeout_seconds: int = Field(
        default=15, description="Network request timeout in seconds"
    )
    max_retries: int = Field(
        default=3, description="Maximum number of retry attempts for network requests"
    )

    # pydantic-settings v2 config
    model_config = SettingsConfigDict(
        env_prefix="GRANOLA_",
        case_sensitive=False,
        env_file=(".env",),  # will read if present
        env_file_encoding="utf-8",
        frozen=True,  # make settings immutable
    )

    # ---- validators ----
    @field_validator("cache_path", "db_path", "supabase_config", mode="before")
    @classmethod
    def _expand_all_paths(cls, v):
        return _expand_path(v)

    # ---- derived conveniences (no mutation) ----
    @property
    def effective_use_sqlite(self) -> bool:
        """True when SQLite should actually be used, respecting stdlib_only."""
        return self.use_sqlite and not self.stdlib_only


def load_config() -> AppConfig:
    """Load and validate application configuration from environment variables.

    • All variables are prefixed with GRANOLA_ (e.g., GRANOLA_CACHE_PATH).
    • Missing values fall back to the documented defaults.
    • Paths expand ~ and ${VARS}.
    """
    return AppConfig()
