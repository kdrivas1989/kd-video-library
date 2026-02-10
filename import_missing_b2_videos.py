#!/usr/bin/env python3
"""
Import videos that exist in B2 storage but are not in the database.
This script scans B2, compares with database, and creates entries for missing videos.
"""

import os
import sys
import re
from datetime import datetime

# Add parent directory to path to import app modules
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

# Load .env file before importing app
from dotenv import load_dotenv
load_dotenv(os.path.join(script_dir, '.env'))

import boto3
from botocore.config import Config
from supabase import create_client

# B2 Configuration
B2_ENDPOINT = os.getenv('B2_ENDPOINT')
B2_KEY_ID = os.getenv('B2_KEY_ID')
B2_APPLICATION_KEY = os.getenv('B2_APPLICATION_KEY')
B2_BUCKET = os.getenv('B2_BUCKET')

# Supabase Configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Category mapping based on folder/filename patterns
CATEGORY_MAPPING = {
    '4way': 'fs',
    '4-way': 'fs',
    '8way': 'fs',
    '8-way': 'fs',
    'vfs': 'fs',
    'fs': 'fs',
    'cf': 'cf',
    'ae': 'ae',
    'freestyle': 'ae',
    'freefly': 'ae',
    'nationals': 'fs',
}

SUBCATEGORY_MAPPING = {
    '4way': 'fs_4way_fs',
    '4-way': 'fs_4way_fs',
    '8way': 'fs_8way',
    '8-way': 'fs_8way',
    'vfs': 'fs_4way_vfs',
    '2way_vfs': 'fs_4way_vfs',
    'cf2': 'cf_2way_open',
    'cf4': 'cf_4way_seq',
}


def get_b2_client():
    """Create B2/S3 client."""
    return boto3.client(
        's3',
        endpoint_url=B2_ENDPOINT,
        aws_access_key_id=B2_KEY_ID,
        aws_secret_access_key=B2_APPLICATION_KEY,
        config=Config(signature_version='s3v4')
    )


def get_all_b2_videos(s3_client):
    """Get all video files from B2."""
    paginator = s3_client.get_paginator('list_objects_v2')
    videos = {}

    for page in paginator.paginate(Bucket=B2_BUCKET):
        for obj in page.get('Contents', []):
            key = obj['Key']
            if key.endswith(('.mp4', '.webm', '.mov', '.m4v')) and 'thumb' not in key.lower():
                videos[key] = obj

    return videos


def get_db_video_keys(supabase):
    """Get all video S3 keys from database."""
    db_keys = set()
    offset = 0
    batch_size = 1000

    while True:
        result = supabase.table('videos').select('id, url').range(offset, offset + batch_size - 1).execute()
        if not result.data:
            break

        for v in result.data:
            url = v.get('url', '') or ''
            # Extract key from URL
            if '.amazonaws.com/' in url:
                key = url.split('.amazonaws.com/')[1]
                db_keys.add(key)
            elif 'backblaze' in url.lower() and '/file/' in url:
                parts = url.split('/file/')
                if len(parts) > 1:
                    key = '/'.join(parts[1].split('/')[1:])
                    db_keys.add(key)

        if len(result.data) < batch_size:
            break
        offset += batch_size

    return db_keys


def parse_metadata_from_key(s3_key):
    """Parse video metadata from S3 key path."""
    # Example keys:
    # 2018_USPA_Nationals/3_163_1601_6.mp4
    # uncategorized/abc123.mp4
    # fs/4way/video.mp4

    parts = s3_key.split('/')
    folder = parts[0] if len(parts) > 1 else ''
    filename = parts[-1]
    name_without_ext = os.path.splitext(filename)[0]

    # Try to use app's detection logic if available
    try:
        from app import detect_category_from_filename, parse_filename_metadata
        detected_cat, detected_sub, detected_event = detect_category_from_filename(name_without_ext)
        file_meta = parse_filename_metadata(filename, folder)

        category = detected_cat or file_meta.get('category') or 'uncategorized'
        subcategory = detected_sub or file_meta.get('subcategory') or ''
        event = detected_event or file_meta.get('event') or folder.replace('_', ' ')
        team = file_meta.get('team') or file_meta.get('team_number') or ''
        round_num = file_meta.get('round') or ''

        title = name_without_ext.replace('_', ' ')
        if event and event not in title:
            title = f"{event} - {title}"

        return {
            'category': category,
            'subcategory': subcategory,
            'event': event,
            'title': title,
            'round_num': round_num,
            'team': team,
            'jump_num': file_meta.get('jump') or '',
            's3_key': s3_key,
        }
    except ImportError:
        pass

    # Fallback: basic detection
    category = 'uncategorized'
    subcategory = ''
    folder_lower = folder.lower()

    for pattern, cat in CATEGORY_MAPPING.items():
        if pattern in folder_lower:
            category = cat
            break

    for pattern, subcat in SUBCATEGORY_MAPPING.items():
        if pattern in folder_lower or pattern in name_without_ext.lower():
            subcategory = subcat
            break

    # Try to extract event name from folder
    event = folder.replace('_', ' ') if folder else ''

    # Try to parse structured filename: round_team_jump_camera.mp4
    # Example: 3_163_1601_6.mp4
    round_num = ''
    team = ''
    jump_num = ''

    filename_parts = name_without_ext.split('_')
    if len(filename_parts) >= 3:
        # Pattern: round_day_team_jump
        round_num = filename_parts[0]
        if len(filename_parts) >= 4:
            team = filename_parts[2]
            jump_num = filename_parts[1]

    # Create readable title
    title = name_without_ext.replace('_', ' ')
    if event:
        title = f"{event} - {title}"

    return {
        'category': category,
        'subcategory': subcategory,
        'event': event,
        'title': title,
        'round_num': round_num,
        'team': team,
        'jump_num': jump_num,
        's3_key': s3_key,
    }


