"""Example: Using the Remote API Document Source

This script demonstrates how to use the remote document source
to fetch documents from the Granola API.
"""

import os
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from granola_mcp_server.config import AppConfig
from granola_mcp_server.sources import create_document_source
from granola_mcp_server.sources.adapter import DocumentSourceAdapter


def main():
    """Example usage of remote document source."""
    
    # Check if token is set
    token = os.getenv("GRANOLA_API_TOKEN")
    if not token:
        print("❌ Error: GRANOLA_API_TOKEN environment variable not set")
        print("\nTo use remote mode:")
        print("  export GRANOLA_API_TOKEN=your_token_here")
        print("  python examples/remote_source_example.py")
        sys.exit(1)
    
    print("🚀 Granola Remote Source Example")
    print("=" * 50)
    
    # Create configuration for remote mode
    config = AppConfig(
        document_source="remote",
        api_token=token,
        cache_ttl_seconds=3600,  # 1 hour for testing
    )
    
    print(f"✓ Configuration loaded")
    print(f"  Source: {config.document_source}")
    print(f"  API Base: {config.api_base}")
    print(f"  Cache TTL: {config.cache_ttl_seconds}s")
    print()
    
    # Create document source
    try:
        source = create_document_source(config)
        adapter = DocumentSourceAdapter(source)
        print("✓ Document source created")
    except Exception as e:
        print(f"❌ Failed to create document source: {e}")
        sys.exit(1)
    
    # Get cache info
    print("\n📊 Cache Information")
    print("-" * 50)
    info = adapter.get_cache_info()
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    # Fetch meetings
    print("\n📥 Fetching meetings...")
    try:
        meetings = adapter.get_meetings()
        print(f"✓ Fetched {len(meetings)} meetings")
        
        if meetings:
            print("\n📋 Recent Meetings:")
            print("-" * 50)
            for i, meeting in enumerate(meetings[:5], 1):
                title = meeting.get("title", "Untitled")
                start = meeting.get("start_ts", "Unknown time")
                participants = meeting.get("participants", [])
                
                print(f"\n{i}. {title}")
                print(f"   Time: {start}")
                print(f"   Participants: {', '.join(participants) if participants else 'None'}")
        else:
            print("  No meetings found")
            
    except Exception as e:
        print(f"❌ Failed to fetch meetings: {e}")
        sys.exit(1)
    
    # Test manual refresh
    print("\n🔄 Testing manual refresh...")
    try:
        adapter.refresh_cache()
        meetings_after_refresh = adapter.get_meetings()
        print(f"✓ Cache refreshed, {len(meetings_after_refresh)} meetings available")
    except Exception as e:
        print(f"⚠️  Refresh failed: {e}")
    
    print("\n✅ Example completed successfully!")
    print("\nNext steps:")
    print("  • Run 'granola-mcp' with GRANOLA_DOCUMENT_SOURCE=remote")
    print("  • Use the MCP inspector to test tools")
    print("  • Deploy to your web platform")


if __name__ == "__main__":
    main()
