"""
indexer.py

Recursively scans a folder hierarchy for media files matching a
configured extension list, and logs them into a database. Non-
destructive: only reads filesystem metadata, never opens or modifies
the files it finds.

ARCHIVE DETECTION (new): during the same walk, Indexer also recognizes
compressed/disc-image files (zip, tar, tar.gz/tgz, iso -- configurable
via 'archive_extensions') and records their location, unconditionally,
in a separate table. This never opens the archive itself -- it's exactly
as cheap as noticing a normal file's path and size.

Whether Indexer goes a step further and actually PEEKS INSIDE an archive
(no extraction -- just listing which member files inside match the same
'extensions' list Indexer is already searching for) is controlled by
'look_inside_archives' in config.json, defaulting to false. This is a
real design choice, not a limitation: listing an archive's table of
contents is cheap (zipfile/tarfile read only headers, not file data;
ISO listing via pycdlib is similar), but a person may still want to
scan a huge/slow source location first with archive-opening off, then
decide afterward whether it's worth turning on.

BACKFILL: if look_inside_archives is turned on in a LATER run over the
same source location, archives already on record from an earlier run
(logged with contents never listed) are revisited and listed then --
Indexer doesn't need a full rescan just because a config flag changed.
An archive whose contents were already successfully listed is never
re-listed on a later run, the same "don't redo work already done"
principle used for hashing elsewhere in the project.

Usage (from the ChronoVault/ project root):
    python3 indexer/indexer.py indexer/config.json /path/to/search
"""

import json
import sys
import sqlite3
import os
import subprocess
from pathlib import Path
from datetime import datetime

# Built-in archive types Indexer knows how to actually list the contents
# of, without extracting anything. Anything else a person adds to
# archive_extensions in config.json is still detected and its location
# recorded -- it just can't be peeked inside (list_archive_contents()
# returns a note saying so, rather than failing).
KNOWN_ARCHIVE_TYPES = {
    '.zip': 'zip',
    '.tar': 'tar',
    '.tar.gz': 'targz',
    '.tgz': 'targz',
    '.iso': 'iso',
}

# Capped so a single absurdly-large archive (a full disc image with tens
# of thousands of files) can't produce an unreasonably large JSON blob in
# the database. Hitting this cap doesn't mean listing "failed" -- the
# note field says so, and matching_file_count still reflects the true
# total actually found before the cap was hit.
MAX_LISTED_MATCHES = 500


def load_config(config_file):
    """Load and validate indexer configuration before touching its database."""
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_file}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Configuration file '{config_file}' is not valid JSON.")
        sys.exit(1)

    if not isinstance(config, dict):
        print("Error: Configuration must be a JSON object.")
        sys.exit(1)

    database_path = config.get('database_path')
    extensions = config.get('extensions', [])
    archive_extensions = config.get('archive_extensions', ['zip', 'tar', 'tar.gz', 'tgz', 'iso'])
    look_inside_archives = config.get('look_inside_archives', False)

    if not isinstance(database_path, str) or not database_path.strip():
        print("Error: 'database_path' must be a non-empty path in the configuration file.")
        sys.exit(1)
    if not isinstance(extensions, list) or not extensions or not all(
        isinstance(ext, str) and ext.strip() for ext in extensions
    ):
        print("Error: 'extensions' must be a non-empty list of extension strings.")
        sys.exit(1)
    if not isinstance(archive_extensions, list) or not all(
        isinstance(ext, str) and ext.strip() for ext in archive_extensions
    ):
        print("Error: 'archive_extensions' must be a list of extension strings.")
        sys.exit(1)
    if not isinstance(look_inside_archives, bool):
        print("Error: 'look_inside_archives' must be true or false.")
        sys.exit(1)

    return {
        'database_path': database_path.strip(),
        'extensions': [ext.strip() for ext in extensions],
        'archive_extensions': [ext.strip() for ext in archive_extensions],
        'look_inside_archives': look_inside_archives,
    }


