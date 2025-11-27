# Incremental Indexing & Web Deletion Guide

Two powerful new features for managing your photo index!

---

## 🔄 Feature 1: Incremental Indexing

Smart indexing that only processes new or changed photos.

### Quick Start

```bash
# Index new photos only (default behavior)
python index_photos.py

# Force reindex everything
python index_photos.py --force

# Index single file
python index_photos.py --file /raid/photos/IMG_4681.JPG

# Index photos modified since a date
python index_photos.py --since 2024-11-18

# Preview what would be indexed
python index_photos.py --dry-run
```

### Features

✅ **GUID-based detection** - Reliable photo identification  
✅ **Skip indexed photos** - Only process new ones  
✅ **Date filtering** - Index photos from specific timeframe  
✅ **Single file mode** - Quickly reindex one photo  
✅ **Dry run** - Preview before indexing  
✅ **Progress tracking** - See what's happening  
✅ **Force mode** - Reindex everything when needed  

### Use Cases

**1. Daily Updates:**
```bash
# Add photos from today
python index_photos.py --since 2024-11-25
```

**2. Fix Corrupted Entry:**
```bash
# Reindex single photo
python index_photos.py --file /raid/photos/IMG_4681.JPG --force
```

**3. Preview Changes:**
```bash
# See what would be indexed
python index_photos.py --since 2024-11-18 --dry-run
```

**4. Full Reindex:**
```bash
# Nuclear option - reindex everything
python index_photos.py --force
```

**5. New Photo Import:**
```bash
# After copying new photos to /raid/photos
python index_photos.py
# → Automatically finds and indexes only new ones
```

### How It Works

**GUID-Based Checking:**
1. Calculates GUID from photo content (SHA256 hash)
2. Checks if GUID exists in Qdrant
3. Skips if already indexed (unless --force)
4. More reliable than file path checking

**Date Filtering:**
1. Checks file modification time
2. Includes photos modified after specified date
3. Useful for importing batches

**Dry Run Mode:**
1. Scans all photos
2. Shows what would be indexed
3. No actual indexing happens
4. Safe way to preview

### Command-Line Options

| Flag | Description | Example |
|------|-------------|---------|
| `--file FILE` | Index single file | `--file photo.jpg` |
| `--force` | Reindex even if exists | `--force` |
| `--since DATE` | Photos modified since | `--since 2024-11-18` |
| `--dry-run` | Preview only | `--dry-run` |
| `--photo-dir DIR` | Custom photo directory | `--photo-dir /path` |

### Examples

**Fix corrupted GPS data:**
```bash
# The photo you mentioned with wrong GPS
python index_photos.py --file /raid/photos/IMG_4681.JPG --force
```

**Add last week's photos:**
```bash
python index_photos.py --since 2024-11-18
```

**Preview full reindex:**
```bash
python index_photos.py --force --dry-run
# Shows: "Would index 7000 photos"
```

**Check what's new:**
```bash
python index_photos.py --dry-run
# Shows: "Would index 23 new photos"
```

### Output

**Typical run:**
```
Initializing photo indexer...
Scanning /raid/photos...
Found 7234 total photos
Checking which photos are already indexed...
  → 7211 photos already in index
  → 23 new photos to index

Indexing 23 photos...
Processing batches: 100%|████████| 3/3 [00:45<00:00]

======================================================================
Indexing complete!
  ✓ Successfully indexed: 23
======================================================================
```

**Dry run:**
```
[DRY RUN] Would index 23 photos:
  1. IMG_4690.JPG
  2. IMG_4691.JPG
  3. IMG_4692.JPG
  ... and 20 more

Run without --dry-run to actually index these photos.
```

### Performance

| Operation | Time | Notes |
|-----------|------|-------|
| Check if indexed | ~0.01s/photo | GUID lookup in Qdrant |
| Index new photo | ~2-3s/photo | Embedding + description |
| Skip indexed | Instant | No processing needed |
| Dry run scan | ~1s/100 photos | Just file listing |

