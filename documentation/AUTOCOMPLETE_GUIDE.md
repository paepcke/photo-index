# Autocomplete Feature Guide

Smart suggestions as you type - discover what's actually in your collection!

## What It Does

The autocomplete feature provides real-time suggestions from your actual photo collection as you type in any search field. No more guessing - see exactly what terms exist.

## Features

✅ **Live suggestions** - appears as you type (after 2 characters)  
✅ **Real data** - shows actual values from your collection  
✅ **Smart matching** - finds terms anywhere in the word  
✅ **Prioritizes** - matches at start of word appear first  
✅ **Keyboard navigation** - use arrow keys and Enter  
✅ **Works everywhere** - all text fields have autocomplete  
✅ **Fast** - debounced requests, cached results  

## Where It Works

### Main Search Box
**Fields searched:**
- Objects (dog, tree, person, building, etc.)
- Materials (wood, metal, glass, fabric, etc.)
- Settings (outdoor, indoor, daytime, night, etc.)
- Visual attributes (colors, lighting styles, etc.)

**Example:** Type "bot" → suggests "bottle", "bottles", "robot"

### Location Fields
**City, State, Country fields:**
- Shows actual locations from your photos
- Starts suggesting after 1 character
- Prioritizes exact matches

**Example:** Type "wel" → suggests "Wellington", "Wellesley"

### Camera Fields
**Make and Model fields:**
- Lists cameras you've actually used
- Helps with exact spelling

**Example:** Type "can" → suggests "Canon", "Nikon D850"

## How to Use

### Basic Usage

1. **Start typing** in any text field
2. **Wait ~0.3 seconds** - suggestions appear
3. **Use mouse or keyboard:**
   - **Click** a suggestion to select it
   - **↓/↑ arrows** to navigate
   - **Enter** to select highlighted
   - **Esc** to close dropdown

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Type 2+ chars | Show suggestions |
| ↓ | Move down list |
| ↑ | Move up list |
| Enter | Select current |
| Esc | Close dropdown |
| Click | Select item |

### Search Strategies

**Discovery:**
```
1. Type "b" in search
2. See all "b" words: "bottle", "building", "beach"
3. Pick "beach"
4. Get all beach photos
```

**Refinement:**
```
1. Type "welling"
2. See "Wellington"
3. Select it - no typos!
```

**Exploration:**
```
1. Type partial word
2. See all variations
3. Learn what's in your collection
```

## Technical Details

**Frontend:**
- Vanilla JavaScript - no dependencies
- Debounced API calls (300ms)
- Client-side caching
- Keyboard navigation support

**Backend:**
- Uses existing `/facets/<field>` endpoint
- Fetches up to 1000 values per field
- Filters on frontend for speed

**Performance:**
- First load: ~200-500ms (fetches data)
- Subsequent: Instant (cached)
- Smart caching by field combination

## Examples

### Text Search with Autocomplete

```
Scenario: Find photos with bottles

1. Click in main search box
2. Type "bot"
3. Autocomplete shows:
   - bottle
   - bottles
   - robot
   - bottom
4. Click "bottles"
5. Search finds all bottle photos
```

### Location Search with Autocomplete

```
Scenario: Find photos from Wellington

1. Expand "Advanced Filters"
2. Click "City" field
3. Type "wel"
4. Autocomplete shows:
   - Wellington
   - Wellesley
5. Click "Wellington"
6. Search finds all Wellington photos
```

### Combined Search

```
Scenario: Find sunset photos from California

1. Main search: Type "sun"
   → Select "sunset"
2. State filter: Type "cal"
   → Select "California"
3. Search → Get California sunsets
```

## Configuration

Autocomplete is configured per field type:

**Description fields** (objects, materials, etc.):
- Minimum characters: 2
- Maximum results: 15
- Debounce: 300ms

**Location fields**:
- Minimum characters: 1
- Maximum results: 20
- Debounce: 300ms

**Camera fields**:
- Minimum characters: 1
- Maximum results: 15
- Debounce: 300ms

## Styling

Clean, Bootstrap-compatible design:
- White dropdown with shadow
- Hover highlighting
- Active item highlighting  
- Matched text in blue bold
- Smooth animations

## Benefits

**1. Discovery:**
- See what's actually in your collection
- Find terms you didn't know existed
- No guessing at spelling

**2. Accuracy:**
- Prevent typos
- Get exact matches
- Consistent terminology

**3. Speed:**
- No need to remember exact terms
- Quick selection with keyboard
- Faster than typing full words

**4. User Experience:**
- Instant feedback
- Visual confirmation
- Reduces cognitive load

## Implementation Details

### Files Added

**JavaScript:**
- `static/js/autocomplete.js` - Main component (200 lines)

**CSS:**
- `static/css/autocomplete.css` - Styling

**Templates:**
- `base.html` - Includes CSS/JS
- `index.html` - Initializes on all fields

### API Endpoints Used

```
GET /facets/description_parsed.objects?limit=1000
GET /facets/location.city?limit=1000
GET /facets/exif.camera_make?limit=1000
... etc
```

### Browser Support

Works in all modern browsers:
- Chrome/Edge 90+
- Firefox 88+
- Safari 14+

## Troubleshooting

**Suggestions not appearing:**
- Type at least 2 characters (1 for location/camera)
- Wait 300ms for debounce
- Check browser console for errors

**Wrong suggestions:**
- Autocomplete shows actual data from your collection
- If term doesn't appear, it's not in any indexed photos
- Use Browse page to see all available values

**Slow performance:**
- First load fetches data (500ms)
- Subsequent loads are instant (cached)
- Cache is per-field combination

**Dropdown overlaps:**
- Positioned absolutely below input
- May need scrolling in filters section
- Z-index: 1000 (above most elements)

## Future Enhancements

Possible improvements:
- Show counts next to suggestions
- Multi-select for multiple terms
- Fuzzy matching
- Recent searches history
- Popular terms first

## Comparison with Browse Page

| Feature | Autocomplete | Browse Page |
|---------|-------------|-------------|
| Speed | Instant | Page load |
| Context | In search | Separate page |
| Selection | One click | Two clicks |
| Discovery | Partial | Full list |
| Best for | Quick search | Exploration |

Use **autocomplete** for fast searches.  
Use **Browse** for exploring all values.

Enjoy effortless searching! 🔍✨
