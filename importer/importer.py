import json
import sys
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS


def load_config(config_file):
    """Load the importer configuration from JSON."""
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        database_path = config.get('database_path')
        archive_root = config.get('archive_root')
        extensions = config.get('extensions_to_copy', [])

        # Optional filters -- all have safe defaults so existing configs
        # keep working exactly as before if these keys are absent.
        min_file_size_bytes = config.get('min_file_size_bytes', 0)
        max_file_size_bytes = config.get('max_file_size_bytes', None)  # None = no upper limit
        require_exif = config.get('require_exif', False)
        exclude_path_contains = config.get('exclude_path_contains', [])

        # Thumbnail handling. Cameras (esp. Canon) create .THM sidecar thumbnail
        # files alongside videos/photos -- these can be useful to keep as a trace
        # of a deleted original, so they're excluded by default rather than
        # silently dropped at indexing time.
        exclude_thumbnails = config.get('exclude_thumbnails', True)
        thumbnail_extensions = config.get('thumbnail_extensions', ['thm'])

        if not database_path or not archive_root:
            print("Error: 'database_path' and 'archive_root' must be specified in config.")
            sys.exit(1)

        filters = {
            'min_file_size_bytes': min_file_size_bytes,
            'max_file_size_bytes': max_file_size_bytes,
            'require_exif': require_exif,
            'exclude_path_contains': exclude_path_contains,
            'exclude_thumbnails': exclude_thumbnails,
            'thumbnail_extensions': [
                ext.lower() if ext.startswith('.') else '.' + ext.lower()
                for ext in thumbnail_extensions
            ],
        }

        return database_path, archive_root, extensions, filters
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_file}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Configuration file '{config_file}' is not valid JSON.")
        sys.exit(1)


def init_archive_database(archive_root):
    """Initialize archive_database.db inside the archive folder, creating the table if needed."""
    archive_dir = Path(archive_root)
    archive_dir.mkdir(parents=True, exist_ok=True)

    archive_db_path = archive_dir / "archive_database.db"

    conn = sqlite3.connect(archive_db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS archive_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            archive_path TEXT UNIQUE NOT NULL,
            source_path TEXT,
            file_extension TEXT,
            file_size INTEGER,
            date_taken TEXT,
            date_added TEXT
        )
    ''')
    conn.commit()
    return conn, archive_db_path


def add_to_archive_database(conn, archive_path, source_path, file_extension, file_size, date_taken):
    """Insert a record for a newly copied file into archive_database."""
    cursor = conn.cursor()
    date_added = datetime.now().isoformat()
    date_taken_str = date_taken.isoformat() if date_taken else None

    cursor.execute('''
        INSERT OR IGNORE INTO archive_files
        (archive_path, source_path, file_extension, file_size, date_taken, date_added)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (str(archive_path), str(source_path), file_extension, file_size, date_taken_str, date_added))
    conn.commit()


def get_exif_data(file_path):
    """Return the raw EXIF dict for a file, or None if unavailable/not an image."""
    try:
        image = Image.open(file_path)
        return image._getexif()
    except Exception:
        return None


def get_photo_date_from_exif(exif_data):
    """Pull DateTimeOriginal or DateTimeDigitized out of an already-loaded EXIF dict."""
    if not exif_data:
        return None
    for tag_id, value in exif_data.items():
        tag_name = TAGS.get(tag_id, tag_id)
        if tag_name == "DateTimeOriginal" and value:
            return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
        if tag_name == "DateTimeDigitized" and value:
            return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
    return None


def get_photo_date(file_path, exif_data):
    """Determine date: EXIF first, then fall back to file system creation date."""
    exif_date = get_photo_date_from_exif(exif_data)
    if exif_date:
        return exif_date

    try:
        stat = Path(file_path).stat()
        return datetime.fromtimestamp(stat.st_ctime)
    except Exception:
        return None


def get_archive_path(file_path, archive_root, photo_date):
    """Determine the archive destination path based on photo date."""
    if not photo_date:
        print(f"Warning: Could not determine date for {file_path}, using current date")
        photo_date = datetime.now()

    year = photo_date.strftime("%Y")
    month = photo_date.strftime("%m")
    day = photo_date.strftime("%d")

    archive_dir = Path(archive_root) / year / month / day
    archive_dir.mkdir(parents=True, exist_ok=True)

    filename = Path(file_path).name
    return archive_dir / filename


def format_size(num_bytes):
    """Convert a byte count into a human readable string."""
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}PB"


def check_filters(file_path, file_size, exif_data, filters):
    """
    Check a file against the configured filters.
    Returns (passes, reason) -- reason is a short string explaining
    why the file was excluded, or None if it passes.
    """
    min_size = filters['min_file_size_bytes']
    max_size = filters['max_file_size_bytes']
    require_exif = filters['require_exif']
    exclude_terms = filters['exclude_path_contains']

    if min_size and file_size < min_size:
        return False, f"below min size ({format_size(file_size)} < {format_size(min_size)})"

    if max_size and file_size > max_size:
        return False, f"above max size ({format_size(file_size)} > {format_size(max_size)})"

    if exclude_terms:
        path_str = str(file_path)
        for term in exclude_terms:
            if term in path_str:
                return False, f"path contains excluded term '{term}'"

    if filters['exclude_thumbnails']:
        file_extension = Path(file_path).suffix.lower()
        if file_extension in filters['thumbnail_extensions']:
            return False, f"thumbnail file ({file_extension})"

    if require_exif and not exif_data:
        return False, "no EXIF data found"

    return True, None


