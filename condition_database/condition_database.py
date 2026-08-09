"""
condition_database.py

Runs between Indexer and Importer. For every file still sitting at
status 'located' in located_files.db:
    1. Computes a SHA-256 hash of its contents.
    2. Runs it through analyze_date() to get a date, confidence, and reasoning.
    3. Writes both back onto the row.

Once every file has been hashed, groups files by identical hash and marks
duplicates: the first file in each group stays 'located' (so Importer
will copy it normally); every other file in that group is marked
'duplicate' -- skipped from import, but never deleted or hidden. Nothing
about which copy is "correct" is decided here beyond that default pick;
a person can review and override it later.

This is file-type independent by design: hashing works identically for
any file, and analyze_date() already gracefully falls back to the
filesystem date for any type it doesn't have a smart signal for yet
(MP3, PDF, etc.) -- so pointing this at a folder of documents or audio
files works today, it just won't be as confident about the date as it is
for JPEG/TIFF until audio_tools/a future document_tools exist.

Usage:
    python3 condition_database.py condition_database/config.json
"""

import sys
import json
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime

# Make the project root importable regardless of the current working
# directory, matching the convention used by importer.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analyze_date.analyze_date import analyze_date


def load_config(config_file):
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_file}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Configuration file '{config_file}' is not valid JSON.")
        sys.exit(1)

    database_path = config.get('database_path')
    if not database_path:
        print("Error: 'database_path' must be specified in config.")
        sys.exit(1)

    return {
        'database_path': database_path,
        'output_report_path': config.get('output_report_path', 'condition_report.json'),
        'mismatch_threshold_days': config.get('mismatch_threshold_days', 1),
        'try_ocr': config.get('try_ocr', False),
    }


