# List Values Tool

Explore unique values in your photo collection to help with searching.

## CLI Tool

**[list_values.py](computer:///mnt/user-data/outputs/list_values.py)**

### Usage

**See available fields:**
```bash
./list_values.py --show-fields
```

**List values for a specific field:**
```bash
# List all cities
./list_values.py --field location.city

# List all objects found in photos
./list_values.py --field description_parsed.objects

# List all camera makes
./list_values.py --field exif.camera_make
```

**Show all values (not just top 100):**
```bash
./list_values.py --field location.city --show-all
```

**List all common fields at once:**
```bash
./list_values.py --all-fields
```

**JSON output:**
```bash
./list_values.py --field location.city --json
```

### Common Fields

**Locations:**
- `location.city` - Cities
- `location.state` - States/provinces
- `location.country` - Countries

**Descriptions:**
- `description_parsed.objects` - Objects in photos (dog, tree, car, etc.)
- `description_parsed.materials` - Materials (wood, metal, fabric, etc.)
- `description_parsed.setting` - Settings (outdoor, indoor, daytime, etc.)
- `description_parsed.visual_attributes` - Visual attributes (colors, lighting, style)

**Camera:**
- `exif.camera_make` - Camera manufacturers
- `exif.camera_model` - Camera models

**Dates:**
- `exif.date_taken` - Photo dates

### Example Workflow

```bash
# 1. See what cities you have
./list_values.py --field location.city

# Output:
#   San Francisco: 150
#   New York: 89
#   Paris: 45
#   ...

# 2. Then search for photos from a specific city
./search_cli.py --location-city "San Francisco"

# 3. See what objects are in your photos
./list_values.py --field description_parsed.objects

# Output:
#   dog: 234
#   tree: 189
#   person: 156
#   ...

# 4. Search for specific objects
./search_cli.py --text "dog"
```

## Web UI

**Browse Values Page:** http://localhost:5000/browse

Interactive interface for exploring collection values:

1. **Select a category** (Locations, Descriptions, Cameras)
2. **Choose a field** (e.g., Cities, Objects)
3. **Browse values** with counts
4. **Filter** the list with search box
5. **Click "Search"** to find photos with that value

Great for:
- Discovering what's in your collection
- Planning searches
- Finding typos or duplicates
- Understanding your photo distribution

## Use Cases

**1. Discover your travel destinations:**
```bash
./list_values.py --field location.city
```

**2. Find what you photograph most:**
```bash
./list_values.py --field description_parsed.objects
```

**3. See your camera gear:**
```bash
./list_values.py --field exif.camera_make
```

**4. Plan targeted searches:**
```bash
# First: see what's available
./list_values.py --field description_parsed.setting

# Then: search for specific setting
./search_cli.py --text "outdoor"
```

**5. Data quality checking:**
```bash
# Look for inconsistencies
./list_values.py --field location.city --show-all

# Might find: "San Francisco", "san francisco", "SF" 
# (all referring to same place)
```

## Future: Autocomplete

This same functionality will power search autocomplete in the web UI, suggesting:
- Cities as you type
- Objects you've photographed
- Camera models you own
- Common visual attributes

## Tips

- Start with `--all-fields` to get an overview
- Use `--json` for scripting/analysis
- Fields with many unique values may take longer to load
- The web UI is great for interactive exploration
- The CLI is better for quick checks and scripts

Ready to explore your collection! 🔍
