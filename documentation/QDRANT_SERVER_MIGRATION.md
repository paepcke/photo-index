# Qdrant Server Migration Guide

## ✅ What You've Done So Far

1. ✓ Installed Docker on sextus
2. ✓ Started Qdrant server container
3. ✓ Updated config.py to use server mode
4. ✓ Got updated code files

**Status:** Almost done! Just need to copy updated files and test.

---

## Files Updated

Two files now support both local and server modes:

1. **photo_search.py** - Search library
2. **photo_indexer.py** - Indexing system

Both automatically detect server vs local mode from config.py.

---

## Installation Steps

### 1. Copy Updated Files

```bash
# Copy to your photo_index package
cp photo_search.py src/photo_index/
cp photo_indexer.py src/photo_index/
```

### 2. Verify config.py Settings

Your config.py should have:

```python
# Qdrant Server Mode (ACTIVE)
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333

# Qdrant Local Mode (COMMENTED OUT)
# QDRANT_PATH = "/raid/qdrant_storage/photos"
```

### 3. Test Connection

```bash
python test_qdrant_connection.py
```

**Expected output:**
```
Testing Qdrant server connection...
----------------------------------------------------------------------
✓ Connected to Qdrant server successfully!
  Host: localhost:6333

Collections found: 1

  Collection: photos
    Vectors: 9906
    Dimension: 7680

======================================================================
✓ Qdrant server is working correctly!
======================================================================
```

### 4. Test CLI Tools (Concurrent Access!)

```bash
# In one terminal: Start web UI
python search_web.py

# In another terminal: Use CLI simultaneously! ✓
python src/photo_index/cli/show_index.py /raid/photos/IMG_4681.JPG
python find_by_gps.py 46.401761 -64.102203
./search_cli.py --text "sunset"
```

**This is the magic!** No more "already accessed by another instance" errors!

---

## What Changed in the Code

### Before (Local Only):

```python
# photo_search.py
def __init__(self, qdrant_path: str = QDRANT_PATH, ...):
    self.client = QdrantClient(path=qdrant_path)
```

### After (Local OR Server):

```python
# photo_search.py
def __init__(
    self,
    qdrant_path: Optional[str] = QDRANT_PATH,
    qdrant_host: Optional[str] = QDRANT_HOST,
    qdrant_port: Optional[int] = QDRANT_PORT,
    ...
):
    if qdrant_path:
        print(f"Connecting to Qdrant local storage: {qdrant_path}")
        self.client = QdrantClient(path=qdrant_path)
    elif qdrant_host and qdrant_port:
        print(f"Connecting to Qdrant server: {qdrant_host}:{qdrant_port}")
        self.client = QdrantClient(host=qdrant_host, port=qdrant_port)
    else:
        raise ValueError("Must specify either qdrant_path or (qdrant_host and qdrant_port)")
```

**Same change in photo_indexer.py!**

---

## Qdrant Server Management

### Check Status

```bash
# List running containers
sudo docker ps

# Should show:
# CONTAINER ID   IMAGE             PORTS                              NAMES
# f0f20c54c6fd   qdrant/qdrant     0.0.0.0:6333-6334->6333-6334/tcp   qdrant
```

### Stop Server

```bash
sudo docker stop qdrant
```

### Start Server

```bash
sudo docker start qdrant
```

### Restart Server

```bash
sudo docker restart qdrant
```

### View Logs

```bash
sudo docker logs qdrant

# Follow logs in real-time
sudo docker logs -f qdrant
```

### Remove Container (if needed)

```bash
# Stop and remove container
sudo docker stop qdrant
sudo docker rm qdrant

# Start fresh
sudo docker run -d --name qdrant -p 6333:6333 -p 6334:6334 \
  -v /raid/qdrant_storage:/qdrant/storage qdrant/qdrant
```

---

## Qdrant Dashboard

Qdrant provides a web dashboard!

**Access it:**
```
http://localhost:6334/dashboard
```

**Features:**
- View collections
- Browse data points
- Check cluster status
- Monitor performance

