# "More Like This" Feature Guide

Find visually similar photos without re-uploading images!

## How It Works

The system retrieves the embedding vector of any photo already in your collection and uses it to find similar photos. No need to generate a new embedding - it uses the one already stored in Qdrant.

## Web UI Usage

### From Search Results

1. **Do any search** (text, image, filters, etc.)
2. **See "Find Similar" button** on each result card
3. **Click the button** → Instantly get similar photos
4. **Chain searches:** Find similar → Pick one → Find similar again!

### From Photo Detail Page

1. **Click any photo** to view details
2. **Click "Find Similar Photos"** button (top right)
3. **Results appear** on main search page

### Example Workflow

```
1. Search for "Wellington" → Get 45 results
2. See a great photo of harbor → Click "Find Similar"
3. Get 20 similar harbor photos
4. Find an even better one → Click "Find Similar" again
5. Keep iterating until you find exactly what you want!
```

## CLI Usage

```bash
# Find photos similar to a specific photo
./search_cli.py --similar /raid/photos/IMG_4513.JPG

# With filters
./search_cli.py --similar /raid/photos/IMG_4513.JPG --location-city "Wellington"

# With score threshold
./search_cli.py --similar /raid/photos/IMG_4513.JPG --score-threshold 0.8 --limit 50
```

## Technical Details

**Backend (`photo_search.py`):**
- New method: `search_similar_to_guid(guid, limit, filters, score_threshold)`
- Retrieves photo's embedding from Qdrant by GUID
- Excludes the original photo from results
- Supports all standard filters

**Web API:**
- New endpoint: `GET /similar/<guid>?limit=20&score_threshold=0.8`
- Returns JSON with same format as regular search
- Handles errors gracefully (404 if photo not found)

**Frontend:**
- "Find Similar" button on every search result card
- "Find Similar Photos" button on detail page
- URL parameter support: `/?findSimilar=<guid>`
- Updates results title to "Similar Photos"

## Advantages Over Image Upload

**Faster:**
- No upload time
- No embedding generation (reuses existing)
- Results in ~1 second

**Iterative:**
- Chain multiple "Find Similar" searches
- Refine results by picking best matches
- Explore visual neighborhoods in your collection

**Convenient:**
- No need to download/save photos to upload
- Works directly from search results
- One click instead of multi-step process

## Use Cases

**1. Find More from a Shoot:**
```
Search: date=2024-07-15
→ Find photo you like
→ "Find Similar"
→ Get other photos from similar angle/lighting
```

**2. Explore Visual Themes:**
```
Search: "sunset"
→ Find best sunset
→ "Find Similar"
→ Discover other dramatic sky photos
```

**3. Locate Duplicates:**
```
Pick any photo
→ "Find Similar" with threshold 0.95
→ Find near-duplicates/burst shots
```

**4. Visual Discovery:**
```
Random browse
→ Interesting photo catches your eye
→ "Find Similar"
→ Explore similar aesthetic/composition
```

## Tips

1. **Combine with filters:** After "Find Similar", add location/date filters to narrow down
2. **Adjust threshold:** Higher = stricter matches, lower = more variety
3. **Chain searches:** Keep clicking "Find Similar" to explore visual connections
4. **Use from detail page:** Great for when you're viewing a photo and want context

## Comparison with Other Methods

| Method | Speed | Accuracy | Convenience |
|--------|-------|----------|-------------|
| Upload Image | Slow (5-10s) | High | Low |
| Find Similar | Fast (1s) | High | High |
| Text Search | Instant | Medium | Medium |

## Examples

**CLI:**
```bash
# Basic similar search
./search_cli.py --similar /raid/photos/harbor_photo.jpg

# Only from specific location
./search_cli.py --similar /raid/photos/harbor_photo.jpg \
  --location-city "Wellington" \
  --limit 30

# High similarity only
./search_cli.py --similar /raid/photos/harbor_photo.jpg \
  --score-threshold 0.9
```

**API (for custom integrations):**
```bash
# Get similar photos via API
curl "http://localhost:5000/similar/<guid>?limit=20&score_threshold=0.8"
```

## Future Enhancements

Potential additions:
- Bulk "Find Similar" for multiple photos
- Save similarity search queries
- Visual similarity clustering view
- "Not like this" negative examples

Enjoy discovering visual connections in your collection! 📸✨
