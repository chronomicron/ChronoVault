"""
write_data.py

The mutating twin of retrieve_data.py -- deliberately kept in its own
module rather than added to retrieve_data.py. Anything that only needs
to *read* archive data (a list view, a detail panel) can import
retrieve_data.py alone and have no ability whatsoever to move a file or
change the database, even by accident. Importing write_data.py is an
explicit opt-in to that ability.

Like retrieve_data.py, this module knows nothing about Qt or HTML, and
does no "asking" of its own -- it only accepts already-decided,
structured input (a file id and a corrected date) and reports back what
it did, as a plain dict. Whichever UI actually collects that input from
a person -- a Qt date picker, a web form -- is responsible for the
asking; this module only acts on the answer, the same way a form
submission handler doesn't care what the form looked like.
"""

import shutil
import sqlite3
from pathlib import Path
from datetime import datetime


def _connect(archive_root):
    """Open a connection to archive_database.db inside the given archive folder."""
    db_path = Path(archive_root) / "archive_database.db"
    if not db_path.exists():
        raise FileNotFoundError(f"No archive database found at '{db_path}'.")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_correction_columns(conn):
    """Add the columns a correction needs, if they don't already exist (schema upgrade, in place)."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(archive_files)")
    existing = {row[1] for row in cursor.fetchall()}
    if 'user_corrected_date' not in existing:
        cursor.execute("ALTER TABLE archive_files ADD COLUMN user_corrected_date TEXT")
    if 'corrected_at' not in existing:
        cursor.execute("ALTER TABLE archive_files ADD COLUMN corrected_at TEXT")
    conn.commit()


def _get_unique_destination(dest):
    """
    Same collision-avoidance convention Importer uses: if dest already
    exists, append ' (1)', ' (2)', etc. rather than silently overwriting
    an existing file.
    """
    if not dest.exists():
        return dest
    stem, suffix, parent = dest.stem, dest.suffix, dest.parent
    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def apply_date_correction(archive_root, file_id, corrected_date):
    """
    Record a person's corrected date for one archived file, and move it
    out of the review folder into the normal YYYY/MM/DD folder that date
    implies.

    'corrected_date' should be a datetime (or date) object -- parsing
    whatever raw input a UI collected (a date picker's value, a form
    field) into that shape is the caller's responsibility, same as
    'asking' itself.

    The original algorithmic evidence for the file (date_taken,
    date_source, confidence, date_reason -- whatever analyze_date
    originally concluded) is left completely untouched, as a permanent
    record of what the automatic analysis found. Only 'user_corrected_date'
    and 'corrected_at' are added, and 'date_uncertain' is flipped to 0 --
    the file is now considered resolved, without erasing why it was
    uncertain in the first place.

    Returns a dict:
        {'success': bool, 'new_archive_path': str or None, 'error': str or None}
    """
    conn = _connect(archive_root)
    _ensure_correction_columns(conn)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM archive_files WHERE id = ?", (file_id,))
    row = cursor.fetchone()
    if row is None:
        conn.close()
        return {'success': False, 'new_archive_path': None, 'error': f"No file with id {file_id}."}

    current_path = Path(row['archive_path'])
    if not current_path.exists():
        conn.close()
        return {'success': False, 'new_archive_path': None,
                'error': f"File no longer exists on disk: {current_path}"}

    year = corrected_date.strftime("%Y")
    month = corrected_date.strftime("%m")
    day = corrected_date.strftime("%d")
    dest_dir = Path(archive_root) / year / month / day
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = _get_unique_destination(dest_dir / current_path.name)

    try:
        shutil.move(str(current_path), str(dest))
    except Exception as e:
        conn.close()
        return {'success': False, 'new_archive_path': None, 'error': str(e)}

    cursor.execute('''
        UPDATE archive_files
        SET archive_path = ?, user_corrected_date = ?, corrected_at = ?, date_uncertain = 0
        WHERE id = ?
    ''', (str(dest), corrected_date.isoformat(), datetime.now().isoformat(), file_id))
    conn.commit()
    conn.close()

    return {'success': True, 'new_archive_path': str(dest), 'error': None}