---

## Auto-Start on Boot (Optional)

To make Qdrant start automatically when sextus boots:

```bash
# Remove current container
sudo docker stop qdrant
sudo docker rm qdrant

# Recreate with restart policy
sudo docker run -d \
  --name qdrant \
  --restart unless-stopped \
  -p 6333:6333 \
  -p 6334:6334 \
  -v /raid/qdrant_storage:/qdrant/storage \
  qdrant/qdrant
```

**Now Qdrant will start automatically on reboot!**

---

## Performance Comparison

### Local Mode:
- Direct file access
- Fast for single user
- Locks storage (no concurrent access)
- ~200MB RAM

### Server Mode:
- Network protocol (localhost, still fast)
- Multiple concurrent clients ✓
- Better caching
- ~200MB RAM + ~50MB per client

**Your use case:** Server is better (need concurrent CLI + Web UI)

---

## Troubleshooting

### Connection Refused

**Error:** `Connection refused` when connecting

**Fix:**
```bash
# Check if container is running
sudo docker ps | grep qdrant

# If not running, start it
sudo docker start qdrant

# Check logs for errors
sudo docker logs qdrant
```

### Port Already in Use

**Error:** `Port 6333 is already allocated`

**Fix:**
```bash
# Find what's using the port
sudo lsof -i :6333

# Kill the process or use different port
sudo docker run -d --name qdrant -p 6335:6333 -p 6336:6334 \
  -v /raid/qdrant_storage:/qdrant/storage qdrant/qdrant

# Update config.py:
# QDRANT_PORT = 6335
```

### Permission Denied

**Error:** `Permission denied` accessing /raid/qdrant_storage

**Fix:**
```bash
# Check ownership
ls -ld /raid/qdrant_storage

# Fix permissions (if needed)
sudo chown -R $USER:$USER /raid/qdrant_storage

# Or make readable by all
sudo chmod -R 755 /raid/qdrant_storage
```

### Old Data Not Visible

**Problem:** Server can't see your indexed data

**Check:**
```bash
# Verify storage is mounted
sudo docker inspect qdrant | grep -A5 Mounts

# Should show:
# "Source": "/raid/qdrant_storage",
# "Destination": "/qdrant/storage",
```

**Fix:**
```bash
# Recreate container with correct volume
sudo docker stop qdrant
sudo docker rm qdrant
sudo docker run -d --name qdrant -p 6333:6333 -p 6334:6334 \
  -v /raid/qdrant_storage:/qdrant/storage qdrant/qdrant
```

---

## Reverting to Local Mode (If Needed)

If you need to go back to local mode:

```bash
# 1. Stop Qdrant server
sudo docker stop qdrant

# 2. Update config.py
# Uncomment QDRANT_PATH, comment out QDRANT_HOST/PORT

# 3. Use old code files
# (But new code works with both modes!)
```

---

## Benefits You Now Have

✅ **Concurrent access** - Web UI + CLI simultaneously  
✅ **Better debugging** - Can inspect index while web UI runs  
✅ **Production ready** - Same setup used in production  
✅ **Dashboard** - Visual interface at :6334/dashboard  
✅ **Better performance** - Optimized server caching  
✅ **Auto-restart** - Survives reboots (if configured)  

---

## Next Steps: GPS Bug Investigation

Now that you can use CLI + Web UI simultaneously:

```bash
# Terminal 1: Keep web UI running
python search_web.py

# Terminal 2: Run diagnostics
python src/photo_index/cli/show_index.py /raid/photos/IMG_4681.JPG
python find_by_gps.py 46.401761 -64.102203

# Compare results and find the GPS bug!
```

---

## Summary

**What we did:**
1. Started Qdrant server in Docker ✓
2. Updated code to support server mode ✓
3. Now you can use CLI + Web UI simultaneously ✓

**What you need to do:**
1. Copy updated files to src/photo_index/
2. Test with test_qdrant_connection.py
3. Start debugging that GPS bug!

Enjoy concurrent access! 🎉
