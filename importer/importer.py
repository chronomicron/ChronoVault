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

        if not database_path or not archive_root:
            print("Error: 'database_path' and 'archive_root' must be specified in config.")
            sys.exit(1)

        return database_path, archive_root, extensions
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_file}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Configuration file '{config_file}' is not valid JSON.")
        sys.exit(1)


def get_photo_date(file_path):
    """Extract date from EXIF, then fall back to file system dates."""
    try:
        image = Image.open(file_path)
        exif_data = image._getexif()

        if exif_data:
            for tag_id, value in exif_data.items():
                tag_name = TAGS.get(tag_id, tag_id)
                if tag_name == "DateTimeOriginal" and value:
                    return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
                if tag_name == "DateTimeDigitized" and value:
                    return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass

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
    """Retrieve files from database that match the extensions and have 'located' status."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    ext_list = tuple(
        '.' + ext.lower() if not ext.startswith('.') else ext.lower()
        for ext in extensions
    )

    placeholders = ','.join('?' * len(ext_list))
    query = f'''
        SELECT id, file_path FROM located_files
        WHERE status = 'located' AND LOWER(file_extension) IN ({placeholders})
    '''
    cursor.execute(query, ext_list)
    files = cursor.fetchall()
    conn.close()

    return files


def update_file_status(db_path, file_id, status):
    """Update the status of a file in the database."""
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
    database_path, archive_root, extensions = load_config(config_file)

    if not extensions:
        print("Error: No extensions specified in configuration file.")
        sys.exit(1)

    print(f"Database: {database_path}")
    print(f"Archive root: {archive_root}")
    print(f"Extensions to copy: {extensions}")
    print("-" * 60)

    files = get_files_to_copy(database_path, extensions)

    if not files:
        print("No files to copy. (Nothing with status 'located' matches your extensions.)")
        return

    print(f"Found {len(files)} file(s) to copy.")
    print("-" * 60)

    copied = 0
    failed = 0
    skipped_missing = 0

    for idx, (file_id, file_path) in enumerate(files, 1):
        progress_label = f"[{idx}/{len(files)}]"

        source = Path(file_path)
        if not source.exists():
            print(f"{progress_label} MISSING: {file_path}")
            skipped_missing += 1
            continue

        file_size = source.stat().st_size
        print(f"{progress_label} {file_path} ({format_size(file_size)})")

        photo_date = get_photo_date(file_path)
        dest = get_archive_path(file_path, archive_root, photo_date)

        if copy_file_with_progress(source, dest, file_size):
            update_file_status(database_path, file_id, 'imported')
            print(f"    OK -> {dest}")
            copied += 1
        else:
            print("    FAILED")
            failed += 1

    print("-" * 60)
    print(f"Copied: {copied}")
    print(f"Failed: {failed}")
    print(f"Missing (source no longer exists): {skipped_missing}")
    print(f"Total processed: {len(files)}")


if __name__ == "__main__":
    main()
    