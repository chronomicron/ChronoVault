# ChronoVault - Archiver Module
# Description: Responsible for copying discovered media files into the organized vault
# structure (YYYY/MM/DD folders), handling duplicates, optional deletion of originals,
# and (later) notifying the database module of successful archiving.
#
# Called from the main entry point or GUI when archiving is triggered.
#
# Version History:
#   0.1.1 – Initial placeholder file with basic copy logic stub

from pathlib import Path
import shutil
import datetime
from typing import List, Dict, Any


def archive_files(
    media_items: List[Dict[str, Any]],
    vault_root: str | Path,
    delete_originals: bool = False
) -> List[Path]:
    """
    Placeholder: Move/copy media files to vault folder structure based on date.
    
    Expected media_items format:
        [{'original_path': '...', 'capture_date': '2023-05-12T14:30:00', ...}, ...]
    
    Returns list of successfully archived vault paths.
    """
    vault_root = Path(vault_root)
    archived_paths = []

    for item in media_items:
        src_path = Path(item.get('original_path'))
        if not src_path.is_file():
            continue

        # Try to get date → fallback to today
        try:
            dt = datetime.datetime.fromisoformat(item.get('capture_date', ''))
            year_month_day = dt.strftime("%Y/%m/%d")
        except (ValueError, TypeError):
            year_month_day = datetime.date.today().strftime("%Y/%m/%d")

        dest_dir = vault_root / year_month_day
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_path = dest_dir / src_path.name

        # Very basic duplicate handling (skip if exists)
        if dest_path.exists():
            print(f"Skipping duplicate: {dest_path}")
            continue

        shutil.copy2(src_path, dest_path)
        archived_paths.append(dest_path)

        if delete_originals:
            try:
                src_path.unlink()
            except Exception as e:
                print(f"Failed to delete original {src_path}: {e}")

    return archived_paths


if __name__ == "__main__":
    # Minimal smoke test
    fake_items = [
        {"original_path": "/tmp/test.jpg", "capture_date": "2024-06-15T10:22:00"},
    ]
    vault = Path("test_vault")
    print("Archiving test files...")
    results = archive_files(fake_items, vault)
    print("Archived:", [str(p) for p in results])
    