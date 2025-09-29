"""Local file-based document source.

Wraps the existing GranolaParser to provide the DocumentSource interface
for local cache files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from ..document_source import DocumentSource
from ..parser import GranolaParser


class LocalFileDocumentSource(DocumentSource):
    """Document source that reads from local Granola cache files.
    
    This implementation wraps the existing GranolaParser and provides
    the DocumentSource interface for backward compatibility.
    
    Args:
        cache_path: Path to the local cache file (cache-v3.json).
    """

    def __init__(self, cache_path: str | Path):
        self._parser = GranolaParser(cache_path)

    def get_documents(
        self,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        include_last_viewed_panel: bool = True,
        force: bool = False,
    ) -> List[Dict[str, object]]:
        """Fetch documents from local cache file.
        
        Note: limit, offset, and include_last_viewed_panel are accepted for
        interface compatibility but don't affect the local file read since
        the entire cache is always loaded.
        """
        if force:
            self._parser.reload()
        
        cache_data = self._parser.load_cache()
        state = cache_data.get("state", {})
        documents = state.get("documents", {})
        
        # Convert documents dict to list format
        docs_list = []
        if isinstance(documents, dict):
            for doc_id, doc in documents.items():
                if isinstance(doc, dict):
                    # Ensure id field is set
                    if "id" not in doc:
                        doc["id"] = doc_id
                    docs_list.append(doc)
        
        # Apply pagination if specified
        if offset is not None:
            docs_list = docs_list[offset:]
        if limit is not None:
            docs_list = docs_list[:limit]
            
        return docs_list

    def get_document_by_id(
        self, doc_id: str, *, force: bool = False
    ) -> Optional[Dict[str, object]]:
        """Fetch a single document by ID from local cache."""
        if force:
            self._parser.reload()
            
        cache_data = self._parser.load_cache()
        state = cache_data.get("state", {})
        documents = state.get("documents", {})
        
        if isinstance(documents, dict):
            doc = documents.get(doc_id)
            if isinstance(doc, dict):
                if "id" not in doc:
                    doc["id"] = doc_id
                return doc
        
        return None

    def refresh_cache(self) -> None:
        """Force reload from local file."""
        self._parser.reload()

    def get_cache_info(self) -> Dict[str, object]:
        """Get local cache file information."""
        return self._parser.get_cache_info()
    
    @property
    def parser(self) -> GranolaParser:
        """Access the underlying parser for backward compatibility."""
        return self._parser