def copy_file_with_progress(source, dest, file_size):
    """Copy a file in chunks, printing byte-level progress for large files."""
    chunk_size = 4 * 1024 * 1024  # 4 MB chunks
    copied_bytes = 0

    # For small files, just do a plain fast copy, no need for a progress readout
    if file_size < 20 * 1024 * 1024:  # under 20 MB
        try:
            shutil.copy2(source, dest)
            return True
        except Exception as e:
            print(f"\n    Error copying {source}: {e}")
            return False

    # For larger files, copy manually in chunks and print progress
    try:
        with open(source, 'rb') as src_file, open(dest, 'wb') as dst_file:
            while True:
                chunk = src_file.read(chunk_size)
                if not chunk:
                    break
                dst_file.write(chunk)
                copied_bytes += len(chunk)
                percent = (copied_bytes / file_size) * 100
                print(f"\r    {format_size(copied_bytes)} / {format_size(file_size)} ({percent:.1f}%)",
                      end='', flush=True)
        print()  # newline after progress finishes
        shutil.copystat(source, dest)  # preserve timestamps/permissions like copy2 does
        return True
    except Exception as e:
        print(f"\n    Error copying {source}: {e}")
        return False


def get_files_to_copy(db_path, extensions):
    """
    Retrieve files from database that match the extensions and are still eligible
    to be processed. 'located' and 'excluded' are both eligible, since filters
    (min/max size, require_exif, exclude_path_contains) can change between runs
    and a previously-excluded file may pass on a later run. Only 'imported' files
    are considered permanently done and are skipped.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    ext_list = tuple(
        '.' + ext.lower() if not ext.startswith('.') else ext.lower()
        for ext in extensions
    )

    placeholders = ','.join('?' * len(ext_list))
    query = f'''
        SELECT id, file_path FROM located_files
        WHERE status IN ('located', 'excluded') AND LOWER(file_extension) IN ({placeholders})
    '''
    cursor.execute(query, ext_list)
    files = cursor.fetchall()
    conn.close()

    return files


def update_file_status(db_path, file_id, status):
    """Update the status of a file in the located_files database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('UPDATE located_files SET status = ? WHERE id = ?', (status, file_id))
    conn.commit()
    conn.close()


def main():
    if len(sys.argv) != 2:
        print("Usage: python importer.py <config.json>")
        print("Example: python importer.py importer/config.json")
        sys.exit(1)

    config_file = sys.argv[1]

    print(f"Loading configuration from: {config_file}")
    database_path, archive_root, extensions, filters = load_config(config_file)

    if not extensions:
        print("Error: No extensions specified in configuration file.")
        sys.exit(1)

    print(f"Located-files database: {database_path}")
    print(f"Archive root: {archive_root}")
    print(f"Extensions to copy: {extensions}")
    print(f"Filters: min_size={filters['min_file_size_bytes']} bytes, "
          f"max_size={filters['max_file_size_bytes']}, "
          f"require_exif={filters['require_exif']}, "
          f"exclude_path_contains={filters['exclude_path_contains']}, "
          f"exclude_thumbnails={filters['exclude_thumbnails']} "
          f"({filters['thumbnail_extensions']})")

    archive_conn, archive_db_path = init_archive_database(archive_root)
    print(f"Archive database: {archive_db_path}")
    print("-" * 60)

    files = get_files_to_copy(database_path, extensions)

    if not files:
        print("No files to copy. (Nothing with status 'located' matches your extensions.)")
        archive_conn.close()
        return

    print(f"Found {len(files)} file(s) to evaluate.")
    print("-" * 60)

    copied = 0
    failed = 0
    skipped_missing = 0
    excluded = 0

    for idx, (file_id, file_path) in enumerate(files, 1):
        progress_label = f"[{idx}/{len(files)}]"

        source = Path(file_path)
        if not source.exists():
            print(f"{progress_label} MISSING: {file_path}")
            skipped_missing += 1
            continue

        file_size = source.stat().st_size

        # Only attempt EXIF read if require_exif is on or we need it for dating anyway;
        # cheap enough to just always try for image-like files.
        exif_data = get_exif_data(source)

        passes, reason = check_filters(source, file_size, exif_data, filters)
        if not passes:
            print(f"{progress_label} EXCLUDED: {file_path} ({reason})")
            update_file_status(database_path, file_id, 'excluded')
            excluded += 1
            continue

        print(f"{progress_label} {file_path} ({format_size(file_size)})")

        photo_date = get_photo_date(source, exif_data)
        dest = get_archive_path(file_path, archive_root, photo_date)
        file_extension = source.suffix.lower()

        if copy_file_with_progress(source, dest, file_size):
            update_file_status(database_path, file_id, 'imported')
            add_to_archive_database(archive_conn, dest, source, file_extension, file_size, photo_date)
            print(f"    OK -> {dest}")
            copied += 1
        else:
            print("    FAILED")
            failed += 1

    archive_conn.close()

    print("-" * 60)
    print(f"Copied: {copied}")
    print(f"Excluded by filter: {excluded}")
    print(f"Failed: {failed}")
    print(f"Missing (source no longer exists): {skipped_missing}")
    print(f"Total evaluated: {len(files)}")


if __name__ == "__main__":
    main()
    