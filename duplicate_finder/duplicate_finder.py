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
        mode = config.get('mode', 'source')
        output_path = config.get('output_path', 'duplicate_report.json')

        if mode == 'source':
            database_path = config.get('database_path')
            statuses_to_check = config.get('statuses_to_check', ['located'])
            if not database_path:
                print("Error: 'database_path' must be specified in config for source mode.")
                sys.exit(1)
            return mode, {'database_path': database_path, 'statuses_to_check': statuses_to_check}, output_path

        elif mode == 'archive':
            archive_root = config.get('archive_root')
            if not archive_root:
                print("Error: 'archive_root' must be specified in config for archive mode.")
                sys.exit(1)
            return mode, {'archive_root': archive_root}, output_path

        else:
            print(f"Error: unknown mode '{mode}'. Use 'source' or 'archive'.")
            sys.exit(1)

    except FileNotFoundError:
        print(f"Error: Configuration file '{config_file}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Configuration file '{config_file}' is not valid JSON.")
        sys.exit(1)


def ensure_hash_column_source(conn):
    """Add a file_hash column to located_files if it doesn't already exist."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(located_files)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'file_hash' not in columns:
        cursor.execute("ALTER TABLE located_files ADD COLUMN file_hash TEXT")
        conn.commit()


def ensure_hash_column_archive(conn):
    """Add a file_hash column to archive_files if it doesn't already exist."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(archive_files)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'file_hash' not in columns:
        cursor.execute("ALTER TABLE archive_files ADD COLUMN file_hash TEXT")
        conn.commit()


def get_files_on_disk(archive_root):
    """Recursively walk the archive folder and return the set of file paths found."""
    archive_dir = Path(archive_root)
    if not archive_dir.exists():
        print(f"Error: Archive root '{archive_root}' does not exist.")
        sys.exit(1)

    files_on_disk = set()
    for file_path in archive_dir.rglob('*'):
        if file_path.is_file() and file_path.name != "archive_database.db":
            files_on_disk.add(str(file_path))
    return files_on_disk


def get_archive_records(archive_root):
    """Return {archive_path: {file_size, file_hash}} from archive_database.db."""
    archive_db_path = Path(archive_root) / "archive_database.db"
    if not archive_db_path.exists():
        print(f"Error: Archive database '{archive_db_path}' does not exist.")
        sys.exit(1)

    conn = sqlite3.connect(archive_db_path)
    ensure_hash_column_archive(conn)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT archive_path, file_size, file_hash FROM archive_files")
    rows = cursor.fetchall()

    return conn, {row['archive_path']: {'file_size': row['file_size'], 'file_hash': row['file_hash']} for row in rows}


def update_archive_hash(conn, archive_path, file_hash):
    cursor = conn.cursor()
    cursor.execute("UPDATE archive_files SET file_hash = ? WHERE archive_path = ?", (file_hash, archive_path))
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


def run_source_mode(options, output_path):
    """Original behaviour: hash located_files.db entries (pre-import source inventory)."""
    database_path = options['database_path']
    statuses_to_check = options['statuses_to_check']

    print(f"Mode: source")
    print(f"Database: {database_path}")
    print(f"Checking statuses: {statuses_to_check}")
    print(f"Output report: {output_path}")
    print("-" * 60)

    conn = sqlite3.connect(database_path)
    ensure_hash_column_source(conn)

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

    rows = get_rows_to_check(conn, statuses_to_check)
    conn.close()

    entries = [
        {'label': file_path, 'file_size': file_size, 'file_hash': file_hash, 'documented': True}
        for _id, file_path, file_size, file_hash in rows if file_hash
    ]

    extra_summary = {}
    return entries, extra_summary


