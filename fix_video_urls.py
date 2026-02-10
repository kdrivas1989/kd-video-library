#!/usr/bin/env python3
"""
Fix video URLs to point to Backblaze B2 instead of old AWS S3.
"""

import os
import sys
import re

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(script_dir, '.env'))

from supabase import create_client

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
B2_BUCKET = os.getenv('B2_BUCKET')

# Old AWS S3 URL pattern
OLD_PATTERN = r'https://uspa-video-library\.s3\.us-east-2\.amazonaws\.com/'
# New B2 URL format
NEW_BASE = f'https://f005.backblazeb2.com/file/{B2_BUCKET}/'


def get_all_videos(supabase):
    """Get all videos from database."""
    videos = []
    offset = 0

    while True:
        result = supabase.table('videos').select('id, url, thumbnail').range(offset, offset + 999).execute()
        if not result.data:
            break
        videos.extend(result.data)
        if len(result.data) < 1000:
            break
        offset += 1000

    return videos


def fix_url(url):
    """Convert old AWS S3 URL to B2 URL."""
    if not url:
        return url

    if re.match(OLD_PATTERN, url):
        return re.sub(OLD_PATTERN, NEW_BASE, url)

    return url


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Fix video URLs to point to B2')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    args = parser.parse_args()

    print("Connecting to Supabase...")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("Fetching all videos...")
    videos = get_all_videos(supabase)
    print(f"Found {len(videos)} videos")

    # Find videos with old AWS URLs
    to_fix = []
    for v in videos:
        url = v.get('url', '') or ''
        thumb = v.get('thumbnail', '') or ''

        needs_fix = False
        new_url = fix_url(url)
        new_thumb = fix_url(thumb)

        if new_url != url or new_thumb != thumb:
            to_fix.append({
                'id': v['id'],
                'old_url': url,
                'new_url': new_url,
                'old_thumb': thumb,
                'new_thumb': new_thumb
            })

    print(f"Videos needing URL fix: {len(to_fix)}")

    if not to_fix:
        print("No URLs to fix!")
        return

    if args.dry_run:
        print("\n=== DRY RUN ===")
        for v in to_fix[:5]:
            print(f"\n{v['id']}:")
            print(f"  OLD: {v['old_url'][:80]}...")
            print(f"  NEW: {v['new_url'][:80]}...")
        if len(to_fix) > 5:
            print(f"\n... and {len(to_fix) - 5} more")
        return

    # Fix URLs
    success = 0
    failed = 0

    for i, v in enumerate(to_fix, 1):
        print(f"[{i}/{len(to_fix)}] {v['id']}...", end=' ', flush=True)

        try:
            update_data = {}
            if v['new_url'] != v['old_url']:
                update_data['url'] = v['new_url']
            if v['new_thumb'] != v['old_thumb']:
                update_data['thumbnail'] = v['new_thumb']

            supabase.table('videos').update(update_data).eq('id', v['id']).execute()
            print("OK")
            success += 1
        except Exception as e:
            print(f"FAILED: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Complete: {success} fixed, {failed} failed")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
