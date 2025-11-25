# Complete Photo Search System - Installation Guide

Everything you need to search your indexed photo collection.

## Quick Start

### 1. Extract Web UI
```bash
cd /path/to/your/project
tar xzf web_ui.tar.gz
```

### 2. Install Dependencies
```bash
pip install flask waitress
```

### 3. Start the Web Server
```bash
python search_web.py
```

Open browser to: **http://localhost:5000**

## What You Get

### Web UI (http://localhost:5000)

**Main Features:**
- **Search Page** (/) - Text, image similarity, and hybrid search with filters
- **Browse Page** (/browse) - NEW! Explore collection values
- **Photo Detail** (/photo/<guid>) - Full metadata view

**Browse Page Features:**
- Explore Cities, States, Countries
- Browse Objects, Materials, Settings, Visual Attributes
- View Camera Makes and Models
- Filter values with search box
- Click to search with selected value
- See counts for each value

### CLI Tools

**Search Tools:**
- `search_cli.py` - Full-featured search (updated with filter-only support)
- `photo_search.py` - Search library (used by both CLI and web)

**Value Explorer:**
- `list_values.py` - NEW! List unique values in collection

**Indexing Tools:**
- `get_description.py` - Generate AI descriptions
- `get_exif.py` - Extract EXIF data
- `show_index.py` - View indexed data
- `delete_photo.py` - Remove from index

### Documentation

- `WEB_UI_README.md` - Web interface guide
- `SEARCH_TOOLS_README.md` - Search usage examples
- `LIST_VALUES_README.md` - NEW! Value explorer guide
- `CLI_TOOLS_README.md` - Indexing tools reference

## New Features in This Release

### 1. Browse Collection Values

**CLI:**
```bash
# See all cities
./list_values.py --field location.city

# See all objects in photos
./list_values.py --field description_parsed.objects

# See all camera makes
./list_values.py --field exif.camera_make

# Show everything
./list_values.py --all-fields
```

**Web UI:**
- Navigate to "Browse" in the top menu
- Click categories (Locations, Descriptions, Cameras)
- Browse values with live counts
- Filter with search box
- Click "Search with selected" to find photos

### 2. Filter-Only Search

Now you can search using filters alone (no text/image required):

```bash
# Find all photos from Anchorage
./search_cli.py --location-city "Anchorage"

# Find all photos from 2024
./search_cli.py --date-from 2024-01-01 --date-to 2024-12-31

# Find all Canon photos
./search_cli.py --camera-make "Canon"
```

## Example Workflows

### Discover and Search

```bash
# 1. See what cities you have photos from
./list_values.py --field location.city

# Output:
#   San Francisco: 150
#   New York: 89
#   Anchorage: 45
#   ...

# 2. Search for photos from a specific city
./search_cli.py --location-city "Anchorage"

# 3. See what objects are common in your photos
./list_values.py --field description_parsed.objects

# Output:
#   tree: 234
#   person: 189
#   building: 156
#   ...

# 4. Search for specific objects
./search_cli.py --text "tree"
```

### Use Web UI for Visual Exploration

1. Start server: `python search_web.py`
2. Browse to: http://localhost:5000
3. Click "Browse" in nav
4. Explore categories visually
5. Click values to search
6. View results in gallery

## File Locations

After extraction:
```
your-project/
├── search_web.py          # Flask application
├── templates/
│   ├── base.html          # Base template
│   ├── index.html         # Search interface
│   ├── photo_detail.html  # Photo details
│   └── browse_values.html # NEW! Browse values
└── static/
    ├── css/
    └── js/
```

Your CLI tools (add to src/photo_search/ or use standalone):
```
list_values.py       # NEW! Value explorer
search_cli.py        # Updated with filter-only search
photo_search.py      # Search library (both use this)
```

## Configuration

Uses your existing photo_index configuration:
- `QDRANT_PATH` - Vector database location
- `COLLECTION_NAME` - Collection to search
- `MODEL_PATH` - Vision model (for image search)
- `DEVICE` - GPU or CPU

## Tips

1. **Start with Browse** - Explore what's in your collection before searching
2. **Use Filter-Only Search** - Great for finding photos by metadata alone
3. **Combine Approaches** - Browse → See values → Filter → Search
4. **Web UI for Discovery** - CLI for scripting and automation
5. **Value Counts** - Help understand your photo distribution

## Troubleshooting

**"Can't find module photo_search":**
- Make sure `photo_search.py` is in same directory or PYTHONPATH
- Or: `export PYTHONPATH=/path/to/your/src/photo_search:$PYTHONPATH`

**Browse page not working:**
- Verify web_ui.tar.gz was fully extracted
- Check that `browse_values.html` is in `templates/`
- Look for errors in terminal where search_web.py is running

**No values showing:**
- Verify photos are indexed: `./search_cli.py --stats`
- Check QDRANT_PATH is correct
- Try a different field: some may be empty

## What's Next

Future enhancements:
- Autocomplete in search (using value lists)
- Face recognition (separate collection with GUID links)
- Batch operations from web UI
- Export search results
- Timeline view by date

Enjoy exploring your collection! 🎉📸
