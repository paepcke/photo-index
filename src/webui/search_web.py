#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Flask web UI for photo search.

Usage:
    python search_web.py
    
Then open browser to: http://localhost:5000
"""

import os
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, url_for
from werkzeug.utils import secure_filename
import tempfile

from photo_search.photo_search import PhotoSearch, FilterBuilder

# Initialize Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

# Initialize searcher (lazy loaded)
_searcher = None

def get_searcher():
    """Get or create searcher instance."""
    global _searcher
    if _searcher is None:
        _searcher = PhotoSearch()
    return _searcher


@app.route('/')
def index():
    """Homepage with search interface."""
    return render_template('index.html')


@app.route('/search', methods=['POST'])
def search():
    """Execute search and return results."""
    try:
        searcher = get_searcher()
        
        # Get search parameters
        search_type = request.form.get('search_type', 'text')
        text_query = request.form.get('text_query', '').strip()
        limit = int(request.form.get('limit', 20))
        score_threshold = request.form.get('score_threshold')
        if score_threshold:
            score_threshold = float(score_threshold)
        
        # Build filters
        filters = []
        
        # Location filters
        city = request.form.get('location_city', '').strip()
        state = request.form.get('location_state', '').strip()
        country = request.form.get('location_country', '').strip()
        if city or state or country:
            location_filter = FilterBuilder.by_location(
                city=city if city else None,
                state=state if state else None,
                country=country if country else None
            )
            if location_filter:
                filters.append(location_filter)
        
        # Date filters (handled post-retrieval since dates are stored as strings)
        date_from = request.form.get('date_from', '').strip()
        date_to = request.form.get('date_to', '').strip()
        # Don't add to Qdrant filters - will filter results after retrieval
        
        # Camera filters
        camera_make = request.form.get('camera_make', '').strip()
        camera_model = request.form.get('camera_model', '').strip()
        if camera_make or camera_model:
            camera_filter = FilterBuilder.by_camera(
                make=camera_make if camera_make else None,
                model=camera_model if camera_model else None
            )
            if camera_filter:
                filters.append(camera_filter)
        
        combined_filter = FilterBuilder.combine_filters(*filters) if filters else None
        
        # Execute search based on type
        if search_type == 'image' and 'query_image' in request.files:
            # Image similarity search
            file = request.files['query_image']
            if file.filename:
                filename = secure_filename(file.filename)
                filepath = Path(app.config['UPLOAD_FOLDER']) / filename
                file.save(filepath)
                
                results = searcher.search_by_image(
                    filepath,
                    limit=limit,
                    filters=combined_filter,
                    score_threshold=score_threshold
                )
                
                # Clean up uploaded file
                filepath.unlink()
            else:
                return jsonify({'error': 'No image file provided'}), 400
        
        elif search_type == 'hybrid' and 'query_image' in request.files:
            # Hybrid search
            file = request.files['query_image']
            filepath = None
            
            if file.filename:
                filename = secure_filename(file.filename)
                filepath = Path(app.config['UPLOAD_FOLDER']) / filename
                file.save(filepath)
            
            results = searcher.search_hybrid(
                image_path=filepath,
                text_query=text_query if text_query else None,
                filters=combined_filter,
                limit=limit,
                score_threshold=score_threshold
            )
            
            # Clean up
            if filepath:
                filepath.unlink()
        
        else:
            # Text search or filter-only search
            if not text_query and not combined_filter:
                return jsonify({'error': 'No search query or filters provided'}), 400
            
            if text_query:
                # Text search with optional filters
                results = searcher.search_by_text(
                    text_query,
                    limit=limit,
                    filters=combined_filter
                )
            else:
                # Filter-only search
                results, _ = searcher.client.scroll(
                    collection_name=searcher.collection_name,
                    scroll_filter=combined_filter,
                    limit=limit,
                    with_payload=True,
                    with_vectors=False
                )
                results = searcher._format_results(results, include_score=False)
        
        # Apply date filtering post-retrieval (dates stored as strings, not in Qdrant filter)
        if date_from or date_to:
            if not date_from:
                date_from = '1900-01-01'
            if not date_to:
                date_to = '2100-12-31'
            
            # Add time component for inclusive comparison
            date_from_full = date_from + 'T00:00:00'  # Start of day
            date_to_full = date_to + 'T23:59:59'      # End of day
            
            # Filter results by date
            results = [
                r for r in results
                if r.get('date_taken') and 
                   date_from_full <= r['date_taken'] <= date_to_full
            ]
        
        # Format results for JSON
        formatted_results = []
        for result in results:
            formatted_results.append({
                'guid': result['guid'],
                'file_name': result['file_name'],
                'file_path': result['file_path'],
                'date_taken': result['date_taken'],
                'score': result.get('score'),
                'description': result.get('description'),
                'location': result.get('location'),
                'thumbnail_url': url_for('serve_photo', guid=result['guid'])
            })
        
        return jsonify({
            'results': formatted_results,
            'count': len(formatted_results)
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/photo/<guid>')
def photo_detail(guid):
    """Show detailed view of a photo."""
    try:
        searcher = get_searcher()
        photo = searcher.get_photo_by_guid(guid)
        
        if not photo:
            return "Photo not found", 404
        
        return render_template('photo_detail.html', photo=photo)
    
    except Exception as e:
        return f"Error: {e}", 500


@app.route('/serve/<guid>')
def serve_photo(guid):
    """Serve the actual photo file."""
    try:
        searcher = get_searcher()
        photo = searcher.get_photo_by_guid(guid)
        
        if not photo:
            return "Photo not found", 404
        
        file_path = Path(photo['file_path'])
        
        if not file_path.exists():
            return "Photo file not found on disk", 404
        
        return send_file(file_path, mimetype='image/jpeg')
    
    except Exception as e:
        return f"Error: {e}", 500


@app.route('/browse')
def browse_values():
    """Browse collection values page."""
    return render_template('browse_values.html')


@app.route('/similar/<guid>')
def find_similar(guid):
    """Find photos similar to a given photo by GUID."""
    try:
        searcher = get_searcher()
        limit = int(request.args.get('limit', 20))
        score_threshold = request.args.get('score_threshold')
        if score_threshold:
            score_threshold = float(score_threshold)
        
        # Get similar photos
        results = searcher.search_similar_to_guid(
            guid,
            limit=limit,
            score_threshold=score_threshold
        )
        
        # Format results for JSON
        formatted_results = []
        for result in results:
            formatted_results.append({
                'guid': result['guid'],
                'file_name': result['file_name'],
                'file_path': result['file_path'],
                'date_taken': result['date_taken'],
                'score': result.get('score'),
                'description': result.get('description'),
                'location': result.get('location'),
                'thumbnail_url': url_for('serve_photo', guid=result['guid'])
            })
        
        return jsonify({
            'results': formatted_results,
            'count': len(formatted_results)
        })
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/delete/<guid>', methods=['POST'])
def delete_photo(guid):
    """Delete a photo from the index and optionally from disk.
    
    Expects JSON body: {"delete_file": true/false}
    """
    try:
        # Parse request
        data = request.get_json() or {}
        delete_file = data.get('delete_file', False)
        
        searcher = get_searcher()
        
        # Get photo info
        photo = searcher.get_photo_by_guid(guid)
        
        if not photo:
            return jsonify({'error': 'Photo not found in index'}), 404
        
        file_path = Path(photo['file_path'])
        file_name = photo['file_name']
        
        # Delete from index
        from common.utils import Utils
        point_id = Utils.guid_to_point_id(guid)
        
        searcher.client.delete(
            collection_name=searcher.collection_name,
            points_selector=[point_id]
        )
        
        # Delete file if requested
        file_deleted = False
        if delete_file:
            if file_path.exists():
                try:
                    file_path.unlink()
                    file_deleted = True
                except Exception as e:
                    return jsonify({
                        'error': f'Removed from index but failed to delete file: {e}'
                    }), 500
            else:
                return jsonify({
                    'error': 'Removed from index but file not found on disk'
                }), 404
        
        # Build success message
        if file_deleted:
            message = f'Successfully deleted {file_name} from index and disk'
        else:
            message = f'Successfully removed {file_name} from index'
        
        return jsonify({
            'success': True,
            'message': message,
            'deleted_from_index': True,
            'deleted_from_disk': file_deleted
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/photo/<guid>/keywords', methods=['POST'])
def update_keywords(guid):
    """Update user keywords for a photo (writes to EXIF and updates index).

    Expects JSON body: {"keywords": ["tag1", "tag2", ...]}
    """
    try:
        # Parse request
        data = request.get_json() or {}
        keywords = data.get('keywords', [])

        if not isinstance(keywords, list):
            return jsonify({'error': 'keywords must be an array'}), 400

        # Sanitize keywords (strip whitespace, remove empty)
        # Also split on commas for defensive handling of comma-separated input
        sanitized = []
        for k in keywords:
            if isinstance(k, str):
                # Split on comma and strip each part
                for part in k.split(','):
                    cleaned = part.strip()
                    if cleaned:
                        sanitized.append(cleaned)
        keywords = sanitized

        searcher = get_searcher()

        # Get photo info
        photo = searcher.get_photo_by_guid(guid)

        if not photo:
            return jsonify({'error': 'Photo not found in index'}), 404

        file_path = Path(photo['file_path'])

        # Check file exists
        if not file_path.exists():
            return jsonify({'error': 'Photo file not found on disk'}), 404

        # Write keywords to EXIF
        from photo_index.exif_utils import ExifExtractor
        exif_extractor = ExifExtractor()

        success = exif_extractor.write_keywords(file_path, keywords)

        if not success:
            return jsonify({'error': 'Failed to write keywords to EXIF'}), 500

        # Update Qdrant index
        from common.utils import Utils
        point_id = Utils.guid_to_point_id(guid)

        # Update just the user_keywords field in the payload
        searcher.client.set_payload(
            collection_name=searcher.collection_name,
            payload={"user_keywords": keywords},
            points=[point_id]
        )

        return jsonify({
            'success': True,
            'message': f'Updated keywords for {photo["file_name"]}',
            'keywords': keywords
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/facets/<field>')
def get_facets(field):
    """Get facet values for a field."""
    try:
        searcher = get_searcher()
        limit = int(request.args.get('limit', 100))
        
        facets = searcher.get_facets(field, limit=limit)
        
        return jsonify(facets)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/stats')
def get_stats():
    """Get collection statistics."""
    try:
        searcher = get_searcher()
        stats = searcher.get_stats()
        
        return jsonify(stats)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def main():
    """Run the web server."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Photo Search Web UI')
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='Host to bind to (default: 0.0.0.0)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Port to bind to (default: 5000)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Run in debug mode (Flask dev server)'
    )
    
    args = parser.parse_args()
    
    if args.debug:
        # Development mode
        print(f"Starting Flask development server on http://{args.host}:{args.port}")
        app.run(host=args.host, port=args.port, debug=True)
    else:
        # Production mode with Waitress
        try:
            from waitress import serve
            print(f"Starting production server on http://{args.host}:{args.port}")
            print("Press Ctrl+C to stop")
            serve(
                app, 
                host=args.host, 
                port=args.port,
                threads=8,  # Increase from default 4 to handle concurrent requests
                channel_timeout=300,  # 5 minutes for slow operations (image embedding)
                connection_limit=100,  # Max concurrent connections
                asyncore_use_poll=True  # Better performance on Linux
            )
        except ImportError:
            print("Waitress not installed. Install with: pip install waitress")
            print("Falling back to Flask development server...")
            app.run(host=args.host, port=args.port)


if __name__ == '__main__':
    main()