### Tips

1. **Run daily:** `python index_photos.py` to catch new photos
2. **Use --since:** After bulk imports from camera/phone
3. **Dry run first:** Always preview with `--dry-run` for large operations
4. **Single file for fixes:** When you notice corrupted data
5. **Force sparingly:** Full reindex takes hours for 7K photos

---

## 🗑️ Feature 2: Web UI Delete

Delete photos from index and optionally from disk via web interface.

### Quick Start

1. **View any photo** in web UI
2. **Click "Delete" button** (red, top right)
3. **Choose options:**
   - ☑️ Remove from index (always)
   - ☐ Also delete file from disk (optional)
4. **Confirm deletion**
5. **Redirected to search** after success

### Features

✅ **Safe by default** - Only removes from index  
✅ **Optional file deletion** - Checkbox for disk deletion  
✅ **Clear warnings** - Shows exactly what will happen  
✅ **Confirmation required** - Modal prevents accidents  
✅ **Immediate feedback** - Success/error messages  
✅ **Auto redirect** - Returns to search after delete  

### Safety Features

**1. Two-Step Process:**
```
Click Delete → Modal appears → Confirm
```

**2. Clear Options:**
```
☑️ Remove from index (checked, disabled)
☐ Also delete file from disk (unchecked by default)
```

**3. Explicit Warning:**
```
⚠️ Warning: This will permanently delete the file from your computer.
By default, the photo is only removed from the index.
```

**4. File Info Shown:**
```
File: IMG_4681.JPG
Path: /raid/photos/IMG_4681.JPG
```

### Use Cases

**1. Remove Unwanted Photos:**
```
Search → Find photo → Delete (index only)
→ Photo removed from search results
→ File still on disk for backup
```

**2. Clean Up Disk Space:**
```
Search → Find photo → Delete
→ Check "Also delete file from disk"
→ Confirm → Both removed
```

**3. Remove Duplicates:**
```
Find Similar → Find duplicate
→ Delete both from index and disk
```

**4. Fix Index:**
```
Find corrupted entry → Delete from index
→ Reindex with: python index_photos.py --file photo.jpg --force
```

### How It Works

**Backend (Flask route: `/delete/<guid>`):**
1. Receives POST with `{"delete_file": true/false}`
2. Looks up photo by GUID
3. Deletes point from Qdrant index
4. If `delete_file=true`, deletes file with `Path.unlink()`
5. Returns JSON with success/error

**Frontend (JavaScript):**
1. Shows Bootstrap modal on click
2. Checkbox for file deletion option
3. On confirm, POSTs to `/delete/<guid>`
4. Shows loading message
5. Displays success/error
6. Redirects to search page

### API Endpoint

```
POST /delete/<guid>
Content-Type: application/json

{
  "delete_file": false  // true to also delete file
}

Response:
{
  "success": true,
  "message": "Successfully removed IMG_4681.JPG from index",
  "deleted_from_index": true,
  "deleted_from_disk": false
}
```

### Browser Permissions

**Q: Can the web UI delete files?**  
A: Yes! Flask runs with your user permissions, so it can delete files you have access to. That's why we:
- Default to index-only
- Require explicit checkbox
- Show clear warnings
- Need confirmation

### Error Handling

**Photo not found in index:**
```
Error: Photo not found in index
```

**File doesn't exist on disk:**
```
Removed from index but file not found on disk
```

**Permission error:**
```
Removed from index but failed to delete file: Permission denied
```

**General error:**
```
Error: [detailed error message]
```

### Comparison: CLI vs Web

| Feature | CLI (`delete_photo.py`) | Web UI |
|---------|------------------------|--------|
| Delete from index | ✅ | ✅ |
| Delete file | ✅ `-d` flag | ✅ Checkbox |
| Confirmation | ✅ `-y` to skip | ✅ Always asks |
| Multiple files | ✅ Yes | ❌ One at a time |
| Dry run | ✅ `--dry-run` | ❌ No |
| Convenience | CLI | Visual |

