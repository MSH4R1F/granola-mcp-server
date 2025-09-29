"""Document source abstraction layer.

Provides pluggable implementations for fetching documents from different
sources (local file, remote API) with a unified interface. This enables
web deployment scenarios where local file access is not available.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterable, Dict, List, Optional


class DocumentSource(ABC):
    """Abstract interface for document sources.
    
    Implementations can fetch documents from local files, remote APIs,
    or other sources. The interface is designed to support both sync
    and async iteration patterns.
    """

    @abstractmethod
    def get_documents(
        self,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        include_last_viewed_panel: bool = True,
        force: bool = False,
    ) -> List[Dict[str, object]]:
        """Fetch documents synchronously.
        
        Args:
            limit: Maximum number of documents to return.
            offset: Offset for pagination.
            include_last_viewed_panel: Whether to include last viewed panel data.
            force: Force refresh, bypassing cache.
            
        Returns:
            List of document dictionaries from the Granola API format.
        """
        pass

    @abstractmethod
    def get_document_by_id(
        self, doc_id: str, *, force: bool = False
    ) -> Optional[Dict[str, object]]:
        """Fetch a single document by ID.
        
        Args:
            doc_id: Document identifier.
            force: Force refresh, bypassing cache.
            
        Returns:
            Document dictionary or None if not found.
        """
        pass

    @abstractmethod
    def refresh_cache(self) -> None:
        """Manually refresh the cache.
        
        This method forces a reload from the source and updates any
        internal caches. Useful for implementing manual refresh controls.
        """
        pass

    @abstractmethod
    def get_cache_info(self) -> Dict[str, object]:
        """Get information about the cache state.
        
        Returns:
            Dictionary with cache metadata (size, age, path, etc.).
        """
        pass