def generate_video_id():
    """Generate 8-char UUID."""
    import uuid
    return str(uuid.uuid4())[:8]


def build_video_url(s3_key):
    """Build the video URL from S3 key."""
    # Using AWS S3 URL format (same as existing videos in DB)
    return f"https://uspa-video-library.s3.us-east-2.amazonaws.com/{s3_key}"


def import_video(supabase, s3_key, metadata, dry_run=False):
    """Import a single video to the database."""
    video_id = generate_video_id()
    video_url = build_video_url(s3_key)

    video_data = {
        'id': video_id,
        'title': metadata['title'][:255],  # Truncate if too long
        'description': f"Imported from B2: {metadata['event']}" if metadata['event'] else 'Imported from B2 storage',
        'url': video_url,
        'thumbnail': '',  # No thumbnail yet
        'category': metadata['category'],
        'subcategory': metadata['subcategory'],
        'tags': metadata['event'].replace(' ', ',') if metadata['event'] else '',
        'duration': None,
        'created_at': datetime.now().isoformat(),
        'views': 0,
        'video_type': 's3',
        'local_file': '',
        'event': metadata['event'],
        'team': metadata['team'],
        'round_num': metadata['round_num'],
        'jump_num': metadata['jump_num'],
    }

    if dry_run:
        print(f"  [DRY RUN] Would import: {video_id} - {metadata['title'][:50]}")
        return True

    try:
        supabase.table('videos').insert(video_data).execute()
        return True
    except Exception as e:
        print(f"  Error importing {s3_key}: {e}")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Import missing B2 videos to database')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be imported without actually importing')
    parser.add_argument('--limit', type=int, default=0, help='Limit number of videos to import (0 = all)')
    parser.add_argument('--filter', type=str, default='', help='Only import videos matching this pattern')
    args = parser.parse_args()

    print("Connecting to B2 and Supabase...")

    s3_client = get_b2_client()
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("Fetching videos from B2...")
    b2_videos = get_all_b2_videos(s3_client)
    print(f"  Found {len(b2_videos)} videos in B2")

    print("Fetching videos from database...")
    db_keys = get_db_video_keys(supabase)
    print(f"  Found {len(db_keys)} videos in database")

    # Find missing videos
    missing_keys = set(b2_videos.keys()) - db_keys
    print(f"\nVideos in B2 but not in database: {len(missing_keys)}")

    if args.filter:
        missing_keys = {k for k in missing_keys if args.filter.lower() in k.lower()}
        print(f"After filter '{args.filter}': {len(missing_keys)} videos")

    if not missing_keys:
        print("No videos to import!")
        return

    # Apply limit
    if args.limit > 0:
        missing_keys = set(sorted(missing_keys)[:args.limit])
        print(f"Limited to: {len(missing_keys)} videos")

    if args.dry_run:
        print("\n=== DRY RUN MODE ===\n")

    # Import videos
    success = 0
    failed = 0

    for i, s3_key in enumerate(sorted(missing_keys), 1):
        metadata = parse_metadata_from_key(s3_key)
        print(f"[{i}/{len(missing_keys)}] {s3_key}")

        if import_video(supabase, s3_key, metadata, dry_run=args.dry_run):
            success += 1
        else:
            failed += 1

    print(f"\n{'='*60}")
    if args.dry_run:
        print(f"DRY RUN Complete: {success} would be imported")
    else:
        print(f"Complete: {success} imported, {failed} failed")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
