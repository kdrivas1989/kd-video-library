#!/usr/bin/env python3
"""
Generate thumbnails for videos that are missing them.
"""

import os
import sys
import time

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(script_dir, '.env'))

from supabase import create_client

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')


def get_videos_missing_thumbnails(supabase):
    """Get all videos without thumbnails."""
    videos = []
    offset = 0

    while True:
        result = supabase.table('videos').select('id, url, thumbnail, video_type').range(offset, offset + 999).execute()
        if not result.data:
            break

        for v in result.data:
            thumb = v.get('thumbnail', '') or ''
            if not thumb.strip() and v.get('video_type') == 's3' and v.get('url'):
                videos.append(v)

        if len(result.data) < 1000:
            break
        offset += 1000

    return videos


def generate_thumbnail(video_url, video_id):
    """Generate thumbnail from video URL."""
    import subprocess
    import tempfile

    # Import app functions
    from app import upload_to_s3, get_ffmpeg_path

    ffmpeg = get_ffmpeg_path()
    temp_thumb = None

    try:
        temp_thumb = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
        temp_thumb.close()

        result = subprocess.run([
            ffmpeg, '-y',
            '-ss', '2',
            '-i', video_url,
            '-vframes', '1',
            '-vf', 'scale=320:-1',
            temp_thumb.name
        ], capture_output=True, timeout=60)

        if result.returncode != 0:
            return None

        if not os.path.exists(temp_thumb.name) or os.path.getsize(temp_thumb.name) == 0:
            return None

        with open(temp_thumb.name, 'rb') as f:
            thumb_data = f.read()

        thumb_filename = f"{video_id}_thumb.jpg"
        thumb_url = upload_to_s3(thumb_data, thumb_filename, 'image/jpeg', 'thumbnails')

        return thumb_url

    except Exception as e:
        print(f"  Error: {e}")
        return None

    finally:
        if temp_thumb and os.path.exists(temp_thumb.name):
            try:
                os.unlink(temp_thumb.name)
            except:
                pass


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Generate missing thumbnails')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    parser.add_argument('--limit', type=int, default=0, help='Limit number to process')
    args = parser.parse_args()

    print("Connecting to Supabase...")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("Finding videos without thumbnails...")
    videos = get_videos_missing_thumbnails(supabase)
    print(f"Found {len(videos)} videos missing thumbnails")

    if not videos:
        return

    if args.limit > 0:
        videos = videos[:args.limit]
        print(f"Limited to {len(videos)} videos")

    if args.dry_run:
        print("\n=== DRY RUN ===")
        for v in videos[:10]:
            print(f"  Would generate: {v['id']}")
        if len(videos) > 10:
            print(f"  ... and {len(videos) - 10} more")
        return

    success = 0
    failed = 0

    for i, video in enumerate(videos, 1):
        video_id = video['id']
        url = video['url']

        print(f"[{i}/{len(videos)}] {video_id}...", end=' ', flush=True)

        thumb_url = generate_thumbnail(url, video_id)

        if thumb_url:
            # Update database with retry logic
            for retry in range(3):
                try:
                    supabase.table('videos').update({'thumbnail': thumb_url}).eq('id', video_id).execute()
                    print("OK")
                    success += 1
                    break
                except Exception as e:
                    if retry < 2:
                        print(f"RETRY({retry+1})...", end=' ', flush=True)
                        time.sleep(2 * (retry + 1))  # Backoff: 2s, 4s
                    else:
                        print(f"DB_ERROR: {str(e)[:50]}")
                        failed += 1
        else:
            print("FAILED")
            failed += 1

        # Small delay to avoid overwhelming the server
        time.sleep(0.5)

    print(f"\n{'='*60}")
    print(f"Complete: {success} generated, {failed} failed")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