def validate_source_root(root_path):
    """Fail before database access unless root_path is an existing directory."""
    root = Path(root_path)
    if not root.exists():
        print(f"Error: Path '{root_path}' does not exist.")
        sys.exit(1)
    if not root.is_dir():
        print(f"Error: '{root_path}' is not a directory.")
        sys.exit(1)


LOCATED_FILES_REQUIRED_COLUMNS = {
    'id', 'file_path', 'file_extension', 'file_size',
    'creation_date', 'modification_date', 'status',
}
LOCATED_FILES_COLUMN_TYPES = {
    'id': 'INTEGER',
    'file_path': 'TEXT',
    'file_extension': 'TEXT',
    'file_size': 'INTEGER',
    'creation_date': 'TEXT',
    'modification_date': 'TEXT',
    'status': 'TEXT',
}
LOCATED_ARCHIVES_REQUIRED_COLUMNS = {
    'id', 'archive_path', 'archive_type', 'archive_size', 'contents_listed',
    'matching_file_count', 'matching_files', 'note',
}
LOCATED_ARCHIVES_COLUMN_TYPES = {
    'id': 'INTEGER',
    'archive_path': 'TEXT',
    'archive_type': 'TEXT',
    'archive_size': 'INTEGER',
    'contents_listed': 'INTEGER',
    'matching_file_count': 'INTEGER',
    'matching_files': 'TEXT',
    'note': 'TEXT',
}


def _table_columns(cursor, table_name):
    cursor.execute("SELECT type FROM sqlite_master WHERE name = ?", (table_name,))
    table = cursor.fetchone()
    if table is None:
        return None, None
    if table[0] != 'table':
        return table[0], set()
    cursor.execute(f'PRAGMA table_info("{table_name}")')
    return table[0], {row[1]: row for row in cursor.fetchall()}


def _has_unique_column(cursor, table_name, column_name):
    cursor.execute(f'PRAGMA index_list("{table_name}")')
    for index in cursor.fetchall():
        if not index[2]:
            continue
        cursor.execute(f'PRAGMA index_info("{index[1]}")')
        if [row[2] for row in cursor.fetchall()] == [column_name]:
            return True
    return False


def _validate_inventory_schema(conn):
    """Reject an existing SQLite file that is not a compatible source inventory."""
    cursor = conn.cursor()
    files_type, files_columns = _table_columns(cursor, 'located_files')
    if files_type != 'table':
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
        names = [row[0] for row in cursor.fetchall()]
        if 'archive_files' in names:
            kind = "appears to be a ChronoVault archive database"
        elif names:
            kind = "contains tables but no ChronoVault 'located_files' inventory table"
        else:
            kind = "is an empty SQLite database with no ChronoVault inventory table"
        raise ValueError(f"database {kind}; refusing to modify it")

    missing = sorted(LOCATED_FILES_REQUIRED_COLUMNS - set(files_columns))
    if missing:
        raise ValueError(
            "database has an incompatible 'located_files' table; missing required "
            f"column(s): {', '.join(missing)}"
        )
    wrong_types = sorted(
        name for name, expected in LOCATED_FILES_COLUMN_TYPES.items()
        if files_columns[name][2].upper() != expected
    )
    if wrong_types or files_columns['id'][5] != 1 or not files_columns['file_path'][3]:
        details = ', '.join(wrong_types) if wrong_types else 'id/file_path constraints'
        raise ValueError(
            "database has an incompatible 'located_files' table; unexpected type or "
            f"constraint for: {details}"
        )
    if not _has_unique_column(cursor, 'located_files', 'file_path'):
        raise ValueError(
            "database has an incompatible 'located_files' table; 'file_path' must be unique"
        )

    archives_type, archives_columns = _table_columns(cursor, 'located_archives')
    if archives_type is not None:
        missing = sorted(LOCATED_ARCHIVES_REQUIRED_COLUMNS - set(archives_columns))
        if archives_type != 'table' or missing:
            detail = f"; missing column(s): {', '.join(missing)}" if missing else ''
            raise ValueError(
                "database has an incompatible 'located_archives' table" + detail
            )
        wrong_types = sorted(
            name for name, expected in LOCATED_ARCHIVES_COLUMN_TYPES.items()
            if archives_columns[name][2].upper() != expected
        )
        if wrong_types or archives_columns['id'][5] != 1 or not archives_columns['archive_path'][3]:
            details = ', '.join(wrong_types) if wrong_types else 'id/archive_path constraints'
            raise ValueError(
                "database has an incompatible 'located_archives' table; unexpected type or "
                f"constraint for: {details}"
            )
        if not _has_unique_column(cursor, 'located_archives', 'archive_path'):
            raise ValueError(
                "database has an incompatible 'located_archives' table; 'archive_path' must be unique"
            )


