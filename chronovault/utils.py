# ChronoVault - Utilities Module
# Description: Collection of small, reusable helper functions used by multiple other modules.
# Includes things like safe path handling, basic EXIF date extraction, thumbnail generation stubs,
# logging helpers, date normalization, etc.
#
# Imported by scanner, archiver, ui, database, etc. when needed.
#
# Version History:
#   0.1.1 – Initial placeholder with basic date and path helpers

from pathlib import Path
from datetime import datetime
from typing import Optional
import logging


# Simple logger setup (can be improved later)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ChronoVault")


def normalize_date(dt_str: Optional[str]) -> Optional[str]:
    """
    Try to turn various date string formats into ISO format (YYYY-MM-DDTHH:MM:SS).
    Returns None if parsing fails.
    """
    if not dt_str:
        return None

    # Very basic fallback parsing - will expand later
    common_formats = [
        "%Y:%m:%d %H:%M:%S",      # common EXIF format
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y%m%d%H%M%S",
    ]

    for fmt in common_formats:
        try:
            dt = datetime.strptime(dt_str, fmt)
            return dt.isoformat()
        except ValueError:
            continue

    return None


def safe_path(path: str | Path) -> Path:
    """Convert to Path and ensure parent directories exist (for writing)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def get_capture_date_fallback(file_path: Path) -> str:
    """Fallback when no EXIF date is found: use file modification time."""
    try:
        mtime = file_path.stat().st_mtime
        return datetime.fromtimestamp(mtime).isoformat()
    except Exception:
        return datetime.now().isoformat()


# Placeholder for future thumbnail generation
def generate_thumbnail_stub(image_path: Path, size: tuple = (128, 128)) -> bool:
    """Later: create small thumbnail and save somewhere. For now just log."""
    logger.info(f"Would generate thumbnail for {image_path} at size {size}")
    return True


if __name__ == "__main__":
    # Quick smoke test
    print(normalize_date("2023:04:15 14:30:22"))
    print(normalize_date("invalid"))
    print(get_capture_date_fallback(Path(__file__)))