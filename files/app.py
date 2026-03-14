"""
pip install flask flask-cors Pillow
TODO: Improve speed by caching thumbnails and metadata, and by using a more efficient image processing library if needed.

Photo Gallery Backend
Run on your laptop: python3 app.py
"""

from flask import Flask, jsonify, send_file, request, send_from_directory
from flask_cors import CORS
from PIL import Image
import os
import io
import hashlib
import json
from datetime import datetime
from pathlib import Path

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION ---
PHOTOS_DIR = os.environ.get('PHOTOS_DIR', r'\\100.85.128.110\\fotos\\nastst')  # Change this!
CACHE_DIR = os.path.join(os.path.dirname(__file__), '.thumb_cache')
THUMBNAIL_SIZE = (250, 250)  # Smaller = faster over slow connections
THUMB_QUALITY = 70           # Lower quality = smaller file size (~8-12KB each)
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif'}

os.makedirs(CACHE_DIR, exist_ok=True)

def get_thumb_path(photo_path):
    h = hashlib.md5(photo_path.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{h}.jpg")

def generate_thumbnail(photo_path):
    thumb_path = get_thumb_path(photo_path)
    if os.path.exists(thumb_path):
        return thumb_path
    try:
        with Image.open(photo_path) as img:
            img = img.convert('RGB')
            img.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)
            img.save(thumb_path, 'JPEG', quality=THUMB_QUALITY, optimize=True)
        return thumb_path
    except Exception as e:
        print(f"Error generating thumbnail for {photo_path}: {e}")
        return None

def get_photo_date(photo_path):
    try:
        from PIL.ExifTags import TAGS
        with Image.open(photo_path) as img:
            exif = img._getexif()
            if exif:
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag == 'DateTimeOriginal':
                        return value
    except:
        pass
    mtime = os.path.getmtime(photo_path)
    return datetime.fromtimestamp(mtime).strftime('%Y:%m:%d %H:%M:%S')

@app.route('/')
def index():
    return send_from_directory(os.path.dirname(__file__), 'index.html')

@app.route('/api/albums')
def get_albums():
    albums = []
    photos_path = Path(PHOTOS_DIR)
    """ DEBUG STUFF
    print(f"DEBUG: Checking path: {photos_path}")
    print(f"DEBUG: Path exists: {photos_path.exists()}")
    
    if not photos_path.exists():
        return jsonify({'error': f'Photos directory not found: {PHOTOS_DIR}'}), 404
    """
    # Root-level photos as "Unsorted" album
    root_photos = [f for f in photos_path.iterdir() 
                   if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS]
    if root_photos:
        albums.append({
            'id': '__root__',
            'name': 'Unsorted',
            'path': '',
            'count': len(root_photos),
            'cover': f'/api/thumbnail?path={root_photos[0]}'
        })

    # Subfolders as albums
    for folder in sorted(photos_path.iterdir()):
        print(f"DEBUG: Found item: {folder.name}, is_dir: {folder.is_dir()}")
        if folder.is_dir() and not folder.name.startswith('.'):
            photos = [f for f in folder.iterdir() 
                      if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS]
            # Also check one level deeper
            for subfolder in folder.iterdir():
                if subfolder.is_dir():
                    photos += [f for f in subfolder.iterdir() 
                               if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS]
            if photos:
                cover = photos[0]
                albums.append({
                    'id': folder.name,
                    'name': folder.name.replace('_', ' ').replace('-', ' ').title(),
                    'path': str(folder.relative_to(photos_path)),
                    'count': len(photos),
                    'cover': f'/api/thumbnail?path={cover}'
                })
    
    print(f"DEBUG: Total albums found: {len(albums)}")
    return jsonify(albums)

@app.route('/api/photos')
def get_photos():
    album_id = request.args.get('album', '__root__')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    
    photos_path = Path(PHOTOS_DIR)
    
    if album_id == '__root__':
        folder = photos_path
        files = [f for f in folder.iterdir() 
                 if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS]
    else:
        folder = photos_path / album_id
        if not folder.exists():
            return jsonify({'error': 'Album not found'}), 404
        files = []
        for f in folder.rglob('*'):
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append(f)

    files.sort(key=lambda f: f.name)
    
    total = len(files)
    start = (page - 1) * per_page
    end = start + per_page
    page_files = files[start:end]
    
    photos = []
    for f in page_files:
        photos.append({
            'id': str(f.relative_to(photos_path)),
            'filename': f.name,
            'thumbnail': f'/api/thumbnail?path={f}',
            'full': f'/api/photo?path={f}',
            'date': get_photo_date(str(f)),
            'size': f.stat().st_size,
        })
    
    return jsonify({
        'photos': photos,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page
    })

@app.route('/api/thumbnail')
def get_thumbnail():
    path = request.args.get('path')
    if not path or not os.path.exists(path):
        return jsonify({'error': 'Not found'}), 404
    # Security: ensure path is inside PHOTOS_DIR
    if not os.path.abspath(path).startswith(os.path.abspath(PHOTOS_DIR)):
        return jsonify({'error': 'Forbidden'}), 403
    
    thumb = generate_thumbnail(path)
    if not thumb:
        return jsonify({'error': 'Could not generate thumbnail'}), 500
    response = send_file(thumb, mimetype='image/jpeg')
    response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response
@app.route('/api/photo')
def get_photo():
    path = request.args.get('path')
    if not path or not os.path.exists(path):
        return jsonify({'error': 'Not found'}), 404
    if not os.path.abspath(path).startswith(os.path.abspath(PHOTOS_DIR)):
        return jsonify({'error': 'Forbidden'}), 403
    response = send_file(path)
    response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response
if __name__ == '__main__':
    print(f"📸 Photo Gallery Backend")
    print(f"   Photos directory: {PHOTOS_DIR}")
    print(f"   Thumbnail cache:  {CACHE_DIR}")
    print(f"   Running at:       http://0.0.0.0:5000")
    print(f"\n   Set your photos path with:")
    print(f"   PHOTOS_DIR=/your/photos python3 app.py\n")
    app.run(host='0.0.0.0', port=5000, debug=False)
