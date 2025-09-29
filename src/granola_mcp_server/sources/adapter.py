"""Adapter to bridge DocumentSource with GranolaParser interface.

This adapter allows the existing tools and code that expect GranolaParser
to work seamlessly with any DocumentSource implementation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..document_source import DocumentSource
from ..parser import MeetingDict


class DocumentSourceAdapter:
    """Adapter that presents a DocumentSource as a parser-like interface.
    
    This allows existing code that expects GranolaParser methods to work
    with any DocumentSource implementation (local or remote).
    
    Args:
        source: The underlying document source.
    """

    def __init__(self, source: DocumentSource):
        self._source = source
        self._cache: Optional[Dict[str, Any]] = None
        self._loaded_at: Optional[datetime] = None

    def load_cache(self, force_reload: bool = False) -> Dict[str, Any]:
        """Load documents into a cache structure.
        
        This mimics the GranolaParser.load_cache() behavior but works
        with any document source.
        """
        if self._cache is not None and not force_reload:
            return self._cache
        
        # Fetch documents from source
        docs = self._source.get_documents(force=force_reload)
        
        # Convert list to dict keyed by id (matching cache-v3.json structure)
        documents_dict = {}
        for doc in docs:
            if isinstance(doc, dict):
                doc_id = doc.get("id")
                if doc_id:
                    documents_dict[str(doc_id)] = doc
        
        # Build cache structure matching cache-v3.json format
        self._cache = {
            "state": {
                "documents": documents_dict,
                # Note: Remote API might not provide these fields
                "meetingsMetadata": {},
                "documentPanels": {},
                "documentLists": {},
                "documentListsMetadata": {},
            }
        }
        self._loaded_at = datetime.now(timezone.utc)
        
        return self._cache

    def reload(self) -> Dict[str, Any]:
        """Force reload from source."""
        return self.load_cache(force_reload=True)

    def get_meetings(self, debug: bool = False) -> List[MeetingDict]:
        """Get meetings in the format expected by tools.
        
        This method converts raw documents into the normalized MeetingDict
        format that the existing tools expect.
        """
        cache = self.load_cache()
        state = cache.get("state", {})
        documents = state.get("documents", {})
        
        meetings: List[MeetingDict] = []
        
        if not isinstance(documents, dict):
            return meetings
        
        for doc_key, doc in documents.items():
            if not isinstance(doc, dict):
                continue
            
            # Only include meetings (skip if type field exists and isn't "meeting")
            doc_type = doc.get("type")
            if doc_type and doc_type != "meeting":
                continue
            
            meeting_id = str(doc.get("id") or doc_key)
            title = doc.get("title") or "Untitled Meeting"
            
            # Extract timestamp - handle both API and cache formats
            start_ts = doc.get("created_at") or doc.get("start_ts") or ""
            if not isinstance(start_ts, str):
                start_ts = str(start_ts) if start_ts else ""
            
            # Extract participants from people array
            participants: List[str] = []
            people = doc.get("people")
            if isinstance(people, dict):
                # Cache format: people object with creator/attendees
                creator = people.get("creator", {})
                if isinstance(creator, dict):
                    creator_name = creator.get("name") or creator.get("email")
                    if creator_name:
                        participants.append(str(creator_name))
                
                attendees = people.get("attendees", [])
                if isinstance(attendees, list):
                    for att in attendees:
                        if isinstance(att, dict):
                            att_name = att.get("name") or att.get("email")
                            if att_name and att_name not in participants:
                                participants.append(str(att_name))
            
            # Extract notes from various possible fields
            notes = (
                doc.get("notes_plain")
                or doc.get("notes_markdown")
                or doc.get("notes")
            )
            if isinstance(notes, dict):
                # If notes is structured (ProseMirror), try to extract plain text
                notes = None  # Will need to handle structured notes separately
            
            meeting: MeetingDict = {
                "id": meeting_id,
                "title": title,
                "start_ts": start_ts,
                "end_ts": None,
                "participants": participants,
                "platform": None,  # Platform detection would need google_calendar_event
                "notes": notes if isinstance(notes, str) else None,
                "overview": doc.get("overview") if isinstance(doc.get("overview"), str) else None,
                "summary": doc.get("summary") if isinstance(doc.get("summary"), str) else None,
                "folder_id": None,
                "folder_name": None,
            }
            
            meetings.append(meeting)
        
        # Sort by start_ts descending
        meetings.sort(key=lambda x: x.get("start_ts") or "", reverse=True)
        
        return meetings

    def get_meeting_by_id(self, meeting_id: str) -> Optional[MeetingDict]:
        """Get a single meeting by ID."""
        for meeting in self.get_meetings():
            if meeting.get("id") == meeting_id:
                return meeting
        return None

    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information from the underlying source."""
        info = self._source.get_cache_info()
        
        # Add adapter-specific info
        if self._loaded_at:
            info["last_loaded_ts"] = self._loaded_at.isoformat()
        
        # Count meetings if cache is loaded
        if self._cache:
            state = self._cache.get("state", {})
            documents = state.get("documents", {})
            info["meeting_count"] = len(documents) if isinstance(documents, dict) else 0
            info["valid_structure"] = True
        
        return info

    def validate_cache_structure(self) -> bool:
        """Validate that the cache structure is valid."""
        try:
            cache = self.load_cache()
            state = cache.get("state", {})
            return isinstance(state, dict) and "documents" in state
        except Exception:
            return False

    def refresh_cache(self) -> None:
        """Refresh the cache from the source."""
        self._source.refresh_cache()
        self._cache = None
        self._loaded_at = None
