#!/usr/bin/env python3
"""
One-time migration: copy all data from Supabase → Railway Postgres.

Usage:
    export SUPABASE_URL=...
    export SUPABASE_KEY=...
    export DATABASE_URL=postgresql://...
    python migrate_to_postgres.py
"""

import os
import sys

from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
DATABASE_URL = os.environ.get('DATABASE_URL')

if not all([SUPABASE_URL, SUPABASE_KEY, DATABASE_URL]):
    print("ERROR: Set SUPABASE_URL, SUPABASE_KEY, and DATABASE_URL env vars")
    sys.exit(1)

from supabase import create_client
import psycopg2
import psycopg2.extras

sb = create_client(SUPABASE_URL, SUPABASE_KEY)


def fetch_all(table_name, order_col='id'):
    """Fetch all rows from Supabase table using cursor-based pagination."""
    all_rows = []
    batch_size = 500
    last_id = None

    while True:
        query = sb.table(table_name).select('*').order(order_col, desc=False).limit(batch_size)
        if last_id is not None:
            query = query.gt(order_col, last_id)
        result = query.execute()
        if not result.data:
            break
        all_rows.extend(result.data)
        last_id = result.data[-1][order_col]
        if len(result.data) < batch_size:
            break

    return all_rows


def get_pg_columns(cur, table_name):
    """Get column names for a Postgres table."""
    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
        (table_name,)
    )
    return {row[0] for row in cur.fetchall()}


# Columns that are boolean in Supabase but integer in our schema
BOOL_TO_INT_COLS = {'rejump', 'training_flag', 'exit_time_penalty', 'must_change_password'}


def insert_batch(cur, table_name, rows):
    """Batch insert rows into Postgres using execute_values."""
    if not rows:
        return 0

    # Only insert columns that exist in the target Postgres table
    pg_cols = get_pg_columns(cur, table_name)
    src_cols = list(rows[0].keys())
    cols = [c for c in src_cols if c in pg_cols]
    dropped = set(src_cols) - set(cols)
    if dropped:
        print(f"  Dropping extra columns: {dropped}")

    # Filter rows to only include valid columns + cast bools to ints
    clean_rows = []
    for row in rows:
        clean = {}
        for c in cols:
            val = row.get(c)
            if c in BOOL_TO_INT_COLS and isinstance(val, bool):
                val = int(val)
            clean[c] = val
        clean_rows.append(clean)

    col_str = ', '.join(f'"{c}"' for c in cols)
    template = '(' + ', '.join(f'%({c})s' for c in cols) + ')'
    sql = f'INSERT INTO "{table_name}" ({col_str}) VALUES %s ON CONFLICT DO NOTHING'
    psycopg2.extras.execute_values(
        cur, sql, clean_rows,
        template=template,
        page_size=100
    )
    return len(clean_rows)


TABLES = [
    'users',
    'videos',
    'competitions',
    'competition_teams',
    'competition_scores',
    'events',
    'video_assignments',
    'category_mappings',
    'event_folders',
]

# Tables where the order column is not 'id'
ORDER_COLS = {
    'users': 'username',
    'category_mappings': 'id',
    'event_folders': 'id',
}


