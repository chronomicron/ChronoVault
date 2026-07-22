import json
import sys
import sqlite3
from pathlib import Path
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS


def get_readable_exif(file_path):
    """Return a {tag_name: value} dict of EXIF data for a file, or {} if unavailable."""
    try:
        image = Image.open(file_path)
        exif_data = image._getexif()
        if not exif_data:
            return {}
        return {TAGS.get(tag_id, tag_id): value for tag_id, value in exif_data.items()}
    except Exception:
        return {}


def get_date_from_exif(readable_exif):
    """Pull DateTimeOriginal or DateTimeDigitized from a readable EXIF dict, if present."""
    for tag_name in ('DateTimeOriginal', 'DateTimeDigitized'):
        value = readable_exif.get(tag_name)
        if value:
            try:
                return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
            except ValueError:
                continue
    return None


def get_filesystem_creation_date(file_path):
    """File system creation date, used as a fallback when EXIF has no date."""
    try:
        stat = Path(file_path).stat()
        return datetime.fromtimestamp(stat.st_ctime)
    except Exception:
        return None


def get_expected_date(file_path, readable_exif):
    """
    Determine the date to use for checking a file's placement, same priority
    Importer uses: EXIF first, file system creation date as a last resort.
    Returns (date, source) where source is 'exif' or 'filesystem_fallback'.
    """
    exif_date = get_date_from_exif(readable_exif)
    if exif_date:
        return exif_date, 'exif'

    fs_date = get_filesystem_creation_date(file_path)
    if fs_date:
        return fs_date, 'filesystem_fallback'

    return None, None


def get_expected_folder(date_value):
    """Given a datetime, return the (year, month, day) folder components ChronoVault would use."""
    if not date_value:
        return None
    return date_value.strftime("%Y"), date_value.strftime("%m"), date_value.strftime("%d")


def get_actual_folder(file_path, archive_root):
    """
    Return the (year, month, day) folder components a file is actually sitting in,
    based on its path relative to archive_root. Returns None if the file isn't
    sitting three levels deep under archive_root (i.e. doesn't follow the expected
    YYYY/MM/DD structure at all).
    """
    try:
        relative = Path(file_path).relative_to(Path(archive_root))
        parts = relative.parts
        if len(parts) >= 4:  # year/month/day/filename at minimum
            return parts[0], parts[1], parts[2]
        return None
    except ValueError:
        return None


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

    # Present in both -- these are the ones we can check for correct placement
    matched_files = sorted(files_on_disk & files_in_database)

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

    # --- Check placement of matched files (on disk + in database) ---
    print("Checking file placement against expected date-based folders...")
    misplaced_files = []
    for path in matched_files:
        record = records_by_path.get(path, {})
        date_taken_str = record.get('date_taken')

        expected_folder = None
        if date_taken_str:
            try:
                date_taken = datetime.fromisoformat(date_taken_str)
                expected_folder = get_expected_folder(date_taken)
            except ValueError:
                expected_folder = None

        actual_folder = get_actual_folder(path, archive_root)

        if expected_folder and actual_folder and expected_folder != actual_folder:
            expected_relative = "/".join(expected_folder) + "/" + Path(path).name
            misplaced_files.append({
                'archive_path': path,
                'expected_relative_path': expected_relative,
                'actual_folder': "/".join(actual_folder),
                'expected_folder': "/".join(expected_folder),
                'date_taken': date_taken_str,
            })

    # --- Check placement of undocumented files (on disk, not yet in database) ---
    # These have no stored date_taken, so we read EXIF fresh, same as Importer would.
    undocumented_entries = []
    for path in not_in_database:
        file_path = Path(path)
        try:
            stat = file_path.stat()
            file_size = stat.st_size
            modified_date = datetime.fromtimestamp(stat.st_mtime).isoformat()
        except OSError:
            file_size = None
            modified_date = None

        readable_exif = get_readable_exif(file_path)
        expected_date, date_source = get_expected_date(file_path, readable_exif)
        expected_folder = get_expected_folder(expected_date) if expected_date else None
        actual_folder = get_actual_folder(path, archive_root)

        entry = {
            'path': path,
            'file_size': file_size,
            'modified_date': modified_date,
            'date_source': date_source,
        }

        if expected_folder and actual_folder and expected_folder != actual_folder:
            entry['correctly_placed'] = False
            entry['expected_folder'] = "/".join(expected_folder)
            entry['actual_folder'] = "/".join(actual_folder)
        else:
            entry['correctly_placed'] = True

        undocumented_entries.append(entry)

    if misplaced_files:
        print(f"Files in the WRONG folder for their date ({len(misplaced_files)}):")
        for item in misplaced_files:
            print(f"  {item['archive_path']}")
            print(f"    currently in: {item['actual_folder']}   expected: {item['expected_folder']}")
        print()
    else:
        print("All matched files are sitting in the correct date-based folder. Good.")
        print()

    undocumented_misplaced = [e for e in undocumented_entries if not e['correctly_placed']]

    if undocumented_misplaced:
        print(f"Undocumented files ALSO in the wrong folder for their date ({len(undocumented_misplaced)}):")
        for item in undocumented_misplaced:
            print(f"  {item['path']}")
            print(f"    currently in: {item['actual_folder']}   expected: {item['expected_folder']}"
                  f"   (date source: {item['date_source']})")
        print()
    elif not_in_database:
        print("Undocumented files are otherwise sitting in the correct date-based folder.")
        print()

    print("-" * 60)
    print("Summary:")
    print(f"  On disk: {len(files_on_disk)}")
    print(f"  In database: {len(files_in_database)}")
    print(f"  On disk but undocumented: {len(not_in_database)}")
    print(f"  In database but missing from disk: {len(missing_from_disk)}")
    print(f"  Matched files in wrong folder for their date: {len(misplaced_files)}")
    print(f"  Undocumented files in wrong folder for their date: {len(undocumented_misplaced)}")

    fully_in_sync = (
        not not_in_database and not missing_from_disk
        and not misplaced_files and not undocumented_misplaced
    )

    if fully_in_sync:
        print("\nArchive and database are fully in sync and correctly organized.")
    else:
        print("\nDiscrepancies found. No changes have been made -- this is a report only.")

    missing_entries = [records_by_path.get(path, {}) for path in missing_from_disk]

    report = {
        'audit_timestamp': datetime.now().isoformat(),
        'archive_root': archive_root,
        'summary': {
            'on_disk': len(files_on_disk),
            'in_database': len(files_in_database),
            'undocumented_count': len(not_in_database),
            'missing_count': len(missing_from_disk),
            'misplaced_count': len(misplaced_files),
            'undocumented_misplaced_count': len(undocumented_misplaced),
            'in_sync': fully_in_sync,
        },
        'undocumented_files': undocumented_entries,
        'missing_files': missing_entries,
        'misplaced_files': misplaced_files,
    }

    with open(output_path, 'w') as f:
        json.dump(report, f, indent=4)

    print(f"\nReport written to: {output_path}")


if __name__ == "__main__":
    main()
    