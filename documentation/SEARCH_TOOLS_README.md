# Photo Search Tools

Search your indexed photo collection using visual similarity, text queries, and metadata filters.

## PhotoSearch Class

Core search library used by both CLI and web UI.

**Key Methods:**
- `search_by_image(image_path)` - Find visually similar photos
- `search_by_text(query)` - Search in photo descriptions
- `search_hybrid(image_path, text_query, filters)` - Combined search
- `get_facets(field)` - Get unique values (e.g., all cities)
- `get_stats()` - Collection statistics

## CLI Search Tool

### Visual Similarity Search

Find photos that look similar to a query image:

```bash
# Basic similarity search
./search_cli.py --image /path/to/query.jpg

# More results
./search_cli.py --image query.jpg --limit 50

# With minimum similarity score
./search_cli.py --image query.jpg --score-threshold 0.8
```

### Text Search

Search in photo descriptions (objects, materials, setting, visual attributes):

```bash
# Find photos with dogs
./search_cli.py --text "dog"

# Find beach sunset photos
./search_cli.py --text "beach sunset"
```

### Filter by Metadata

Filter photos by location, date, camera:

```bash
# Photos from San Francisco
./search_cli.py --text "outdoor" --location-city "San Francisco"

# Photos from 2024
./search_cli.py --date-from 2024-01-01 --date-to 2024-12-31

# Photos from a specific camera
./search_cli.py --camera-make "Canon" --camera-model "EOS R5"

# Combine multiple filters
./search_cli.py --location-state "California" --date-from 2024-01-01 --limit 100
```

### Hybrid Search

Combine visual similarity + text + filters:

```bash
# Similar images that contain "outdoor"
./search_cli.py --hybrid --image query.jpg --text "outdoor"

# Similar sunset photos from California
./search_cli.py --hybrid \
  --image sunset.jpg \
  --text "sunset" \
  --location-state "California"
```

### Explore Your Collection

Get unique values for any field:

```bash
# See all cities in your collection
./search_cli.py --facets location.city

# See all camera makes
./search_cli.py --facets exif.camera_make

# See all states
./search_cli.py --facets location.state
```

### Collection Stats

```bash
# Show total photos and index info
./search_cli.py --stats
```

### Output Formats

```bash
# JSON output (for piping to other tools)
./search_cli.py --text "dog" --json

# Just file paths (one per line)
./search_cli.py --text "dog" --paths-only

# Verbose output (includes full descriptions)
./search_cli.py --image query.jpg --verbose
```

## Example Workflows

**Find all outdoor photos from last summer:**
```bash
./search_cli.py \
  --text "outdoor" \
  --date-from 2024-06-01 \
  --date-to 2024-08-31 \
  --limit 100
```

**Find photos similar to a sunset, from California beaches:**
```bash
./search_cli.py --hybrid \
  --image sunset_example.jpg \
  --text "beach" \
  --location-state "California" \
  --score-threshold 0.7
```

**Explore your collection by location:**
```bash
# See all unique cities
./search_cli.py --facets location.city

# Then view photos from a specific city
./search_cli.py --location-city "Paris" --limit 50
```

**Find photos by camera:**
```bash
# See all cameras in your collection
./search_cli.py --facets exif.camera_make

# View photos from a specific camera
./search_cli.py --camera-make "Canon" --camera-model "EOS R5"
```

## Using PhotoSearch in Your Code

```python
from photo_search import PhotoSearch, FilterBuilder

# Initialize
searcher = PhotoSearch()

# Visual similarity search
results = searcher.search_by_image('/path/to/query.jpg', limit=20)

# Text search
results = searcher.search_by_text('dog beach', limit=10)

# With filters
date_filter = FilterBuilder.by_date_range('2024-01-01', '2024-12-31')
location_filter = FilterBuilder.by_location(city='San Francisco')
combined = FilterBuilder.combine_filters(date_filter, location_filter)

results = searcher.search_by_image(
    '/path/to/query.jpg',
    filters=combined,
    limit=50
)

# Get facets
cities = searcher.get_facets('location.city')
for city, count in cities.items():
    print(f"{city}: {count} photos")

# Hybrid search
results = searcher.search_hybrid(
    image_path='/path/to/query.jpg',
    text_query='sunset',
    filters=location_filter,
    limit=20
)
```

## Tips

1. **Start broad, then filter**: Do a visual or text search first, then add filters to narrow down
2. **Use facets to explore**: See what's in your collection before searching
3. **Adjust score threshold**: For stricter similarity matching, use `--score-threshold 0.8`
4. **Combine approaches**: Hybrid search is powerful for complex queries
5. **Use --paths-only for scripting**: Pipe results to other commands

## Next: Web UI

The same `PhotoSearch` class will power the web interface, giving you a visual way to browse results and explore your collection.