def validate_database_path(database_path):
    """Check a target path without creating or changing its database."""
    db_path = Path(database_path)
    parent = db_path.parent
    if not parent.exists() or not parent.is_dir():
        print(f"Error: Database directory '{parent}' does not exist or is not a directory.")
        sys.exit(1)

    if not db_path.exists():
        if not os.access(parent, os.W_OK):
            print(f"Error: Database directory '{parent}' is not writable.")
            sys.exit(1)
        return
    if not db_path.is_file():
        print(f"Error: Database path '{database_path}' is not a regular file.")
        sys.exit(1)

    try:
        # mode=ro prevents SQLite from creating or changing a file during preflight.
        conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
        try:
            _validate_inventory_schema(conn)
        finally:
            conn.close()
    except (sqlite3.Error, ValueError) as exc:
        print(f"Error: Existing database '{database_path}' is not a compatible ChronoVault inventory: {exc}.")
        sys.exit(1)


def normalize_extensions(extensions):
    """
    Return a set of lowercase, dot-prefixed extensions. Handles both
    single-suffix ('jpg' -> '.jpg') and multi-dot ('tar.gz' -> '.tar.gz')
    entries -- the caller is responsible for matching multi-dot entries
    with a name.endswith() check rather than Path.suffix, since
    Path('x.tar.gz').suffix is only '.gz', not '.tar.gz'.
    """
    normalized = set()
    for ext in extensions:
        ext = ext.lower()
        if not ext.startswith('.'):
            ext = '.' + ext
        normalized.add(ext)
    return normalized


def matches_any_extension(file_path, ext_set):
    """
    True if file_path's name ends with any extension in ext_set.
    Works correctly for both single-suffix ('.jpg') and multi-dot
    ('.tar.gz') entries, since it checks against the full lowercased
    filename rather than relying on Path.suffix.
    """
    name_lower = file_path.name.lower()
    return any(name_lower.endswith(ext) for ext in ext_set)


def classify_archive_type(file_path):
    """
    Return the KNOWN_ARCHIVE_TYPES value for a file, or 'unknown' if it
    matched archive_extensions but isn't one of the types Indexer
    actually knows how to list contents for.
    """
    name_lower = file_path.name.lower()
    for ext, archive_type in KNOWN_ARCHIVE_TYPES.items():
        if name_lower.endswith(ext):
            return archive_type
    return 'unknown'


def init_database(db_path):
    """Initialize the database and create the located_files table if it doesn't exist."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS located_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            file_extension TEXT,
            file_size INTEGER,
            creation_date TEXT,
            modification_date TEXT,
            status TEXT DEFAULT 'located',
            source_filesystem_uuid TEXT
        )
    ''')
    conn.commit()
    ensure_source_filesystem_uuid_column(conn)
    return conn


def ensure_source_filesystem_uuid_column(conn):
    """Add the nullable UUID field to older inventories without changing rows."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(located_files)")
    columns = {row[1] for row in cursor.fetchall()}
    if 'source_filesystem_uuid' not in columns:
        cursor.execute("ALTER TABLE located_files ADD COLUMN source_filesystem_uuid TEXT")
        conn.commit()


