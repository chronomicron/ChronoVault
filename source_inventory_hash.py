"""Shared freshness-aware SHA-256 caching for located_files source rows."""

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path


HASH_COLUMNS = {
    'file_hash': 'TEXT',
    'hash_file_size': 'INTEGER',
    'hash_mtime_ns': 'INTEGER',
    'hash_computed_at': 'TEXT',
}
HASH_CHUNK_SIZE = 4 * 1024 * 1024
HASH_RETRIES = 2
PROGRESS_THRESHOLD_BYTES = 20 * 1024 * 1024


def _format_size(num_bytes):
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}PB"


def ensure_source_hash_columns(conn):
    """Add freshness columns without changing existing rows or other columns."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(located_files)")
    existing = {row[1] for row in cursor.fetchall()}
    for column, column_type in HASH_COLUMNS.items():
        if column not in existing:
            cursor.execute(f"ALTER TABLE located_files ADD COLUMN {column} {column_type}")
    conn.commit()


def file_fingerprint(path):
    """Return the current (size, nanosecond mtime) fingerprint."""
    stat = Path(path).stat()
    return stat.st_size, stat.st_mtime_ns


def _read_state(stat):
    """Metadata used only to detect replacement or mutation during a read."""
    return (
        stat.st_dev,
        stat.st_ino,
        stat.st_size,
        stat.st_mtime_ns,
        stat.st_ctime_ns,
    )


def hash_source_file(path, retries=HASH_RETRIES):
    """Hash a stable file state, retrying when its metadata changes mid-read.

    Returns (sha256, size, mtime_ns, computed_at), or None after repeated
    instability / I/O failure. The returned metadata describes the bytes read.
    """
    path = Path(path)
    for attempt in range(retries + 1):
        try:
            hasher = hashlib.sha256()
            with path.open('rb') as source:
                before = os.fstat(source.fileno())
                before_state = _read_state(before)
                show_progress = before.st_size >= PROGRESS_THRESHOLD_BYTES
                read_bytes = 0
                while True:
                    chunk = source.read(HASH_CHUNK_SIZE)
                    if not chunk:
                        break
                    hasher.update(chunk)
                    read_bytes += len(chunk)
                    if show_progress:
                        percent = (read_bytes / before.st_size) * 100
                        print(
                            f"\r    hashing: {_format_size(read_bytes)} / "
                            f"{_format_size(before.st_size)} ({percent:.1f}%)",
                            end='', flush=True,
                        )
                after = os.fstat(source.fileno())
            if show_progress:
                print()
            path_stat = path.stat()
            if _read_state(before) == _read_state(after) == _read_state(path_stat):
                return (
                    hasher.hexdigest(),
                    before.st_size,
                    before.st_mtime_ns,
                    datetime.now(timezone.utc).isoformat(),
                )
        except OSError:
            if attempt == retries:
                return None
        if attempt < retries:
            continue
    return None


def is_fresh(file_hash, stored_size, stored_mtime_ns, current_size, current_mtime_ns):
    """Derive cache freshness from its digest and stored file snapshot."""
    return (
        bool(file_hash)
        and stored_size is not None
        and stored_mtime_ns is not None
        and stored_size == current_size
        and stored_mtime_ns == current_mtime_ns
    )