def run_archive_mode(options, output_path):
    """
    New behaviour: hash everything actually sitting in the archive folder.
    Files already in archive_database.db use their cached hash (populated by
    Audit, or by this tool itself). Files not yet in the database (undocumented
    -- e.g. manually copied in) are hashed fresh every run, since there's no
    database row to cache the result into.
    """
    archive_root = options['archive_root']

    print(f"Mode: archive")
    print(f"Archive root: {archive_root}")
    print(f"Output report: {output_path}")
    print("-" * 60)

    print("Scanning archive folder on disk...")
    files_on_disk = get_files_on_disk(archive_root)
    print(f"Found {len(files_on_disk)} file(s) on disk.")

    print("Reading archive_database.db...")
    conn, archive_records = get_archive_records(archive_root)
    print(f"Found {len(archive_records)} record(s) in database.")
    print("-" * 60)

    entries = []
    hashed_now = 0
    already_hashed = 0
    hashed_undocumented = 0

    for idx, path in enumerate(sorted(files_on_disk), 1):
        progress_label = f"[{idx}/{len(files_on_disk)}]"
        record = archive_records.get(path)

        if record:
            # Documented file -- use cached hash, or compute and cache it now.
            if record['file_hash']:
                already_hashed += 1
                entries.append({'label': path, 'file_size': record['file_size'],
                                 'file_hash': record['file_hash'], 'documented': True})
                continue

            file_size = record['file_size'] or Path(path).stat().st_size
            print(f"{progress_label} Hashing (documented, uncached): {path} ({format_size(file_size)})")
            file_hash = compute_file_hash(path, file_size)
            if file_hash:
                update_archive_hash(conn, path, file_hash)
                hashed_now += 1
                entries.append({'label': path, 'file_size': file_size,
                                 'file_hash': file_hash, 'documented': True})
        else:
            # Undocumented file -- no database row to cache into, hash fresh every run.
            file_size = Path(path).stat().st_size
            print(f"{progress_label} Hashing (undocumented): {path} ({format_size(file_size)})")
            file_hash = compute_file_hash(path, file_size)
            if file_hash:
                hashed_undocumented += 1
                entries.append({'label': path, 'file_size': file_size,
                                 'file_hash': file_hash, 'documented': False})

    conn.close()

    print("-" * 60)
    print(f"Already cached (documented): {already_hashed}")
    print(f"Newly hashed (documented): {hashed_now}")
    print(f"Hashed (undocumented, not cached): {hashed_undocumented}")
    print("-" * 60)

    extra_summary = {
        'documented_cached': already_hashed,
        'documented_newly_hashed': hashed_now,
        'undocumented_hashed': hashed_undocumented,
    }
    return entries, extra_summary


def main():
    if len(sys.argv) != 2:
        print("Usage: python duplicate_finder.py <config.json>")
        print("Example: python duplicate_finder.py duplicate_finder/config.json")
        sys.exit(1)

    config_file = sys.argv[1]

    print(f"Loading configuration from: {config_file}")
    mode, options, output_path = load_config(config_file)

    if mode == 'source':
        entries, extra_summary = run_source_mode(options, output_path)
    else:
        entries, extra_summary = run_archive_mode(options, output_path)

    # Group by hash, same for both modes
    groups_by_hash = {}
    for entry in entries:
        groups_by_hash.setdefault(entry['file_hash'], []).append(entry)

    duplicate_groups = [
        {'file_hash': file_hash, 'file_size': group_entries[0]['file_size'], 'count': len(group_entries),
         'files': [{'path': e['label'], 'documented': e['documented']} for e in group_entries]}
        for file_hash, group_entries in groups_by_hash.items() if len(group_entries) > 1
    ]
    duplicate_groups.sort(key=lambda g: g['file_size'] * (g['count'] - 1), reverse=True)

    if duplicate_groups:
        print(f"Duplicate groups found: {len(duplicate_groups)}")
        print()
        for group in duplicate_groups:
            wasted = group['file_size'] * (group['count'] - 1)
            print(f"  {group['count']} copies, {format_size(group['file_size'])} each "
                  f"(wasting {format_size(wasted)}):")
            for f in group['files']:
                tag = "" if f['documented'] else "  [undocumented]"
                print(f"    {f['path']}{tag}")
            print()
    else:
        print("No duplicates found among the checked files.")

    total_duplicate_files = sum(g['count'] for g in duplicate_groups)
    total_wasted_bytes = sum(g['file_size'] * (g['count'] - 1) for g in duplicate_groups)

    print("-" * 60)
    print("Summary:")
    print(f"  Files checked: {len(entries)}")
    print(f"  Duplicate groups: {len(duplicate_groups)}")
    print(f"  Files involved in duplicates: {total_duplicate_files}")
    print(f"  Space that could be reclaimed: {format_size(total_wasted_bytes)}")

    report = {
        'scan_timestamp': datetime.now().isoformat(),
        'mode': mode,
        'summary': {
            'files_checked': len(entries),
            'duplicate_groups': len(duplicate_groups),
            'duplicate_files': total_duplicate_files,
            'wasted_bytes': total_wasted_bytes,
            **extra_summary,
        },
        'duplicate_groups': duplicate_groups,
    }

    with open(output_path, 'w') as f:
        json.dump(report, f, indent=4)

    print(f"\nReport written to: {output_path}")


if __name__ == "__main__":
    main()
    