def init_archive_table(conn):
    """
    Create the located_archives table if it doesn't exist. Deliberately a
    DIFFERENT table name from archive_files (which lives in
    archive_database.db, Importer's output) -- same word, different
    meaning, kept apart to avoid confusion between "an archive file
    Indexer found" and "a file already copied into the ChronoVault
    archive."
    """
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS located_archives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            archive_path TEXT UNIQUE NOT NULL,
            archive_type TEXT,
            archive_size INTEGER,
            contents_listed INTEGER DEFAULT 0,
            matching_file_count INTEGER,
            matching_files TEXT,
            note TEXT
        )
    ''')
    conn.commit()


def find_files_and_archives(
    root_path, media_extensions, archive_extensions, skip_nested_archives=True
):
    """
    Walk root_path ONCE, sorting every file into either matching_files
    (matches the media extensions being searched for) or archive_files
    (matches the archive extensions being detected) -- never both, so an
    archive is never mistakenly counted as a media match even if some
    unusual naming coincidence overlapped. A single walk, rather than one
    per concern, matters in practice: the real use case here is scanning
    an old hard drive, potentially a large one, so walking it twice would
    double a cost that's already significant.

    Returns (matching_files, archive_files, interrupted, interruption_reason,
    skipped_archive_roots).
    interrupted is True if the walk didn't finish (an I/O error partway
    through -- a disconnected drive, a failing sector, permissions
    changing mid-scan). Whatever was found BEFORE the interruption is
    still returned, not discarded -- combined with store_files()'s
    batched commits, this means an interrupted scan still saves
    everything it found up to that point, rather than losing the whole
    run. Only a missing/non-directory root path is still a hard,
    immediate exit -- there's nothing partial to salvage from a search
    path that was never valid to begin with.
    """
    media_ext_set = normalize_extensions(media_extensions)
    archive_ext_set = normalize_extensions(archive_extensions)

    matching_files = []
    archive_files = []
    interrupted = False
    interruption_reason = None

    root = Path(root_path)
    if not root.exists():
        print(f"Error: Path '{root_path}' does not exist.")
        sys.exit(1)
    if not root.is_dir():
        print(f"Error: '{root_path}' is not a directory.")
        sys.exit(1)

    skipped_archive_roots = []

    def raise_walk_error(error):
        raise error

    try:
        root_absolute = os.path.abspath(root)
        for current_root, child_directories, filenames in os.walk(
            root, topdown=True, onerror=raise_walk_error
        ):
            current_path = Path(current_root)

            # The selected root itself is handled by the existing guard and
            # its explicit --allow-archive-source override. For a nested root,
            # prune before visiting any descendants or indexing its own files.
            if (
                skip_nested_archives
                and os.path.abspath(current_root) != root_absolute
                and 'archive_database.db' in filenames
            ):
                skipped_archive_roots.append(current_path)
                child_directories[:] = []
                continue

            for filename in filenames:
                file_path = current_path / filename
                if not file_path.is_file():
                    continue
                if matches_any_extension(file_path, archive_ext_set):
                    archive_files.append(file_path)
                    continue
                if matches_any_extension(file_path, media_ext_set):
                    matching_files.append(file_path)
    except OSError as e:
        # Broadened from PermissionError -- a disconnected drive, a
        # failing sector, or a network share dropping mid-scan typically
        # raise OTHER OSError subclasses (FileNotFoundError, "Input/output
        # error", etc.), not PermissionError specifically, and those were
        # previously left uncaught, crashing with a raw traceback instead
        # of a clean, informative stop.
        interrupted = True
        interruption_reason = str(e)
        print(f"\nWarning: Scan interrupted by an I/O error -- {e}")
        print("This could mean a disconnected drive, a failing sector, or a permissions")
        print("problem partway through the scan. Files found before the interruption")
        print("are still saved -- re-run Indexer over the same path once the issue is")
        print("resolved; already-found files won't be re-inserted.")

    return matching_files, archive_files, interrupted, interruption_reason, skipped_archive_roots


COMMIT_BATCH_SIZE = 100


def resolve_filesystem_uuid(file_path, device_id, uuid_cache):
    """Resolve and cache the source filesystem UUID by device number for this scan."""
    if device_id in uuid_cache:
        return uuid_cache[device_id]

    filesystem_uuid = None
    try:
        result = subprocess.run(
            [
                'findmnt', '--noheadings', '--output', 'UUID',
                '--target', str(file_path),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        candidate = result.stdout.strip()
        if result.returncode == 0 and candidate and candidate != '-' and len(candidate.splitlines()) == 1:
            filesystem_uuid = candidate
    except (OSError, subprocess.SubprocessError):
        # Unsupported platforms, missing findmnt, and lookup failures should
        # not prevent the source file from being indexed.
        pass

    uuid_cache[device_id] = filesystem_uuid
    return filesystem_uuid


def store_files(conn, files):
    """
    Insert found media files into the database. Skips files already
    present (by file_path). Commits in batches of COMMIT_BATCH_SIZE
    rather than once at the very end -- measured directly: committing
    every single row is roughly 500x slower than any form of batching,
    but batching even modestly (every 10-50) is effectively free, so
    there's no real cost to choosing safety here. Bounds how much work
    is lost if Indexer is interrupted (killed, crashed, a future Stop
    button) mid-scan to at most COMMIT_BATCH_SIZE files, not the entire run.
    """
    cursor = conn.cursor()
    inserted = 0
    skipped = 0
    uuid_cache = {}

    for i, file_path in enumerate(files, 1):
        try:
            stat = file_path.stat()
            file_extension = file_path.suffix.lower()
            file_size = stat.st_size
            creation_date = datetime.fromtimestamp(stat.st_ctime).isoformat()
            modification_date = datetime.fromtimestamp(stat.st_mtime).isoformat()
            filesystem_uuid = resolve_filesystem_uuid(file_path, stat.st_dev, uuid_cache)

            cursor.execute('''
                INSERT OR IGNORE INTO located_files
                (file_path, file_extension, file_size, creation_date, modification_date,
                 status, source_filesystem_uuid)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (str(file_path), file_extension, file_size, creation_date,
                  modification_date, 'located', filesystem_uuid))

            if cursor.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
                if filesystem_uuid is not None:
                    cursor.execute('''
                        UPDATE located_files
                        SET source_filesystem_uuid = ?
                        WHERE file_path = ? AND source_filesystem_uuid IS NULL
                    ''', (filesystem_uuid, str(file_path)))

        except OSError as e:
            print(f"Warning: Could not read metadata for '{file_path}': {e}")

        if i % COMMIT_BATCH_SIZE == 0:
            conn.commit()

    conn.commit()  # final commit for any remainder under a full batch
    return inserted, skipped


