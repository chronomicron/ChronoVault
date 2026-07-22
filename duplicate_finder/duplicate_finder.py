import json
import sys
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime


def load_config(config_file):
    """Load the duplicate_finder configuration from JSON."""
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        database_path = config.get('database_path')
        statuses_to_check = config.get('statuses_to_check', ['located'])
        output_path = config.get('output_path', 'duplicate_report.json')

        if not database_path:
            print("Error: 'database_path' must be specified in config.")
            sys.exit(1)

        return database_path, statuses_to_check, output_path
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_file}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Configuration file '{config_file}' is not valid JSON.")
        sys.exit(1)


def ensure_hash_column(conn):
    """Add a file_hash column to located_files if it doesn't already exist."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(located_files)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'file_hash' not in columns:
        cursor.execute("ALTER TABLE located_files ADD COLUMN file_hash TEXT")
        conn.commit()


def format_size(num_bytes):
    """Convert a byte count into a human readable string."""
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}PB"


def compute_file_hash(file_path, file_size):
    """
    Compute a SHA-256 hash of a file's contents, reading in chunks so large
    video files don't need to be loaded into memory all at once. Prints a
    live progress readout for large files, same approach as Importer's copy.
    """
    chunk_size = 4 * 1024 * 1024  # 4 MB chunks
    hasher = hashlib.sha256()
    read_bytes = 0

    show_progress = file_size >= 20 * 1024 * 1024  # only bother for 20MB+

    try:
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
                read_bytes += len(chunk)
                if show_progress:
                    percent = (read_bytes / file_size) * 100
                    print(f"\r    hashing: {format_size(read_bytes)} / {format_size(file_size)} ({percent:.1f}%)",
                          end='', flush=True)
        if show_progress:
            print()
        return hasher.hexdigest()
    except Exception as e:
        print(f"\n    Error hashing {file_path}: {e}")
        return None


def get_rows_to_check(conn, statuses_to_check):
    """Retrieve all rows matching the configured statuses."""
    cursor = conn.cursor()
    placeholders = ','.join('?' * len(statuses_to_check))
    cursor.execute(f'''
        SELECT id, file_path, file_size, file_hash FROM located_files
        WHERE status IN ({placeholders})
    ''', statuses_to_check)
    return cursor.fetchall()


def update_hash(conn, file_id, file_hash):
    """Cache a computed hash back into the database so future runs don't re-hash the same file."""
    cursor = conn.cursor()
    cursor.execute("UPDATE located_files SET file_hash = ? WHERE id = ?", (file_hash, file_id))
    conn.commit()


def main():
    if len(sys.argv) != 2:
        print("Usage: python duplicate_finder.py <config.json>")
        print("Example: python duplicate_finder.py duplicate_finder/config.json")
        sys.exit(1)

    config_file = sys.argv[1]

    print(f"Loading configuration from: {config_file}")
    database_path, statuses_to_check, output_path = load_config(config_file)

    print(f"Database: {database_path}")
    print(f"Checking statuses: {statuses_to_check}")
    print(f"Output report: {output_path}")
    print("-" * 60)

    conn = sqlite3.connect(database_path)
    ensure_hash_column(conn)

    rows = get_rows_to_check(conn, statuses_to_check)
    print(f"Found {len(rows)} file(s) to check.")
    print("-" * 60)

    missing = 0
    hashed_now = 0
    already_hashed = 0

    for idx, (file_id, file_path, file_size, existing_hash) in enumerate(rows, 1):
        progress_label = f"[{idx}/{len(rows)}]"
        source = Path(file_path)

        if not source.exists():
            print(f"{progress_label} MISSING: {file_path}")
            missing += 1
            continue

        if existing_hash:
            already_hashed += 1
            continue

        print(f"{progress_label} Hashing: {file_path} ({format_size(file_size)})")
        file_hash = compute_file_hash(source, file_size)
        if file_hash:
            update_hash(conn, file_id, file_hash)
            hashed_now += 1

    print("-" * 60)
    print(f"Newly hashed: {hashed_now}")
    print(f"Already hashed (cached): {already_hashed}")
    print(f"Missing from disk: {missing}")
    print("-" * 60)

    # Re-read everything now that hashes are populated, and group by hash.
    rows = get_rows_to_check(conn, statuses_to_check)
    conn.close()

    groups_by_hash = {}
    for file_id, file_path, file_size, file_hash in rows:
        if not file_hash:
            continue  # missing files that never got hashed
        groups_by_hash.setdefault(file_hash, []).append({
            'file_id': file_id,
            'file_path': file_path,
            'file_size': file_size,
        })

    duplicate_groups = [
        {'file_hash': file_hash, 'file_size': entries[0]['file_size'], 'count': len(entries),
         'files': entries}
        for file_hash, entries in groups_by_hash.items() if len(entries) > 1
    ]
    duplicate_groups.sort(key=lambda g: g['file_size'] * (g['count'] - 1), reverse=True)

    if duplicate_groups:
        print(f"Duplicate groups found: {len(duplicate_groups)}")
        print()
        for group in duplicate_groups:
            wasted = group['file_size'] * (group['count'] - 1)
            print(f"  {group['count']} copies, {format_size(group['file_size'])} each "
                  f"(wasting {format_size(wasted)}):")
            for entry in group['files']:
                print(f"    {entry['file_path']}")
            print()
    else:
        print("No duplicates found among the checked files.")

    total_duplicate_files = sum(g['count'] for g in duplicate_groups)
    total_wasted_bytes = sum(g['file_size'] * (g['count'] - 1) for g in duplicate_groups)

    print("-" * 60)
    print("Summary:")
    print(f"  Files checked: {len(rows)}")
    print(f"  Duplicate groups: {len(duplicate_groups)}")
    print(f"  Files involved in duplicates: {total_duplicate_files}")
    print(f"  Space that could be reclaimed: {format_size(total_wasted_bytes)}")

    report = {
        'scan_timestamp': datetime.now().isoformat(),
        'database_path': database_path,
        'statuses_checked': statuses_to_check,
        'summary': {
            'files_checked': len(rows),
            'duplicate_groups': len(duplicate_groups),
            'duplicate_files': total_duplicate_files,
            'wasted_bytes': total_wasted_bytes,
        },
        'duplicate_groups': duplicate_groups,
    }

    with open(output_path, 'w') as f:
        json.dump(report, f, indent=4)

    print(f"\nReport written to: {output_path}")


if __name__ == "__main__":
    main()
    