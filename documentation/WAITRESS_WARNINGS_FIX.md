# Waitress Server Warnings - Explained & Fixed

## What Are Those Warnings?

```
WARNING:waitress.queue:Task queue depth is 1
WARNING:waitress.queue:Task queue depth is 2
```

These are **Waitress WSGI server** warnings indicating that HTTP requests are queuing up faster than the server can process them.

**Not critical!** But annoying in your terminal.

---

## Why Does This Happen?

### Cause 1: Autocomplete Makes Multiple Requests

When you type in a search field, autocomplete fetches from multiple fields:

```
Type "b" in search box:
  → GET /facets/description_parsed.objects     (1000 values)
  → GET /facets/description_parsed.materials   (1000 values)
  → GET /facets/description_parsed.setting     (1000 values)
  → GET /facets/description_parsed.visual_attributes (1000 values)
```

**4 concurrent requests** = queue builds up

### Cause 2: Image Search Blocks Server

When you do an image similarity search:
```
1. Upload image
2. Load vision model (~10 seconds first time)
3. Generate embedding (~2-3 seconds)
4. Search Qdrant
```

During model loading, other requests queue up.

### Cause 3: Default Thread Count Too Low

Waitress default: **4 threads**  
Your usage: Multiple autocomplete requests + image searches = **needs more!**

---

## ✅ Solution Applied (In New Release)

Updated `search_web.py` with better Waitress configuration:

```python
serve(
    app, 
    host=args.host, 
    port=args.port,
    threads=8,              # ← Doubled from 4 to 8
    channel_timeout=300,    # ← 5 min for slow operations
    connection_limit=100,   # ← Max connections
    asyncore_use_poll=True  # ← Better Linux performance
)
```

**Result:** 
- More threads = handles concurrent requests better
- Longer timeout = no timeouts during model loading
- Fewer warnings!

---

## Additional Options (If Still Seeing Warnings)

### Option 1: Suppress Waitress Logging (Quick Fix)

Add to top of `search_web.py`:

```python
import logging

# Suppress Waitress queue warnings
logging.getLogger('waitress.queue').setLevel(logging.ERROR)
```

**Pro:** Clean terminal  
**Con:** Hides potentially useful info

### Option 2: Increase Threads Further

If you have many users or heavy usage:

```python
serve(
    app,
    threads=16,  # Even more threads
    ...
)
```

**Pro:** Better concurrency  
**Con:** Uses more RAM (~50MB per thread)

### Option 3: Use Gunicorn Instead

Alternative WSGI server with worker processes:

```bash
# Install
pip install gunicorn

# Run
gunicorn -w 4 -b 0.0.0.0:5000 search_web:app
```

**Pro:** Better for production  
**Con:** Linux/Mac only, more complex

---

## When To Worry About These Warnings

**Don't worry if:**
- Warnings appear occasionally
- Depth is low (1-3)
- Searches still work fine

**Do investigate if:**
- Warnings are constant
- Depth is high (10+)
- Searches are timing out
- Server becomes unresponsive

---

## Performance Tips

### 1. Lazy Model Loading (Already Implemented)

Vision model only loads on first image search:

```python
def get_searcher():
    global _searcher
    if _searcher is None:
        _searcher = PhotoSearch()
    return _searcher
```

**Benefit:** Fast startup, model loads when needed

### 2. Autocomplete Caching (Already Implemented)

Autocomplete caches results per field:

```javascript
this.cache = {};  // Results cached here
```

**Benefit:** Repeated typing doesn't re-fetch

### 3. Debounced Keystrokes (Already Implemented)

300ms delay before fetching:

```javascript
this.debounceMs = 300;  // Wait 300ms
```

**Benefit:** Fewer requests while typing

### 4. Consider Redis Cache (Future Enhancement)

Cache facet results in Redis:

```python
# Pseudocode
@cache.memoize(timeout=3600)  # 1 hour
def get_facets(field):
    return searcher.get_facets(field)
```

**Benefit:** Much faster autocomplete

---

## Test the Fix

```bash
# 1. Extract new version
tar xzf web_ui.tar.gz

# 2. Restart server
python search_web.py

# 3. Test autocomplete
# Type in search box
# → Should see fewer/no warnings!

# 4. Do image search
# Model loads (~10s)
# → Should handle it smoothly
```

---

## Technical Details

### Waitress Architecture

```
Client Request
      ↓
   Waitress
      ↓
Task Queue ← [warnings appear here if queue > 0]
      ↓
Thread Pool (now 8 threads)
      ↓
   Flask App
      ↓
Your Code
```

### Why Queuing Happens

1. **Request arrives** → Added to queue
2. **Thread available** → Process request
3. **Thread busy** → Request stays in queue
4. **Queue depth > 0** → Waitress logs warning

### Our Optimization

**Before:**
- 4 threads
- Autocomplete makes 4 concurrent requests
- All threads busy
- 5th request → queue warning

**After:**
- 8 threads  
- Autocomplete makes 4 concurrent requests
- 4 threads busy, 4 available
- No queue warnings!

---

## Comparison: Server Options

| Server | Threads | Performance | Complexity | Use Case |
|--------|---------|-------------|------------|----------|
| **Waitress** (current) | 8 | Good | Simple | Single user, dev |
| **Gunicorn** | 4 workers | Better | Medium | Multi-user, prod |
| **uWSGI** | Configurable | Best | Complex | High traffic |
| **Flask dev** | 1 | Poor | Simplest | Debug only |

**Recommendation:** Stick with Waitress for your use case (single/few users)

---

## Monitoring

### Check Thread Usage

Add to `search_web.py`:

```python
import threading

@app.route('/health')
def health():
    return jsonify({
        'active_threads': threading.active_count(),
        'status': 'ok'
    })
```

Visit: `http://localhost:5000/health`

### Log Slow Requests

Add timing middleware:

```python
import time
from flask import g, request

@app.before_request
def before_request():
    g.start = time.time()

@app.after_request
def after_request(response):
    if hasattr(g, 'start'):
        diff = time.time() - g.start
        if diff > 1.0:  # Log if > 1 second
            print(f"Slow request: {request.path} took {diff:.2f}s")
    return response
```

---

## Summary

**What changed:**
- ✅ Increased Waitress threads: 4 → 8
- ✅ Increased timeout: 120s → 300s
- ✅ Added connection limit: 100
- ✅ Enabled asyncore_use_poll for better performance

**Expected result:**
- Fewer/no queue warnings
- Better handling of concurrent autocomplete requests
- No timeouts during image searches

**Still seeing warnings?**
- Use Option 1 (suppress logging) from above
- Or increase threads to 16
- Or switch to Gunicorn for production

---

## Files Updated

- `search_web.py` - Waitress configuration improved

---

Enjoy a quieter, faster server! 🚀