def list_zip_contents(archive_path, media_ext_set):
    """
    List members inside a ZIP whose extension matches media_ext_set,
    without extracting anything. zipfile only reads the central
    directory (a small index at the end of the file), not the file
    contents themselves -- fast regardless of the archive's total size.
    Returns (matching_names, truncated, success).
    """
    import zipfile
    matching = []
    truncated = False
    with zipfile.ZipFile(archive_path) as zf:
        for name in zf.namelist():
            if name.endswith('/'):
                continue  # directory entry, not a file
            if matches_any_extension(Path(name), media_ext_set):
                matching.append(name)
                if len(matching) >= MAX_LISTED_MATCHES:
                    truncated = True
                    break
    return matching, truncated, True


def list_tar_contents(archive_path, media_ext_set):
    """
    List members inside a TAR (or .tar.gz/.tgz) whose extension matches
    media_ext_set, without extracting anything. tarfile.getmembers()
    reads through the archive's headers to build its member list, but
    does not extract or read file contents -- for a compressed tar this
    does mean decompressing enough to walk the headers, which is the
    inherent cost of TAR's format (no separate central-directory index
    the way ZIP has), not a bug in this implementation.
    Returns (matching_names, truncated, success).
    """
    import tarfile
    matching = []
    truncated = False
    with tarfile.open(archive_path) as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            if matches_any_extension(Path(member.name), media_ext_set):
                matching.append(member.name)
                if len(matching) >= MAX_LISTED_MATCHES:
                    truncated = True
                    break
    return matching, truncated, True