def ensure_column(conn, table, column, column_type):
    """Add a column to a table if it doesn't already exist (same pattern used everywhere else)."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cursor.fetchall()}
    if column not in existing:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
        conn.commit()


def format_size(num_bytes):
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}PB"


def compute_file_hash(file_path, file_size):
    """SHA-256 in 4MB chunks, with a live progress readout for large files -- same convention as audit_archive/duplicate_finder."""
    sha256 = hashlib.sha256()
    chunk_size = 4 * 1024 * 1024
    read_bytes = 0
    show_progress = file_size >= 20 * 1024 * 1024

    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha256.update(chunk)
            read_bytes += len(chunk)
            if show_progress:
                percent = (read_bytes / file_size) * 100
                print(f"\r    hashing: {format_size(read_bytes)} / {format_size(file_size)} ({percent:.1f}%)",
                      end='', flush=True)
    if show_progress:
        print()
    return sha256.hexdigest()


def get_readable_exif(file_path, file_extension):
    """Only meaningful for JPEG-family files -- returns {} for anything else, which analyze_date handles gracefully."""
    if file_extension not in ('.jpg', '.jpeg', '.thm'):
        return {}
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
        image = Image.open(file_path)
        raw = image._getexif()
        return {TAGS.get(k, k): v for k, v in raw.items()} if raw else {}
    except Exception:
        return {}


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 condition_database.py <config.json>")
        print("Example: python3 condition_database.py condition_database/config.json")
        sys.exit(1)

    config = load_config(sys.argv[1])
    database_path = config['database_path']

    print(f"Loading configuration from: {sys.argv[1]}")
    print(f"Database: {database_path}")
    print(f"try_ocr: {config['try_ocr']}")
    print("-" * 60)

    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    ensure_column(conn, 'located_files', 'confidence', 'INTEGER')
    ensure_column(conn, 'located_files', 'date_reason', 'TEXT')
    ensure_column(conn, 'located_files', 'date_source', 'TEXT')
    ensure_column(conn, 'located_files', 'date_taken', 'TEXT')

    # Only files not yet conditioned -- confidence IS NULL is the marker,
    # giving natural idempotency without needing a separate flag column.
    cursor.execute("SELECT * FROM located_files WHERE status = 'located' AND confidence IS NULL")
    rows = cursor.fetchall()

    if not rows:
        print("No unconditioned files found (status='located' AND confidence IS NULL). Nothing to do.")
        conn.close()
        return

    print(f"Found {len(rows)} file(s) to condition.")
    print("-" * 60)

    processed = 0
    failed = 0

    for idx, row in enumerate(rows, 1):
        file_path = row['file_path']
        file_id = row['id']
        path_obj = Path(file_path)

        if not path_obj.exists():
            print(f"[{idx}/{len(rows)}] MISSING: {file_path}")
            failed += 1
            continue

        print(f"[{idx}/{len(rows)}] {file_path}")

        try:
            file_size = path_obj.stat().st_size
            existing_hash = row['file_hash']
            file_hash = existing_hash if existing_hash else compute_file_hash(file_path, file_size)

            readable_exif = get_readable_exif(file_path, row['file_extension'])
            result = analyze_date({
                'file_path': file_path,
                'readable_exif': readable_exif,
                'mismatch_threshold_days': config['mismatch_threshold_days'],
                'try_ocr': config['try_ocr'],
            })

            cursor.execute('''
                UPDATE located_files
                SET file_hash = ?, confidence = ?, date_reason = ?, date_source = ?, date_taken = ?
                WHERE id = ?
            ''', (
                file_hash, result['confidence'], result['reason'], result['date_source'],
                result['date_taken'].isoformat() if result['date_taken'] else None,
                file_id
            ))
            conn.commit()

            print(f"    confidence={result['confidence']}  source={result['date_source']}  {result['reason']}")
            processed += 1

        except Exception as e:
            print(f"    FAILED: {e}")
            failed += 1

    print("-" * 60)
    print("Conditioning complete. Checking for duplicates...")

    # Group by hash among files that are still 'located' (freshly conditioned
    # this run, or from a prior run) -- only files actually eligible for
    # import are worth deduplicating.
    cursor.execute("SELECT id, file_path, file_hash FROM located_files WHERE status = 'located' AND file_hash IS NOT NULL")
    all_located = cursor.fetchall()

    by_hash = {}
    for row in all_located:
        by_hash.setdefault(row['file_hash'], []).append(row)

    duplicate_groups = {h: rows for h, rows in by_hash.items() if len(rows) > 1}
    duplicate_files_marked = 0
    duplicate_group_report = []

    for file_hash, group_rows in duplicate_groups.items():
        kept = group_rows[0]
        skipped = group_rows[1:]
        for row in skipped:
            cursor.execute("UPDATE located_files SET status = 'duplicate' WHERE id = ?", (row['id'],))
            duplicate_files_marked += 1
        conn.commit()
        duplicate_group_report.append({
            'file_hash': file_hash,
            'kept': kept['file_path'],
            'marked_duplicate': [r['file_path'] for r in skipped],
        })

    conn.close()

    print(f"Found {len(duplicate_groups)} duplicate group(s), marked {duplicate_files_marked} file(s) as 'duplicate'.")
    print("-" * 60)
    print(f"Processed: {processed}")
    print(f"Failed/missing: {failed}")
    print(f"Duplicate groups: {len(duplicate_groups)}")
    print(f"Files marked as duplicate (skipped from import): {duplicate_files_marked}")

    report = {
        'condition_timestamp': datetime.now().isoformat(),
        'database_path': database_path,
        'summary': {
            'processed': processed,
            'failed': failed,
            'duplicate_groups': len(duplicate_groups),
            'duplicate_files_marked': duplicate_files_marked,
        },
        'duplicate_groups': duplicate_group_report,
    }
    with open(config['output_report_path'], 'w') as f:
        json.dump(report, f, indent=4)
    print(f"\nReport written to: {config['output_report_path']}")


if __name__ == "__main__":
    main()
    