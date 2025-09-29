"""Remote API-based document source.

Fetches documents directly from the Granola API using token authentication.
Handles gzip decompression and caching of the decompressed JSON.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib import request
from urllib.error import HTTPError, URLError

from ..errors import GranolaParseError
from ..document_source import DocumentSource


class RemoteApiDocumentSource(DocumentSource):
    """Document source that fetches from the Granola API.
    
    Features:
    - Token-based authentication
    - Gzip decompression of responses
    - Local caching of decompressed JSON
    - TTL-based cache invalidation
    - Retry logic with exponential backoff
    
    Args:
        token: Bearer token for API authentication.
        api_base: Base URL for the Granola API.
        cache_dir: Directory for storing decompressed cache files.
        cache_ttl_seconds: Time-to-live for cached data (default 24h).
    """

    def __init__(
        self,
        token: str,
        api_base: str = "https://api.granola.ai",
        cache_dir: Optional[str | Path] = None,
        cache_ttl_seconds: int = 86400,  # 24 hours
    ):
        self.token = token
        self.api_base = api_base.rstrip("/")
        self.cache_ttl = cache_ttl_seconds
        
        # Set up cache directory
        if cache_dir is None:
            cache_dir = Path.home() / ".granola" / "remote_cache"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def _get_cache_key(
        self,
        limit: Optional[int],
        offset: Optional[int],
        include_last_viewed_panel: bool,
    ) -> str:
        """Generate cache key for request parameters."""
        params = f"{limit}:{offset}:{include_last_viewed_panel}"
        return hashlib.sha256(params.encode()).hexdigest()[:16]
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path for a cache key."""
        return self.cache_dir / f"docs_{cache_key}.json"
    
    def _is_cache_fresh(self, cache_path: Path) -> bool:
        """Check if cache file is within TTL."""
        if not cache_path.exists():
            return False
        
        age = time.time() - cache_path.stat().st_mtime
        return age < self.cache_ttl
    
    def _read_cache(self, cache_path: Path) -> Optional[Dict[str, object]]:
        """Read from cache file."""
        if not cache_path.exists():
            return None
        
        try:
            with cache_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    
    def _write_cache(self, cache_path: Path, data: Dict[str, object]) -> None:
        """Write to cache file."""
        try:
            with cache_path.open("w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception as e:
            # Non-fatal: cache write failures shouldn't break the request
            print(f"Warning: Failed to write cache: {e}")
    
    def _fetch_from_api(
        self,
        limit: int = 100,
        offset: int = 0,
        include_last_viewed_panel: bool = True,
    ) -> Dict[str, object]:
        """Fetch documents from the Granola API.
        
        Returns:
            Parsed JSON response after gzip decompression.
            
        Raises:
            GranolaParseError: For network or parsing errors.
        """
        url = f"{self.api_base}/v2/get-documents"
        
        payload = json.dumps({
            "limit": limit,
            "offset": offset,
            "include_last_viewed_panel": include_last_viewed_panel,
        }).encode("utf-8")
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "*/*",
            "User-Agent": "Granola-MCP-Server/0.1.0",
        }
        
        req = request.Request(url, data=payload, headers=headers, method="POST")
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with request.urlopen(req, timeout=30) as response:
                    # Read gzipped response
                    compressed_data = response.read()
                    
                    # Decompress
                    try:
                        decompressed_data = gzip.decompress(compressed_data)
                    except Exception as e:
                        raise GranolaParseError(
                            f"Failed to decompress response: {e}",
                            {"attempt": attempt + 1}
                        ) from e
                    
                    # Parse JSON
                    try:
                        data = json.loads(decompressed_data.decode("utf-8"))
                        return data
                    except Exception as e:
                        raise GranolaParseError(
                            f"Failed to parse JSON: {e}",
                            {"attempt": attempt + 1}
                        ) from e
                        
            except HTTPError as e:
                error_code = e.code
                error_body = e.read().decode("utf-8", errors="replace")
                
                if error_code == 401:
                    raise GranolaParseError(
                        "Invalid or expired token. Please reauthenticate.",
                        {"status": 401}
                    ) from e
                elif error_code == 403:
                    raise GranolaParseError(
                        "Access forbidden. Check your token permissions.",
                        {"status": 403}
                    ) from e
                elif error_code == 429:
                    # Rate limited - retry with backoff
                    if attempt < max_retries - 1:
                        wait = (2 ** attempt) * 1.0  # Exponential backoff
                        time.sleep(wait)
                        continue
                    raise GranolaParseError(
                        "Rate limit exceeded. Please try again later.",
                        {"status": 429, "attempt": attempt + 1}
                    ) from e
                elif 500 <= error_code < 600:
                    # Server error - retry
                    if attempt < max_retries - 1:
                        wait = (2 ** attempt) * 1.0
                        time.sleep(wait)
                        continue
                    raise GranolaParseError(
                        f"Server error: {error_code}",
                        {"status": error_code, "body": error_body, "attempt": attempt + 1}
                    ) from e
                else:
                    raise GranolaParseError(
                        f"HTTP error: {error_code}",
                        {"status": error_code, "body": error_body}
                    ) from e
                    
            except URLError as e:
                if attempt < max_retries - 1:
                    wait = (2 ** attempt) * 1.0
                    time.sleep(wait)
                    continue
                raise GranolaParseError(
                    f"Network error: {e.reason}",
                    {"attempt": attempt + 1}
                ) from e
                
            except Exception as e:
                raise GranolaParseError(
                    f"Unexpected error: {e}",
                    {"attempt": attempt + 1}
                ) from e
        
        raise GranolaParseError("Failed after max retries")

    def get_documents(
        self,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        include_last_viewed_panel: bool = True,
        force: bool = False,
    ) -> List[Dict[str, object]]:
        """Fetch documents from API with caching.
        
        Args:
            limit: Maximum documents to fetch (default 100).
            offset: Pagination offset (default 0).
            include_last_viewed_panel: Include panel data.
            force: Bypass cache and fetch fresh data.
            
        Returns:
            List of document dictionaries.
        """
        limit = limit or 100
        offset = offset or 0
        
        # Check cache first
        cache_key = self._get_cache_key(limit, offset, include_last_viewed_panel)
        cache_path = self._get_cache_path(cache_key)
        
        if not force and self._is_cache_fresh(cache_path):
            cached = self._read_cache(cache_path)
            if cached is not None:
                docs = cached.get("docs", [])
                if isinstance(docs, list):
                    return docs
        
        # Fetch from API
        data = self._fetch_from_api(limit, offset, include_last_viewed_panel)
        
        # Cache the response
        self._write_cache(cache_path, data)
        
        # Extract documents
        docs = data.get("docs", [])
        if not isinstance(docs, list):
            raise GranolaParseError(
                "Invalid response format: 'docs' field is not a list"
            )
        
        return docs

    def get_document_by_id(
        self, doc_id: str, *, force: bool = False
    ) -> Optional[Dict[str, object]]:
        """Fetch a single document by ID.
        
        Note: This implementation fetches all documents and filters.
        A more efficient implementation would use a dedicated endpoint.
        """
        docs = self.get_documents(force=force)
        for doc in docs:
            if isinstance(doc, dict) and doc.get("id") == doc_id:
                return doc
        return None

    def refresh_cache(self) -> None:
        """Clear all cache files to force refresh on next request."""
        for cache_file in self.cache_dir.glob("docs_*.json"):
            try:
                cache_file.unlink()
            except Exception:
                pass

    def get_cache_info(self) -> Dict[str, object]:
        """Get information about the remote cache state."""
        cache_files = list(self.cache_dir.glob("docs_*.json"))
        total_size = sum(f.stat().st_size for f in cache_files)
        
        oldest_cache = None
        if cache_files:
            oldest = min(cache_files, key=lambda f: f.stat().st_mtime)
            oldest_cache = datetime.fromtimestamp(
                oldest.stat().st_mtime, tz=timezone.utc
            ).isoformat()
        
        return {
            "source": "remote_api",
            "api_base": self.api_base,
            "cache_dir": str(self.cache_dir),
            "cache_files_count": len(cache_files),
            "total_cache_size_bytes": total_size,
            "cache_ttl_seconds": self.cache_ttl,
            "oldest_cache_ts": oldest_cache,
        }