def list_iso_contents(archive_path, media_ext_set):
    """
    List files inside an ISO9660/Joliet disc image whose extension
    matches media_ext_set, without ever mounting the image -- pycdlib
    reads the ISO filesystem structures directly. Returns (matching_names,
    truncated, success). success=False (with matching=[] and
    truncated=False) if pycdlib isn't installed; the caller is
    responsible for turning that into a helpful note rather than a crash.
    """
    try:
        import pycdlib
    except ImportError:
        return [], False, False

    matching = []
    truncated = False
    iso = pycdlib.PyCdlib()
    iso.open(str(archive_path))
    try:
        for dirpath, _dirlist, filelist in iso.walk(iso_path='/'):
            for filename in filelist:
                # ISO9660 filenames carry a ";1" version suffix (e.g.
                # "PHOTO.JPG;1") that isn't part of the real extension.
                clean_name = filename.split(';')[0]
                if matches_any_extension(Path(clean_name), media_ext_set):
                    full_name = f"{dirpath.rstrip('/')}/{clean_name}"
                    matching.append(full_name)
                    if len(matching) >= MAX_LISTED_MATCHES:
                        truncated = True
                        break
            if truncated:
                break
    finally:
        iso.close()
    return matching, truncated, True


def list_archive_contents(archive_path, archive_type, media_ext_set):
    """
    Dispatch to the right lister for a known archive type, without
    extracting anything in any case. Returns a dict:
        {'matching': [...], 'truncated': bool, 'success': bool, 'note': str or None}
    success=False means contents genuinely could not be listed (missing
    dependency, corrupt/unreadable archive, or an unrecognized type) --
    the archive's LOCATION is still recorded by the caller regardless;
    this only affects whether its contents get noted too.
    """
    try:
        if archive_type == 'zip':
            matching, truncated, success = list_zip_contents(archive_path, media_ext_set)
            note = f"listing capped at {MAX_LISTED_MATCHES} matches" if truncated else None
            return {'matching': matching, 'truncated': truncated, 'success': success, 'note': note}

        elif archive_type in ('tar', 'targz'):
            matching, truncated, success = list_tar_contents(archive_path, media_ext_set)
            note = f"listing capped at {MAX_LISTED_MATCHES} matches" if truncated else None
            return {'matching': matching, 'truncated': truncated, 'success': success, 'note': note}

        elif archive_type == 'iso':
            matching, truncated, success = list_iso_contents(archive_path, media_ext_set)
            if not success:
                note = "pycdlib not installed -- ISO contents not inspected (pip install pycdlib --break-system-packages)"
            elif truncated:
                note = f"listing capped at {MAX_LISTED_MATCHES} matches"
            else:
                note = None
            return {'matching': matching, 'truncated': truncated, 'success': success, 'note': note}

        else:
            return {'matching': [], 'truncated': False, 'success': False,
                    'note': f"listing not supported for this archive type ('{archive_path.suffix}')"}

    except Exception as e:
        return {'matching': [], 'truncated': False, 'success': False,
                'note': f"could not read archive contents: {e}"}


