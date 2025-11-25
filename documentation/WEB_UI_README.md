# Photo Search Web UI

Beautiful web interface for searching your indexed photo collection.

## Features

✨ **Three Search Modes:**
- **Text Search** - Find photos by description (objects, materials, setting, colors)
- **Visual Similarity** - Upload a query image to find similar photos
- **Hybrid Search** - Combine image similarity with text queries and filters

🔍 **Advanced Filtering:**
- Filter by location (city, state, country)
- Filter by date range
- Filter by camera make/model
- Combine multiple filters

📸 **Rich Display:**
- Gallery grid view with thumbnails
- Detailed photo view with full metadata
- EXIF data display (camera, settings, GPS)
- AI-generated descriptions with tags
- Geocoded locations with map links

## Installation

1. **Extract the archive:**
```bash
cd /path/to/your/project
tar xzf web_ui.tar.gz
```

2. **Install dependencies:**
```bash
pip install flask waitress
```

## Usage

### Start the Server

**Production mode (recommended):**
```bash
python search_web.py
```

Then open your browser to: **http://localhost:5000**

**Custom host/port:**
```bash
python search_web.py --host 0.0.0.0 --port 8080
```

**Development mode (with auto-reload):**
```bash
python search_web.py --debug
```

### Using the Interface

1. **Text Search:**
   - Enter keywords like "dog", "sunset", "beach"
   - Searches across all description fields
   - Click "Advanced Filters" to narrow results

2. **Visual Similarity:**
   - Click "Similar Images" tab
   - Upload a query photo
   - Optionally set minimum similarity threshold (0-1)
   - Results show similarity scores

3. **Hybrid Search:**
   - Combine image + text + filters
   - Great for complex queries like "outdoor photos similar to this, taken in California"

4. **Filters:**
   - Click "Advanced Filters" to expand
   - Set location, date range, or camera
   - Combine with any search mode

5. **View Details:**
   - Click any photo in results
   - See full-size image
   - View complete metadata
   - Click "View on Map" for GPS locations

## Configuration

The web UI uses these from your photo_index configuration:
- `QDRANT_PATH` - Qdrant storage location
- `COLLECTION_NAME` - Collection to search
- `MODEL_PATH` - Vision model for generating query embeddings
- `DEVICE` - GPU or CPU

## File Structure

```
search_web.py           # Flask application
templates/
  ├── base.html         # Base template with nav
  ├── index.html        # Search interface
  └── photo_detail.html # Photo detail view
static/
  ├── css/              # (reserved for custom CSS)
  └── js/               # (reserved for custom JS)
```

## API Endpoints

The web UI exposes these endpoints (useful for custom integrations):

- `POST /search` - Execute search, returns JSON
- `GET /photo/<guid>` - Photo detail page
- `GET /serve/<guid>` - Serve actual photo file
- `GET /facets/<field>` - Get unique values for a field
- `GET /stats` - Collection statistics

## Example API Usage

```bash
# Search via API
curl -X POST http://localhost:5000/search \
  -F "search_type=text" \
  -F "text_query=dog" \
  -F "limit=10"

# Get statistics
curl http://localhost:5000/stats
```

## Tips

1. **First Search Takes Longer:**
   - The vision model loads on first image search
   - Subsequent searches are fast

2. **Similarity Scores:**
   - 1.0 = identical images
   - 0.9+ = very similar
   - 0.7+ = moderately similar
   - 0.5+ = somewhat similar

3. **Text Search:**
   - Searches exact matches in description fields
   - Try single keywords for best results
   - Combine with filters for precision

4. **Performance:**
   - Handles thousands of photos smoothly
   - Text search is instant
   - Image search takes 1-2 seconds (model inference)

5. **Network Access:**
   - To access from other devices on your network:
     ```bash
     python search_web.py --host 0.0.0.0 --port 5000
     ```
   - Then visit: `http://your-machine-ip:5000`

## Troubleshooting

**"No photos found":**
- Check that photos are indexed: `python search_cli.py --stats`
- Verify QDRANT_PATH is correct
- Try simpler query first

**"Model loading slow":**
- First image search loads the model (10-15 seconds)
- This is normal - subsequent searches are fast
- Use GPU for faster inference (DEVICE="cuda")

**"Can't access from other machines":**
- Use `--host 0.0.0.0` to bind to all interfaces
- Check firewall allows port 5000
- Use your machine's IP address, not localhost

**"Port already in use":**
- Change port: `--port 8080`
- Or stop existing process on port 5000

## Development

To customize the UI:

1. **Styling:**
   - Edit `templates/base.html` for global styles
   - Add custom CSS in `static/css/`

2. **Add Features:**
   - New routes in `search_web.py`
   - New templates in `templates/`

3. **JavaScript:**
   - Main search logic in `templates/index.html` (inline)
   - Can move to `static/js/` for organization

## Production Deployment

For serious production use (not needed for personal use on sextus):

1. **Use a proper WSGI server:**
   - Gunicorn: `gunicorn -w 4 search_web:app`
   - uWSGI: `uwsgi --http :5000 --wsgi-file search_web.py --callable app`

2. **Add reverse proxy (nginx/Apache)**

3. **Enable HTTPS**

But for local use, Waitress (built-in) is perfect!

## Credits

Built with:
- Flask (web framework)
- Bootstrap 5 (UI components)
- Waitress (production server)
- PhotoSearch class (search logic)

Enjoy exploring your photo collection! 📸✨
