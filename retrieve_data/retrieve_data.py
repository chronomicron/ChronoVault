"""
retrieve_data.py

A UI-agnostic data-access layer over archive_database.db.

This module knows nothing about Qt, HTML, or any particular display
technology -- it only knows how to query the archive database and hand
back plain Python dicts (strings, numbers, booleans -- nothing that isn't
JSON-serializable). That's deliberate: the exact same functions here can
be called directly by a desktop app (PySide6, say) running on the same
machine, or wrapped in a couple of lines by a small web server (Flask,
FastAPI, whatever) to serve the identical data as JSON to a browser.
Neither consumer needs its own copy of this querying logic, and neither
is assumed or favored over the other.

What this module does NOT do:
- It does not read image bytes or generate thumbnails. It returns a
  resolved, absolute file path for each item -- what a caller does with
  that path (open it directly on disk, stream it over HTTP, downscale it
  for a thumbnail) is entirely up to that caller. Different display
  layers will reasonably want different things here (a desktop app can
  just open the file; a web layer needs its own route to serve the
  bytes), so it doesn't belong in a shared data layer.
- It does not move files or write to the database. That's a separate,
  deliberately riskier concern -- see the (future) write-side functions,
  e.g. apply_date_correction(), once this read-side shape is confirmed.

Usage:
    from retrieve_data.retrieve_data import list_review_items, get_file_details

    items = list_review_items("archive")
    for item in items:
        print(item["archive_path"], item["confidence"], item["date_reason"])

    details = get_file_details("archive", file_id=12)
"""

import sqlite3
from pathlib import Path


def _connect(archive_root):
    """Open a connection to archive_database.db inside the given archive folder."""
    db_path = Path(archive_root) / "archive_database.db"
    if not db_path.exists():
        raise FileNotFoundError(f"No archive database found at '{db_path}'.")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # lets us access columns by name
    return conn


def _row_to_item_dict(row):
    """
    Convert one archive_files row into a plain, display-ready dict.

    Date fields (date_taken, filesystem_creation_date, date_added) are
    already stored as ISO-format strings by Importer, so no conversion
    is needed here -- everything in the returned dict is already
    JSON-safe as-is.
    """
    item = dict(row)

    # Resolved absolute path, so any consumer (desktop or web) can locate
    # the actual file without needing to know or guess the caller's
    # current working directory.
    resolved_path = Path(item['archive_path']).resolve()
    item['absolute_path'] = str(resolved_path)
    item['file_exists'] = resolved_path.exists()

    return item


def list_review_items(archive_root):
    """
    Return every archived file currently flagged as date-uncertain
    (i.e. sitting in the review folder instead of a normal date folder),
    most recently added first.

    Returns a list of dicts. Each dict is every column from archive_files
    for that row, plus 'absolute_path' and 'file_exists'.
    """
    conn = _connect(archive_root)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM archive_files WHERE date_uncertain = 1 ORDER BY date_added DESC"
    )
    rows = cursor.fetchall()
    conn.close()

    return [_row_to_item_dict(row) for row in rows]


def get_file_details(archive_root, file_id):
    """
    Return the full record for a single archived file by its database id,
    or None if no file with that id exists.

    Same dict shape as list_review_items() -- meant for a "detail view"
    once a user has selected one item from a list.
    """
    conn = _connect(archive_root)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM archive_files WHERE id = ?", (file_id,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    return _row_to_item_dict(row)
