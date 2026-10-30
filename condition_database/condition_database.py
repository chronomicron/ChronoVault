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
import signal
from pathlib import Path
from datetime import datetime

# Make the project root importable regardless of the current working
# directory, matching the convention used by importer.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analyze_date.analyze_date import analyze_date
from source_inventory_hash import (
    HashCancelled, ensure_source_hash_columns, file_fingerprint,
    hash_source_file, is_fresh,
)


PROGRESS_PREFIX = "CHRONOVAULT_PROGRESS "
EXIT_STOPPED = 2
STOP_REQUESTED = False
IMAGE_EXTENSIONS = frozenset({
    "jpg", "jpeg", "bmp", "tif", "tiff", "png", "gif", "webp", "thm", "raw", "cr2", "arw",
})
VIDEO_EXTENSIONS = frozenset({
    "mp4", "mov", "avi", "mkv", "mpeg", "mpg", "3gp", "mts", "m2ts",
})


class StopRequested(Exception):
    """Raised at a safe checkpoint after SIGINT or SIGTERM."""


def _request_stop(_signum, _frame):
    global STOP_REQUESTED
    STOP_REQUESTED = True


def check_stop_requested():
    if STOP_REQUESTED:
        raise StopRequested()


def emit_progress(stage, completed, total, **details):
    event = {
        "version": 1,
        "event": "progress",
        "tool": "condition_database",
        "stage": stage,
        "completed": completed,
        "total": total,
    }
    event.update(details)
    print(PROGRESS_PREFIX + json.dumps(event, separators=(",", ":")), flush=True)


def emit_status(status, exit_code):
    event = {
        "version": 1,
        "event": "status",
        "tool": "condition_database",
        "status": status,
        "exit_code": exit_code,
    }
    print(PROGRESS_PREFIX + json.dumps(event, separators=(",", ":")), flush=True)


def processing_priority(row):
    """Order images, videos, then other types; use id for stable resumption."""
    extension = (row["file_extension"] or "").lower().lstrip(".")
    if extension in IMAGE_EXTENSIONS:
        category = 0
    elif extension in VIDEO_EXTENSIONS:
        category = 1
    else:
        category = 2
    return category, row["id"]


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


def refresh_source_hashes(conn):
    """Refresh unknown/stale hashes without changing existing statuses."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, file_path, file_extension, file_hash, hash_file_size, hash_mtime_ns, status
        FROM located_files WHERE status IN ('located', 'duplicate')
    """)
    rows = sorted(cursor.fetchall(), key=processing_priority)
    refreshed = 0
    failed = 0
    total = len(rows)
    emit_progress("hash_refresh", 0, total)
    for completed, row in enumerate(rows, 1):
        check_stop_requested()
        file_id = row['id']
        file_path = row['file_path']
        cached_hash = row['file_hash']
        cached_size = row['hash_file_size']
        cached_mtime_ns = row['hash_mtime_ns']
        try:
            current_size, current_mtime_ns = file_fingerprint(file_path)
        except OSError:
            cursor.execute("""
                UPDATE located_files SET file_hash = NULL, hash_file_size = NULL,
                    hash_mtime_ns = NULL, hash_computed_at = NULL WHERE id = ?
            """, (file_id,))
            failed += 1
            conn.commit()
            emit_progress("hash_refresh", completed, total, file_path=file_path, result="unavailable")
            continue

        if is_fresh(cached_hash, cached_size, cached_mtime_ns, current_size, current_mtime_ns):
            emit_progress("hash_refresh", completed, total, file_path=file_path, result="cached")
            continue

        print(f"    Hashing source: {file_path} ({current_size} bytes)")
        try:
            snapshot = hash_source_file(
                file_path,
                should_stop=lambda: STOP_REQUESTED,
                on_progress=lambda byte_count, byte_total: emit_progress(
                    "hash_refresh", completed - 1, total,
                    file_path=file_path,
                    file_bytes_completed=byte_count,
                    file_bytes_total=byte_total,
                ),
            )
        except HashCancelled as exc:
            raise StopRequested() from exc
        check_stop_requested()
        if snapshot is None:
            cursor.execute("""
                UPDATE located_files SET file_hash = NULL, hash_file_size = NULL,
                    hash_mtime_ns = NULL, hash_computed_at = NULL WHERE id = ?
            """, (file_id,))
            print(f"    UNSTABLE/FAILED hash: {file_path}; hash cache cleared")
            failed += 1
        else:
            file_hash, file_size, mtime_ns, computed_at = snapshot
            cursor.execute("""
                UPDATE located_files
                SET file_hash = ?, hash_file_size = ?, hash_mtime_ns = ?, hash_computed_at = ?
                WHERE id = ?
            """, (file_hash, file_size, mtime_ns, computed_at, file_id))
            refreshed += 1
        conn.commit()
        emit_progress("hash_refresh", completed, total, file_path=file_path,
                      result="hashed" if snapshot else "failed")
    return refreshed, failed


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