**Use CLI for:** Batch operations, scripting, dry runs  
**Use Web for:** Quick one-off deletions while browsing

---

## Combined Workflows

### Fix Corrupted Entry

**Problem:** Photo has wrong GPS data in index

**Solution:**
```bash
# 1. Delete from index (Web UI or CLI)
# Web: View photo → Delete (index only)

# 2. Reindex with correct data
python index_photos.py --file /raid/photos/IMG_4681.JPG --force

# 3. Verify in web UI
# Search for photo → Check GPS data
```

### Clean Up After Import

**Scenario:** Imported 100 photos, 5 are bad quality

```bash
# 1. Index all new photos
python index_photos.py

# 2. Browse in web UI
# Find bad photos → Delete (index + disk)

# 3. Good photos remain indexed
```

### Maintenance Routine

**Weekly:**
```bash
# Add new photos
python index_photos.py --since 2024-11-18
```

**Monthly:**
```bash
# Preview what's new
python index_photos.py --dry-run

# Check if anything unexpected
# If looks good, run without --dry-run
```

**As Needed:**
```
# Fix specific issues via web UI
# Delete corrupted entries
# Reindex with CLI
```

---

## Technical Details

### Incremental Indexing

**GUID Calculation:**
```python
import hashlib
def get_photo_guid(file_path):
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        sha256.update(f.read())
    return sha256.hexdigest()[:16]  # First 16 chars (64 bits)
```

**Qdrant Point ID:**
```python
def guid_to_point_id(guid):
    return int(guid, 16) % (2**63)  # Fit in signed 64-bit
```

**Checking if Indexed:**
```python
point_id = guid_to_point_id(guid)
results = client.retrieve(
    collection_name=collection_name,
    ids=[point_id]
)
return len(results) > 0
```

### Web Deletion

**Flask Route:**
```python
@app.route('/delete/<guid>', methods=['POST'])
def delete_photo(guid):
    data = request.get_json()
    delete_file = data.get('delete_file', False)
    
    # Delete from Qdrant
    point_id = guid_to_point_id(guid)
    client.delete(collection_name, points_selector=[point_id])
    
    # Delete file if requested
    if delete_file:
        Path(photo['file_path']).unlink()
    
    return jsonify({'success': True})
```

**Frontend:**
```javascript
async function confirmDelete() {
    const deleteFile = document.getElementById('deleteFileCheck').checked;
    
    const response = await fetch(`/delete/${photoGuid}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({delete_file: deleteFile})
    });
    
    // Handle success/error
}
```

---

## Files Added/Updated

**New Files:**
- `index_photos.py` - Enhanced indexing CLI with incremental support

**Updated Files:**
- `templates/photo_detail.html` - Delete button and modal
- `search_web.py` - `/delete/<guid>` route

---

## Migration from Old Indexing

**Old way:**
```bash
# Had to reindex everything each time
python photo_indexer.py
# → 5+ hours for 7K photos
```

**New way:**
```bash
# Incremental indexing
python index_photos.py
# → Only indexes new photos (~minutes)

# When needed, force full reindex
python index_photos.py --force
# → Still 5+ hours, but rarely needed
```

---

## Tips & Best Practices

### Incremental Indexing

1. **Default to incremental:** Just run `python index_photos.py` regularly
2. **Use --since after imports:** When you copy many photos at once
3. **Dry run for safety:** Always preview large operations
4. **Single file for fixes:** Precise control for problem photos
5. **Force reindex rarely:** Only when you've updated indexing code

### Web Deletion

1. **Default to index-only:** Keeps file as backup
2. **Check twice for disk deletion:** Can't undo!
3. **Use Find Similar first:** To check for duplicates before deleting
4. **CLI for batch:** Web is for one-at-a-time
5. **Reindex after:** If you deleted wrong photo from index

---

Enjoy your enhanced photo management system! 🚀📸
