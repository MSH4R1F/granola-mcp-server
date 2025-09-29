"""Factory for creating document sources based on configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..document_source import DocumentSource
from .local_file import LocalFileDocumentSource
from .remote_api import RemoteApiDocumentSource

if TYPE_CHECKING:
    from ..config import AppConfig


def create_document_source(config: AppConfig) -> DocumentSource:
    """Create a document source based on configuration.
    
    Args:
        config: Application configuration.
        
    Returns:
        DocumentSource implementation (local or remote).
        
    Raises:
        ValueError: If document_source is invalid or required config is missing.
    """
    source_type = config.document_source.lower()
    
    if source_type == "local":
        return LocalFileDocumentSource(config.cache_path)
    
    elif source_type == "remote":
        if not config.api_token:
            raise ValueError(
                "GRANOLA_API_TOKEN is required when using remote document source. "
                "Set it in your environment or .env file."
            )
        
        return RemoteApiDocumentSource(
            token=config.api_token,
            api_base=config.api_base,
            cache_dir=config.cache_dir,
            cache_ttl_seconds=config.cache_ttl_seconds if config.cache_enabled else 0,
        )
    
    else:
        raise ValueError(
            f"Invalid document_source: {source_type}. "
            "Must be 'local' or 'remote'."
        )