def main():
    # First, create tables in Postgres
    print("=== Creating Postgres schema ===")
    # Import and run schema creation from app
    sys.path.insert(0, os.path.dirname(__file__))

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    # Create tables (same as init_postgres_schema in app.py)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT,
            url TEXT NOT NULL, thumbnail TEXT, category TEXT NOT NULL,
            subcategory TEXT, tags TEXT, duration TEXT, created_at TEXT NOT NULL,
            views INTEGER DEFAULT 0, video_type TEXT DEFAULT 'url', local_file TEXT,
            event TEXT, team TEXT, round_num TEXT, jump_num TEXT,
            start_time REAL DEFAULT 0, draw TEXT, trimmed BOOLEAN,
            category_auto BOOLEAN
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY, password TEXT NOT NULL, role TEXT NOT NULL,
            name TEXT NOT NULL, email TEXT, must_change_password INTEGER DEFAULT 0,
            signature_pin TEXT, signature_data TEXT, assigned_categories TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS competitions (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, event_type TEXT NOT NULL,
            event_types TEXT, total_rounds INTEGER DEFAULT 10, created_at TEXT NOT NULL,
            status TEXT DEFAULT 'active', event_rounds TEXT, chief_judge TEXT,
            chief_judge_pin TEXT, event_locations TEXT, event_dates TEXT, draws TEXT,
            ws_reference_points TEXT, ws_validation_window TEXT,
            ws_competitor_ref_points TEXT, ws_field_elevation REAL,
            score_approvals TEXT, artistic_difficulty_scores TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS competition_teams (
            id TEXT PRIMARY KEY, competition_id TEXT NOT NULL REFERENCES competitions(id),
            team_number TEXT NOT NULL, team_name TEXT NOT NULL, class TEXT NOT NULL,
            members TEXT, category TEXT, event TEXT, photo TEXT,
            created_at TEXT NOT NULL, display_order INTEGER DEFAULT 0
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS competition_scores (
            id TEXT PRIMARY KEY, competition_id TEXT NOT NULL REFERENCES competitions(id),
            team_id TEXT NOT NULL REFERENCES competition_teams(id),
            round_num INTEGER NOT NULL, score REAL, score_data TEXT, video_id TEXT,
            scored_by TEXT, created_at TEXT NOT NULL, rejump INTEGER DEFAULT 0,
            training_flag INTEGER DEFAULT 0, exit_time_penalty INTEGER DEFAULT 0
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, year INTEGER, disciplines TEXT,
            location TEXT, start_date TEXT, end_date TEXT, status TEXT DEFAULT 'active',
            created_at TEXT, created_by TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS video_assignments (
            id TEXT PRIMARY KEY, video_id TEXT NOT NULL REFERENCES videos(id),
            assigned_to TEXT NOT NULL REFERENCES users(username),
            assigned_by TEXT NOT NULL REFERENCES users(username),
            status TEXT DEFAULT 'pending', notes TEXT, created_at TEXT NOT NULL,
            scored_at TEXT, practice_score REAL, practice_score_data TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS category_mappings (
            id SERIAL PRIMARY KEY, pattern TEXT UNIQUE, category TEXT, subcategory TEXT,
            created_at TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS event_folders (
            id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL, created_at TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS conversion_jobs (
            job_id TEXT PRIMARY KEY, video_id TEXT, filename TEXT, title TEXT,
            status TEXT DEFAULT 'queued', progress INTEGER DEFAULT 0,
            session_id TEXT, created_at TEXT, completed_at TEXT, error TEXT,
            input_path TEXT, output_path TEXT, video_data TEXT, pid INTEGER
        )
    ''')
    print("Schema created.")

    # Migrate each table
    print("\n=== Migrating data ===")
    for table in TABLES:
        order_col = ORDER_COLS.get(table, 'id')
        print(f"\n--- {table} ---")
        try:
            rows = fetch_all(table, order_col)
        except Exception as e:
            print(f"  SKIP (fetch error): {e}")
            continue

        print(f"  Fetched {len(rows)} rows from Supabase")
        if not rows:
            continue

        try:
            count = insert_batch(cur, table, rows)
            print(f"  Inserted {count} rows into Postgres")
        except Exception as e:
            print(f"  ERROR inserting: {e}")
            conn.rollback()
            conn.autocommit = True

    # Verify counts
    print("\n=== Verification ===")
    for table in TABLES:
        cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        pg_count = cur.fetchone()[0]

        order_col = ORDER_COLS.get(table, 'id')
        try:
            sb_rows = fetch_all(table, order_col)
            sb_count = len(sb_rows)
        except Exception:
            sb_count = '?'

        match = "OK" if pg_count == sb_count else "MISMATCH"
        print(f"  {table}: Supabase={sb_count}, Postgres={pg_count} [{match}]")

    cur.close()
    conn.close()
    print("\nDone!")


if __name__ == '__main__':
    main()
