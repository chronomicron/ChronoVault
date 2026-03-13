# ChronoVault - Scanner Module
# Description: Scans one or more directories for supported media files,
# collects basic file information and (when possible) capture date from EXIF.
# Returns list of media dictionaries that can be passed to archiver/database.
#
# Can be called from main entry point (CLI) or GUI.
#
# Version History:
#   0.1.1 – Initial placeholder file with simple recursive file finder

from pathlib import Path
from typing import List, Dict, Any
import datetime
from PIL import Image
from PIL.ExifTags import TAGS


SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.heic', '.mov', '.mp4'}


def scan_directory(
    root_dir: str | Path,
    extensions: set = SUPPORTED_EXTENSIONS
) -> List[Dict[str, Any]]:
    """
    Placeholder: Recursively find media files and extract minimal metadata.
    
    Returns list of dicts like:
        {
            'original_path': str,
            'capture_date': ISO string or None,
            'file_size': int,
            'extension': str
        }
    """
    root = Path(root_dir)
    if not root.is_dir():
        return []

    found = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in extensions:
            continue

        item = {
            'original_path': str(path),
            'file_size': path.stat().st_size,
            'extension': path.suffix.lower(),
            'capture_date': None
        }

        # Try to read EXIF date (very basic)
        try:
            with Image.open(path) as img:
                exif = img.getexif()
                if exif:
                    date_str = exif.get(36867) or exif.get(306)  # DateTimeOriginal or DateTime
                    if date_str:
                        # Very naive parsing — improve later
                        item['capture_date'] = date_str.replace(":", "-", 2).replace(" ", "T")
        except Exception:
            pass

        # Fallback: use file modification time
        if not item['capture_date']:
            mtime = datetime.datetime.fromtimestamp(path.stat().st_mtime)
            item['capture_date'] = mtime.isoformat()

        found.append(item)

    return found


if __name__ == "__main__":
    # Quick test
    import sys
    if len(sys.argv) < 2:
        print("Usage: python scanner.py /path/to/folder")
        sys.exit(1)

    results = scan_directory(sys.argv[1])
    print(f"Found {len(results)} media files.")
    if results:
        print("First item:", results[0])