def store_archives(conn, archive_files, media_extensions, look_inside_archives):
    """
    Record every detected archive's location, unconditionally. If
    look_inside_archives is True, also attempt to list contents for any
    archive that doesn't already have a successful listing on record --
    this is what makes turning the flag on LATER a backfill rather than
    requiring a full rescan: an archive already logged (location only)
    from an earlier run gets listed now instead of being skipped as
    "already in the database."
    """
    cursor = conn.cursor()
    media_ext_set = normalize_extensions(media_extensions)

    newly_recorded = 0
    already_known = 0
    newly_listed = 0
    already_listed = 0
    listing_failed = 0

    for file_path in archive_files:
        archive_path_str = str(file_path)
        cursor.execute(
            "SELECT id, contents_listed FROM located_archives WHERE archive_path = ?",
            (archive_path_str,)
        )
        existing = cursor.fetchone()

        if existing and existing[1] == 1:
            # Already fully processed on a prior run -- don't redo work
            # already done, same principle used for hashing elsewhere.
            already_known += 1
            already_listed += 1
            continue

        archive_type = classify_archive_type(file_path)
        try:
            archive_size = file_path.stat().st_size
        except OSError:
            archive_size = None

        if look_inside_archives:
            result = list_archive_contents(file_path, archive_type, media_ext_set)
            contents_listed = 1 if result['success'] else 0
            matching_file_count = len(result['matching']) if result['success'] else None
            matching_files_json = json.dumps(result['matching']) if result['success'] else None
            note = result['note']
            if result['success']:
                newly_listed += 1
            else:
                listing_failed += 1
        else:
            contents_listed = 0
            matching_file_count = None
            matching_files_json = None
            note = None

        if existing:
            # Backfill case: location was already on record, now updating
            # it with a listing attempt.
            cursor.execute('''
                UPDATE located_archives
                SET archive_type = ?, archive_size = ?, contents_listed = ?,
                    matching_file_count = ?, matching_files = ?, note = ?
                WHERE id = ?
            ''', (archive_type, archive_size, contents_listed,
                  matching_file_count, matching_files_json, note, existing[0]))
        else:
            cursor.execute('''
                INSERT INTO located_archives
                (archive_path, archive_type, archive_size, contents_listed,
                 matching_file_count, matching_files, note)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (archive_path_str, archive_type, archive_size, contents_listed,
                  matching_file_count, matching_files_json, note))
            newly_recorded += 1

        conn.commit()

    return {
        'newly_recorded': newly_recorded,
        'already_known': already_known,
        'newly_listed': newly_listed,
        'already_listed': already_listed,
        'listing_failed': listing_failed,
    }


def looks_like_chronovault_archive(root_path):
    """
    True if root_path itself directly contains archive_database.db --
    the file Importer, and only Importer, ever creates, always at the
    root of whatever archive it built. A strong, unambiguous signal.

    Found necessary by a real, reproducible accident, not a hypothetical:
    pointing Indexer at an existing archive re-discovers every already-
    organized photo as if it were new source material. Importer then
    does its normal, correct job on each one -- recomputes the same
    date, finds the destination already occupied (by itself), and its
    existing filename-collision handling appends "(1)", "(2)" -- every
    piece behaves exactly as designed, and the result is still entirely
    wrong. This check exists to catch that before any scanning starts.

    This direct-root guard runs before the database is opened. During the
    subsequent top-down scan, nested archive roots are detected and pruned
    separately; the explicit override on a selected archive root preserves
    full-scan behavior for deliberate archive migrations.
    """
    return (Path(root_path) / "archive_database.db").exists()


def main():
    args = sys.argv[1:]
    allow_archive_source = '--allow-archive-source' in args
    args = [a for a in args if a != '--allow-archive-source']

    if len(args) != 2:
        print("Usage: python indexer.py <config.json> <top_level_path> [--allow-archive-source]")
        print("Example: python indexer.py config.json /home/user/documents")
        print()
        print("--allow-archive-source: proceed even if <top_level_path> looks like an")
        print("  already-built ChronoVault archive (contains archive_database.db).")
        print("  Only needed if you're deliberately migrating or consolidating an archive.")
        sys.exit(1)

    config_file, root_path = args

    # Checked before ANYTHING else -- before even opening located_files.db --
    # so a mistaken invocation doesn't touch the database at all, not just
    # exit cleanly partway through.
    source_root_is_archive = looks_like_chronovault_archive(root_path)
    if source_root_is_archive and not allow_archive_source:
        print(f"Error: '{root_path}' looks like it might already be a ChronoVault archive")
        print(f"(it contains 'archive_database.db', which only Importer ever creates).")
        print()
        print(f"Indexing an existing archive and importing it again would re-copy every file")
        print(f"into itself, landing as duplicate '(1)', '(2)' copies -- almost certainly not")
        print(f"what you want.")
        print()
        print(f"If you're deliberately migrating or consolidating an existing archive and know")
        print(f"what you're doing, re-run with --allow-archive-source to proceed anyway.")
        sys.exit(1)

    print(f"Loading configuration from: {config_file}")
    config = load_config(config_file)
    database_path = config['database_path']
    extensions = config['extensions']
    archive_extensions = config['archive_extensions']
    look_inside_archives = config['look_inside_archives']

    # Complete all path/schema checks before opening SQLite in write mode.
    # A missing database is a valid first-run case; an existing file must
    # already be a compatible ChronoVault source inventory.
    validate_source_root(root_path)
    validate_database_path(database_path)

    print(f"Database path: {database_path}")
    print(f"Looking for file extensions: {extensions}")
    print(f"Detecting archive extensions: {archive_extensions}")
    print(f"Look inside archives: {look_inside_archives}")
    print(f"Searching in: {root_path}")
    print("-" * 60)

    conn = init_database(database_path)
    init_archive_table(conn)

    (
        files,
        archive_files,
        interrupted,
        interruption_reason,
        skipped_archive_roots,
    ) = find_files_and_archives(
        root_path,
        extensions,
        archive_extensions,
        skip_nested_archives=not (source_root_is_archive and allow_archive_source),
    )
    print(f"Found {len(files)} matching media file(s) on disk.")
    print(f"Found {len(archive_files)} archive file(s) on disk.")
    if skipped_archive_roots:
        print(f"Skipped {len(skipped_archive_roots)} nested ChronoVault archive root(s):")
        for archive_root in skipped_archive_roots:
            print(f"  {archive_root}")

    inserted, skipped = store_files(conn, files)

    archive_stats = store_archives(conn, archive_files, extensions, look_inside_archives)

    conn.close()

    print("-" * 60)
    print("Media files:")
    print(f"  Inserted into database: {inserted}")
    print(f"  Already in database (skipped): {skipped}")
    print(f"  Total matching files: {len(files)}")

    if archive_files:
        print()
        print("Archives:")
        print(f"  Newly recorded (location only): {archive_stats['newly_recorded']}")
        print(f"  Already on record: {archive_stats['already_known']}")
        if look_inside_archives:
            print(f"  Contents newly listed: {archive_stats['newly_listed']}")
            print(f"  Contents already listed (skipped, no rework): {archive_stats['already_listed']}")
            if archive_stats['listing_failed']:
                print(f"  Contents could not be listed: {archive_stats['listing_failed']} "
                      f"(see the 'note' column in located_archives for why)")
        else:
            print(f"  Contents NOT inspected (look_inside_archives is false) -- "
                  f"their locations are saved, so turning this on later will pick them up "
                  f"without needing to rescan {root_path}")

    if interrupted:
        print()
        print("=" * 60)
        print(f"WARNING: The scan was interrupted before completing -- {interruption_reason}")
        print(f"Everything found up to that point has been saved (see counts above).")
        print(f"Re-run Indexer over the same path once the issue is resolved -- already-")
        print(f"found files won't be re-inserted, so this just picks up where it left off.")
        print("=" * 60)
        # Exit non-zero (not a raised exception) so a GUI or script can tell
        # "finished, but something went wrong" apart from a clean run --
        # without this looking like a crash, which it genuinely isn't.
        sys.exit(1)


if __name__ == "__main__":
    main()
