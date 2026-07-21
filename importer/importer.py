import json
import sys
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

# No digital camera existed before this date, so any "date taken" earlier
# than this is treated as implausible. (Also happens to be the author's
# birthday -- also predates digital cameras. Small tribute, not a bug.)
EARLIEST_PLAUSIBLE_DATE = datetime(1972, 7, 26)


def load_config(config_file):
    """Load the importer configuration from JSON."""
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        database_path = config.get('database_path')
        archive_root = config.get('archive_root')
        extensions = config.get('extensions_to_copy', [])

        min_file_size_bytes = config.get('min_file_size_bytes', 0)
        max_file_size_bytes = config.get('max_file_size_bytes', None)  # None = no upper limit
        require_exif = config.get('require_exif', False)
        exclude_path_contains = config.get('exclude_path_contains', [])

        exclude_thumbnails = config.get('exclude_thumbnails', True)
        thumbnail_extensions = config.get('thumbnail_extensions', ['thm'])

        # How many days of disagreement between EXIF date and filesystem
        # creation date before we flag the file as date_uncertain.
        date_mismatch_threshold_days = config.get('date_mismatch_threshold_days', 1)

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
            'date_mismatch_threshold_days': date_mismatch_threshold_days,
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
            date_source TEXT,
            filesystem_creation_date TEXT,
            date_uncertain INTEGER DEFAULT 0,
            date_added TEXT,
            camera_make TEXT,
            camera_model TEXT,
            gps_latitude REAL,
            gps_longitude REAL,
            aperture TEXT,
            iso_speed TEXT,
            focal_length_mm TEXT
        )
    ''')
    conn.commit()
    return conn, archive_db_path


def add_to_archive_database(conn, record):
    """Insert a record for a newly copied file into archive_database."""
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO archive_files
        (archive_path, source_path, file_extension, file_size,
         date_taken, date_source, filesystem_creation_date, date_uncertain, date_added,
         camera_make, camera_model, gps_latitude, gps_longitude,
         aperture, iso_speed, focal_length_mm)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        record['archive_path'], record['source_path'], record['file_extension'], record['file_size'],
        record['date_taken'], record['date_source'], record['filesystem_creation_date'],
        record['date_uncertain'], record['date_added'],
        record['camera_make'], record['camera_model'], record['gps_latitude'], record['gps_longitude'],
        record['aperture'], record['iso_speed'], record['focal_length_mm']
    ))
    conn.commit()


def get_exif_data(file_path):
    """Return the raw EXIF dict for a file, or None if unavailable/not an image."""
    try:
        image = Image.open(file_path)
        return image._getexif()
    except Exception:
        return None


def get_readable_exif(exif_data):
    """Convert a raw EXIF dict into a {tag_name: value} dict for easy lookups."""
    if not exif_data:
        return {}
    return {TAGS.get(tag_id, tag_id): value for tag_id, value in exif_data.items()}


def convert_gps_to_decimal(gps_coord, gps_ref):
    """Convert an EXIF GPS (degrees, minutes, seconds) tuple to decimal degrees."""
    try:
        degrees, minutes, seconds = gps_coord
        decimal = float(degrees) + float(minutes) / 60 + float(seconds) / 3600
        if gps_ref in ('S', 'W'):
            decimal = -decimal
        return decimal
    except Exception:
        return None


def get_gps_coordinates(readable_exif):
    """Extract latitude/longitude from EXIF GPSInfo, if present."""
    gps_info = readable_exif.get('GPSInfo')
    if not gps_info:
        return None, None

    gps_tags = {GPSTAGS.get(key, key): value for key, value in gps_info.items()}

    lat = gps_tags.get('GPSLatitude')
    lat_ref = gps_tags.get('GPSLatitudeRef')
    lon = gps_tags.get('GPSLongitude')
    lon_ref = gps_tags.get('GPSLongitudeRef')

    latitude = convert_gps_to_decimal(lat, lat_ref) if lat and lat_ref else None
    longitude = convert_gps_to_decimal(lon, lon_ref) if lon and lon_ref else None

    return latitude, longitude


def get_camera_info(readable_exif):
    """Extract camera make/model/aperture/iso/focal length from EXIF, where present."""
    camera_make = readable_exif.get('Make')
    camera_model = readable_exif.get('Model')

    aperture = readable_exif.get('FNumber')
    if aperture is not None:
        try:
            aperture = f"f/{float(aperture):.1f}"
        except Exception:
            aperture = str(aperture)

    iso_speed = readable_exif.get('ISOSpeedRatings')
    if iso_speed is not None:
        iso_speed = str(iso_speed)

    focal_length = readable_exif.get('FocalLength')
    if focal_length is not None:
        try:
            focal_length = f"{float(focal_length):.1f}mm"
        except Exception:
            focal_length = str(focal_length)

    return (
        str(camera_make).strip() if camera_make else None,
        str(camera_model).strip() if camera_model else None,
        aperture,
        iso_speed,
        focal_length,
    )


def get_photo_date_from_exif(readable_exif):
    """Pull DateTimeOriginal or DateTimeDigitized out of a readable EXIF dict."""
    for tag_name in ('DateTimeOriginal', 'DateTimeDigitized'):
        value = readable_exif.get(tag_name)
        if value:
            try:
                return datetime.strptime(value, "%Y:%m:%d %H:%M:%S"), tag_name
            except ValueError:
                continue
    return None, None


def get_filesystem_creation_date(file_path):
    """File system creation date, used as a fallback and for cross-checking EXIF."""
    try:
        stat = Path(file_path).stat()
        return datetime.fromtimestamp(stat.st_ctime)
    except Exception:
        return None


def determine_date_info(file_path, readable_exif, mismatch_threshold_days):
    """
    Work out the date to use for archiving a file, where that date came from,
    and whether it should be flagged as uncertain.

    Returns a dict with: date_taken, date_source, filesystem_creation_date, date_uncertain
    """
    exif_date, exif_tag = get_photo_date_from_exif(readable_exif)
    fs_date = get_filesystem_creation_date(file_path)

    date_uncertain = False

    if exif_date:
        date_taken = exif_date
        date_source = 'exif_original' if exif_tag == 'DateTimeOriginal' else 'exif_digitized'

        # Trigger 3: EXIF date and filesystem date disagree by more than the threshold.
        if fs_date:
            delta_days = abs((exif_date - fs_date).days)
            if delta_days > mismatch_threshold_days:
                date_uncertain = True
    else:
        # Trigger 1: no EXIF date at all -- falling back to filesystem date.
        date_taken = fs_date
        date_source = 'filesystem_fallback'
        date_uncertain = True

    # Trigger 2: implausible date -- before digital cameras existed, or in the future.
    if date_taken:
        if date_taken < EARLIEST_PLAUSIBLE_DATE or date_taken > datetime.now():
            date_uncertain = True

    return {
        'date_taken': date_taken,
        'date_source': date_source,
        'filesystem_creation_date': fs_date,
        'date_uncertain': date_uncertain,
    }


def get_archive_path(file_path, archive_root, date_taken):
    """Determine the archive destination path based on the resolved date."""
    if not date_taken:
        print(f"Warning: Could not determine any date for {file_path}, using current date")
        date_taken = datetime.now()

    year = date_taken.strftime("%Y")
    month = date_taken.strftime("%m")
    day = date_taken.strftime("%d")

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
    can change between runs and a previously-excluded file may pass on a later
    run. Only 'imported' files are considered permanently done and are skipped.
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
          f"({filters['thumbnail_extensions']}), "
          f"date_mismatch_threshold_days={filters['date_mismatch_threshold_days']}")

    archive_conn, archive_db_path = init_archive_database(archive_root)
    print(f"Archive database: {archive_db_path}")
    print("-" * 60)

    files = get_files_to_copy(database_path, extensions)

    if not files:
        print("No files to copy. (Nothing with status 'located' or 'excluded' matches your extensions.)")
        archive_conn.close()
        return

    print(f"Found {len(files)} file(s) to evaluate.")
    print("-" * 60)

    copied = 0
    failed = 0
    skipped_missing = 0
    excluded = 0
    uncertain_dates = 0

    for idx, (file_id, file_path) in enumerate(files, 1):
        progress_label = f"[{idx}/{len(files)}]"

        source = Path(file_path)
        if not source.exists():
            print(f"{progress_label} MISSING: {file_path}")
            skipped_missing += 1
            continue

        file_size = source.stat().st_size
        raw_exif = get_exif_data(source)
        readable_exif = get_readable_exif(raw_exif)

        passes, reason = check_filters(source, file_size, raw_exif, filters)
        if not passes:
            print(f"{progress_label} EXCLUDED: {file_path} ({reason})")
            update_file_status(database_path, file_id, 'excluded')
            excluded += 1
            continue

        print(f"{progress_label} {file_path} ({format_size(file_size)})")

        date_info = determine_date_info(source, readable_exif, filters['date_mismatch_threshold_days'])
        date_taken = date_info['date_taken']
        dest = get_archive_path(file_path, archive_root, date_taken)
        file_extension = source.suffix.lower()

        camera_make, camera_model, aperture, iso_speed, focal_length = get_camera_info(readable_exif)
        gps_latitude, gps_longitude = get_gps_coordinates(readable_exif)

        if copy_file_with_progress(source, dest, file_size):
            update_file_status(database_path, file_id, 'imported')

            record = {
                'archive_path': dest,
                'source_path': source,
                'file_extension': file_extension,
                'file_size': file_size,
                'date_taken': date_taken.isoformat() if date_taken else None,
                'date_source': date_info['date_source'],
                'filesystem_creation_date': (
                    date_info['filesystem_creation_date'].isoformat()
                    if date_info['filesystem_creation_date'] else None
                ),
                'date_uncertain': 1 if date_info['date_uncertain'] else 0,
                'date_added': datetime.now().isoformat(),
                'camera_make': camera_make,
                'camera_model': camera_model,
                'gps_latitude': gps_latitude,
                'gps_longitude': gps_longitude,
                'aperture': aperture,
                'iso_speed': iso_speed,
                'focal_length_mm': focal_length,
            }
            add_to_archive_database(archive_conn, record)

            uncertain_tag = " [UNCERTAIN DATE]" if date_info['date_uncertain'] else ""
            print(f"    OK -> {dest}{uncertain_tag}")
            copied += 1
            if date_info['date_uncertain']:
                uncertain_dates += 1
        else:
            print("    FAILED")
            failed += 1

    archive_conn.close()

    print("-" * 60)
    print(f"Copied: {copied}")
    print(f"  of which uncertain dates: {uncertain_dates}")
    print(f"Excluded by filter: {excluded}")
    print(f"Failed: {failed}")
    print(f"Missing (source no longer exists): {skipped_missing}")
    print(f"Total evaluated: {len(files)}")


if __name__ == "__main__":
    main()
    