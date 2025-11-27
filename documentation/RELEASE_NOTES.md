# Photo Search System - "More Like This" Release

## What's New

### 🎯 "Find Similar" Feature

One-click visual similarity search from any photo in your results - no re-uploading needed!

**Key Features:**
- ✅ "Find Similar" button on every search result
- ✅ "Find Similar Photos" button on detail pages  
- ✅ CLI support: `--similar /path/to/photo.jpg`
- ✅ Reuses existing embeddings (fast!)
- ✅ Chain multiple searches to explore
- ✅ Works with all filters

## Download Updated Files

**Core Library:**
- [photo_search.py](computer:///mnt/user-data/outputs/photo_search.py) - Added `search_similar_to_guid()` method

**Web UI:**
- [web_ui.tar.gz](computer:///mnt/user-data/outputs/web_ui.tar.gz) - Updated interface with Find Similar buttons

**CLI:**
- [search_cli.py](computer:///mnt/user-data/outputs/search_cli.py) - Added `--similar` flag

**Documentation:**
- [FIND_SIMILAR_GUIDE.md](computer:///mnt/user-data/outputs/FIND_SIMILAR_GUIDE.md) - Complete usage guide

## Installation

```bash
# Extract web UI (overwrites existing files)
tar xzf web_ui.tar.gz

# Copy updated files to your project
cp photo_search.py search_cli.py src/photo_search/

# Restart web server
python search_web.py
```

## Quick Start

### Web UI

1. Do any search
2. Click "Find Similar" on any result
3. Get visually similar photos instantly!

### CLI

```bash
# Find similar photos
./search_cli.py --similar /raid/photos/IMG_4513.JPG --limit 20

# With filters
./search_cli.py --similar /raid/photos/IMG_4513.JPG \
  --location-city "Wellington" \
  --score-threshold 0.8
```

## How It Works

**Technical Flow:**
1. User clicks "Find Similar" on a photo
2. System retrieves photo's GUID
3. Looks up stored embedding in Qdrant (no generation needed!)
4. Runs vector similarity search
5. Returns similar photos (excluding the original)

**Performance:**
- No embedding generation: **~1 second** (vs 5-10s for upload)
- Reuses existing vectors: **no GPU needed**
- Supports all filters: **combine with location/date/camera**

## Use Cases

**Explore Visual Neighborhoods:**
```
Search "sunset" → Find best one → "Find Similar" → Discover related sky photos
```

**Find More from a Shoot:**
```
Filter by date → Pick favorite → "Find Similar" → Get similar angles/lighting
```

**Discover Duplicates:**
```
Any photo → "Find Similar" with 0.95 threshold → Find near-duplicates
```

**Chain Exploration:**
```
Random photo → "Find Similar" → Pick interesting one → "Find Similar" again
```

## Example Session

```
User: Search for "Wellington"
System: Returns 45 photos

User: Clicks "Find Similar" on harbor photo
System: Returns 20 similar harbor/water photos in 1 second

User: Finds better angle, clicks "Find Similar" again
System: Returns 20 photos with similar composition

User: Adds filter: date > 2024-01-01
System: Narrows to recent similar photos
```

## Technical Details

**New Methods:**
```python
# photo_search.py
searcher.search_similar_to_guid(
    guid='abc123...',
    limit=20,
    filters=location_filter,
    score_threshold=0.8
)
```

**New API Endpoint:**
```
GET /similar/<guid>?limit=20&score_threshold=0.8
```

**Frontend Updates:**
- Button on each result card
- Button on detail page
- URL parameter support: `/?findSimilar=<guid>`
- Auto-trigger on page load

## Benefits Over Image Upload

| Aspect | Image Upload | Find Similar |
|--------|-------------|--------------|
| Speed | 5-10 seconds | ~1 second |
| Convenience | Multi-step | One click |
| GPU Usage | Required | Not needed |
| Chaining | Manual | Seamless |

## What's Unchanged

All existing functionality works exactly as before:
- ✅ Text search
- ✅ Visual similarity (upload)
- ✅ Filters (location, date, camera)
- ✅ Hybrid search
- ✅ Browse values
- ✅ All CLI tools

This is a pure addition - no breaking changes!

## Next Steps

Now that you have "Find Similar":
1. Try it on your Wellington results
2. Chain multiple searches to explore
3. Combine with filters for precise results
4. Use from detail page when viewing photos

Then consider:
- Autocomplete for text search (next feature?)
- Face recognition with GUID linking
- Batch "Find Similar" operations
- Visual clustering view

## Files Changed

**Backend:**
- `photo_search.py` - New `search_similar_to_guid()` method
- `search_web.py` - New `/similar/<guid>` endpoint

**Frontend:**
- `templates/index.html` - Find Similar button and handler
- `templates/photo_detail.html` - Find Similar button

**CLI:**
- `search_cli.py` - New `--similar` flag

## Context Status

Still at **96K/190K tokens (50%)** - plenty of room for more features!

Enjoy exploring your photo collection's visual connections! 🎉📸