def regroup_duplicates(conn):
    """Recalculate duplicate statuses atomically so interruption rolls back."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, file_path, file_hash, status FROM located_files
        WHERE status IN ('located', 'duplicate')
    """)
    rows = cursor.fetchall()
    total = len(rows)
    emit_progress("duplicate_regrouping", 0, total)
    by_hash = {}
    for completed, row in enumerate(rows, 1):
        check_stop_requested()
        file_hash = row['file_hash']
        if file_hash:
            by_hash.setdefault(file_hash, []).append(row)
        emit_progress("duplicate_regrouping", completed, total)

    groups = {file_hash: group for file_hash, group in by_hash.items() if len(group) > 1}
    duplicate_ids = {
        row['id']
        for group in groups.values()
        for row in group[1:]
    }

    check_stop_requested()
    conn.execute("BEGIN IMMEDIATE")
    try:
        for completed, row in enumerate(rows, 1):
            check_stop_requested()
            new_status = 'duplicate' if row['id'] in duplicate_ids else 'located'
            if row['status'] != new_status:
                cursor.execute("UPDATE located_files SET status = ? WHERE id = ?", (new_status, row['id']))
        check_stop_requested()
        conn.commit()
    except StopRequested:
        conn.rollback()
        raise

    emit_progress("duplicate_regrouping", total, total)
    reports = []
    for file_hash, group in groups.items():
        reports.append({
            'file_hash': file_hash,
            'kept': group[0]['file_path'],
            'marked_duplicate': [row['file_path'] for row in group[1:]],
        })
    return reports, len(duplicate_ids)


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 condition_database.py <config.json>")
        print("Example: python3 condition_database.py condition_database/config.json")
        sys.exit(1)

    global STOP_REQUESTED
    STOP_REQUESTED = False
    old_sigint = signal.signal(signal.SIGINT, _request_stop)
    old_sigterm = signal.signal(signal.SIGTERM, _request_stop)
    conn = None
    try:
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
        ensure_source_hash_columns(conn)
        check_stop_requested()

        refreshed_hashes, hash_failures = refresh_source_hashes(conn)
        print(f"Source hash snapshots refreshed: {refreshed_hashes}; unavailable/unstable: {hash_failures}")

        cursor.execute("SELECT * FROM located_files WHERE status = 'located' AND confidence IS NULL")
        rows = sorted(cursor.fetchall(), key=processing_priority)
        print(f"Found {len(rows)} file(s) to condition.")
        print("-" * 60)

        processed = 0
        failed = 0
        emit_progress("date_conditioning", 0, len(rows))
        for idx, row in enumerate(rows, 1):
            check_stop_requested()
            file_path = row['file_path']
            file_id = row['id']
            path_obj = Path(file_path)
            if not path_obj.exists():
                print(f"[{idx}/{len(rows)}] MISSING: {file_path}")
                failed += 1
                emit_progress("date_conditioning", idx, len(rows), file_path=file_path, result="missing")
                continue

            print(f"[{idx}/{len(rows)}] {file_path}")
            try:
                readable_exif = get_readable_exif(file_path, row['file_extension'])
                result = analyze_date({
                    'file_path': file_path,
                    'readable_exif': readable_exif,
                    'mismatch_threshold_days': config['mismatch_threshold_days'],
                    'try_ocr': config['try_ocr'],
                })
                check_stop_requested()
                cursor.execute('''
                    UPDATE located_files
                    SET confidence = ?, date_reason = ?, date_source = ?, date_taken = ?
                    WHERE id = ?
                ''', (
                    result['confidence'], result['reason'], result['date_source'],
                    result['date_taken'].isoformat() if result['date_taken'] else None,
                    file_id
                ))
                conn.commit()
                print(f"    confidence={result['confidence']}  source={result['date_source']}  {result['reason']}")
                processed += 1
                emit_progress("date_conditioning", idx, len(rows), file_path=file_path, result="conditioned")
            except StopRequested:
                raise
            except Exception as exc:
                print(f"    FAILED: {exc}")
                failed += 1
                emit_progress("date_conditioning", idx, len(rows), file_path=file_path, result="failed")

        check_stop_requested()
        print("-" * 60)
        print("Conditioning complete. Checking for duplicates...")
        duplicate_group_report, duplicate_files_marked = regroup_duplicates(conn)
        duplicate_group_count = len(duplicate_group_report)

        print(f"Found {duplicate_group_count} duplicate group(s), marked {duplicate_files_marked} file(s) as 'duplicate'.")
        print("-" * 60)
        print(f"Processed: {processed}")
        print(f"Failed/missing: {failed}")
        print(f"Duplicate groups: {duplicate_group_count}")
        print(f"Files marked as duplicate (skipped from import): {duplicate_files_marked}")

        check_stop_requested()
        report = {
            'condition_timestamp': datetime.now().isoformat(),
            'database_path': database_path,
            'summary': {
                'processed': processed,
                'failed': failed + hash_failures,
                'duplicate_groups': duplicate_group_count,
                'duplicate_files_marked': duplicate_files_marked,
            },
            'duplicate_groups': duplicate_group_report,
        }
        with open(config['output_report_path'], 'w') as report_file:
            json.dump(report, report_file, indent=4)
        check_stop_requested()
        print(f"\nReport written to: {config['output_report_path']}")
        emit_status("completed", 0)
        return 0
    except StopRequested:
        if conn is not None:
            conn.rollback()
        print("Condition Database stopped safely. Completed hash/date work is saved; duplicate statuses were not partially changed.")
        emit_status("stopped", EXIT_STOPPED)
        return EXIT_STOPPED
    except Exception:
        if conn is not None:
            conn.rollback()
        emit_status("failed", 1)
        raise
    finally:
        if conn is not None:
            conn.close()
        signal.signal(signal.SIGINT, old_sigint)
        signal.signal(signal.SIGTERM, old_sigterm)


if __name__ == "__main__":
    sys.exit(main())

