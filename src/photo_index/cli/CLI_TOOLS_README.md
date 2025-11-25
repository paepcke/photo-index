# Photo Index CLI Tools

Quick reference for command-line tools to work with your photo index.

## get_description.py
Generate AI description for a photo using Llama Vision.

**Basic usage:**
```bash
./get_description.py /raid/photos/IMG_1234.jpg
```

**With custom prompt:**
```bash
./get_description.py --prompt "What is the mood of this image?" /raid/photos/IMG_1234.jpg
```

**Raw output (no formatting):**
```bash
./get_description.py --raw /raid/photos/IMG_1234.jpg
```

---

## show_index.py
Display the indexed payload for a photo from Qdrant.

**Basic usage:**
```bash
./show_index.py /raid/photos/IMG_1234.jpg
```

**JSON output:**
```bash
./show_index.py --json /raid/photos/IMG_1234.jpg
```

**Custom Qdrant path:**
```bash
./show_index.py --qdrant-path /custom/path /raid/photos/IMG_1234.jpg
```

---

## get_exif.py
Extract and display EXIF metadata from a photo.

**Basic usage:**
```bash
./get_exif.py /raid/photos/IMG_1234.jpg
```

**Include all raw EXIF tags:**
```bash
./get_exif.py --raw /raid/photos/IMG_1234.jpg
```

**Include geocoded location (needs API key):**
```bash
./get_exif.py --gps /raid/photos/IMG_1234.jpg
```

**JSON output:**
```bash
./get_exif.py --json /raid/photos/IMG_1234.jpg
```

---

## delete_photo.py
Delete photos from index and optionally from disk.

**Delete from index only:**
```bash
./delete_photo.py /raid/photos/IMG_1234.jpg
```

**Delete multiple photos:**
```bash
./delete_photo.py /raid/photos/IMG_1234.jpg /raid/photos/IMG_5678.jpg
```

**Delete from index AND disk (with confirmation):**
```bash
./delete_photo.py --delete-file /raid/photos/IMG_1234.jpg
# or short form:
./delete_photo.py -d /raid/photos/IMG_1234.jpg
```

**Delete without confirmation:**
```bash
./delete_photo.py -d -y /raid/photos/IMG_1234.jpg
```

**Dry run (see what would be deleted):**
```bash
./delete_photo.py --dry-run -d /raid/photos/IMG_1234.jpg
```

---

## Installation

1. Make scripts executable:
```bash
chmod +x get_description.py show_index.py get_exif.py delete_photo.py
```

2. Optionally create symlinks in your PATH:
```bash
sudo ln -s $(pwd)/get_description.py /usr/local/bin/photo-describe
sudo ln -s $(pwd)/show_index.py /usr/local/bin/photo-show
sudo ln -s $(pwd)/get_exif.py /usr/local/bin/photo-exif
sudo ln -s $(pwd)/delete_photo.py /usr/local/bin/photo-delete
```

## Notes

- All tools require your photo_index package to be installed
- `get_description.py` loads the full Llama model (takes ~10 seconds, uses GPU)
- `show_index.py` and `delete_photo.py` need access to your Qdrant storage
- `get_exif.py --gps` requires Google Maps API key in `~/.ssh/googleMapsGeoCodingAPIKey.txt`
