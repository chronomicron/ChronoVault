import json
import sys
import sqlite3
from pathlib import Path
from datetime import datetime


def load_config(config_file):
    """Load the audit_archive configuration from JSON."""
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        archive_root = config.get('archive_root')
        extensions = config.get('extensions', [])  # empty list = scan all files
        output_path = config.get('output_path', 'audit_result.json')

        if not archive_root:
            print("Error: 'archive_root' must be specified in config.")
            sys.exit(1)

        return archive_root, extensions, output_path
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_file}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Configuration file '{config_file}' is not valid JSON.")
        sys.exit(1)


def get_files_on_disk(archive_root, extensions):
    """Recursively walk the archive folder and return the set of file paths found."""
    archive_dir = Path(archive_root)

    if not archive_dir.exists():
        print(f"Error: Archive root '{archive_root}' does not exist.")
        sys.exit(1)

    normalized_extensions = None
    if extensions:
        normalized_extensions = {
            ext.lower() if ext.startswith('.') else '.' + ext.lower()
            for ext in extensions
        }

    files_on_disk = set()
    for file_path in archive_dir.rglob('*'):
        if not file_path.is_file():
            continue
        if file_path.name == "archive_database.db":
            continue  # the database itself lives inside archive_root, skip it

        if normalized_extensions is not None:
            if file_path.suffix.lower() not in normalized_extensions:
                continue

        files_on_disk.add(str(file_path))

    return files_on_disk


def get_files_in_database(archive_root):
    """
    Return two things from archive_database.db:
    - a set of archive_path values (for fast set comparison)
    - a dict of {archive_path: full row as a dict} (for detailed reporting)
    """
    archive_db_path = Path(archive_root) / "archive_database.db"

    if not archive_db_path.exists():
        print(f"Error: Archive database '{archive_db_path}' does not exist.")
        sys.exit(1)

    conn = sqlite3.connect(archive_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM archive_files")
    rows = cursor.fetchall()
    conn.close()

    records_by_path = {row["archive_path"]: dict(row) for row in rows}
    paths = set(records_by_path.keys())

    return paths, records_by_path


def main():
    if len(sys.argv) != 2:
        print("Usage: python audit_archive.py <config.json>")
        print("Example: python audit_archive.py audit_archive/config.json")
        sys.exit(1)

    config_file = sys.argv[1]

    print(f"Loading configuration from: {config_file}")
    archive_root, extensions, output_path = load_config(config_file)

    print(f"Archive root: {archive_root}")
    print(f"Extensions filter: {extensions if extensions else '(all files)'}")
    print(f"Output report: {output_path}")
    print("-" * 60)

    print("Scanning archive folder on disk...")
    files_on_disk = get_files_on_disk(archive_root, extensions)
    print(f"Found {len(files_on_disk)} file(s) on disk.")

    print("Reading archive_database.db...")
    files_in_database, records_by_path = get_files_in_database(archive_root)
    print(f"Found {len(files_in_database)} record(s) in database.")
    print("-" * 60)

    # On disk, but no matching database record
    not_in_database = sorted(files_on_disk - files_in_database)

    # In database, but the file no longer exists on disk
    missing_from_disk = sorted(files_in_database - files_on_disk)

    if not_in_database:
        print(f"Files on disk but NOT in database ({len(not_in_database)}):")
        for path in not_in_database:
            print(f"  {path}")
        print()
    else:
        print("No undocumented files found on disk. Good.")
        print()

    if missing_from_disk:
        print(f"Files in database but MISSING from disk ({len(missing_from_disk)}):")
        for path in missing_from_disk:
            print(f"  {path}")
        print()
    else:
        print("No missing files. Every database record has a matching file on disk. Good.")
        print()

    print("-" * 60)
    print("Summary:")
    print(f"  On disk: {len(files_on_disk)}")
    print(f"  In database: {len(files_in_database)}")
    print(f"  On disk but undocumented: {len(not_in_database)}")
    print(f"  In database but missing from disk: {len(missing_from_disk)}")

    if not not_in_database and not missing_from_disk:
        print("\nArchive and database are fully in sync.")
    else:
        print("\nDiscrepancies found. No changes have been made -- this is a report only.")

    # Build the JSON report. Undocumented files get basic filesystem metadata,
    # since there's no database record for them yet. Missing files get their
    # full original database record, since that context is useful for deciding
    # what to do about them later (e.g. was it a big video? when was it taken?).
    undocumented_entries = []
    for path in not_in_database:
        file_path = Path(path)
        try:
            stat = file_path.stat()
            undocumented_entries.append({
                'path': path,
                'file_size': stat.st_size,
                'modified_date': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        except OSError:
            undocumented_entries.append({'path': path, 'file_size': None, 'modified_date': None})

    missing_entries = []
    for path in missing_from_disk:
        record = records_by_path.get(path, {})
        missing_entries.append(record)

    report = {
        'audit_timestamp': datetime.now().isoformat(),
        'archive_root': archive_root,
        'summary': {
            'on_disk': len(files_on_disk),
            'in_database': len(files_in_database),
            'undocumented_count': len(not_in_database),
            'missing_count': len(missing_from_disk),
            'in_sync': not not_in_database and not missing_from_disk,
        },
        'undocumented_files': undocumented_entries,
        'missing_files': missing_entries,
    }

    with open(output_path, 'w') as f:
        json.dump(report, f, indent=4)

    print(f"\nReport written to: {output_path}")


if __name__ == "__main__":
    main()
    