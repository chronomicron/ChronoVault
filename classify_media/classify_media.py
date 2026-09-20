"""
classify_media.py

The conservative media-classification stage between Indexer and Condition
Database.  It examines already-indexed files and records whether an image is
likely to be a personal camera/scanned photograph or a web/graphic asset.

Only categories explicitly named in ``exclude_categories`` are moved out of
``located`` status.  The default excludes *only* ``certain_not``: it is more
important not to lose a stripped photo or scan than to avoid hashing one
ambiguous file.

Usage:
    python3 classify_media/classify_media.py classify_media/config.json
"""

import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from classify_media.image_tools.image_inspection import inspect_image


CATEGORIES = (
    "certain_yes",
    "likely_yes",
    "unknown",
    "likely_not",
    "certain_not",
)


def load_config(config_file):
    """Load and validate the intentionally small, JSON-only configuration."""
    try:
        with open(config_file, "r", encoding="utf-8") as handle:
            config = json.load(handle)
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_file}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Configuration file '{config_file}' is not valid JSON.")
        sys.exit(1)

    database_path = config.get("database_path")
    if not database_path:
        print("Error: 'database_path' must be specified in config.")
        sys.exit(1)

    image_extensions = {f".{ext.lower().lstrip('.')}" for ext in config.get(
        "image_extensions", ["jpg", "jpeg", "bmp", "tif", "tiff", "png", "gif", "webp"]
    )}
    excluded = config.get("exclude_categories", ["certain_not"])
    invalid = set(excluded) - set(CATEGORIES)
    if invalid:
        print(f"Error: unknown exclude_categories value(s): {', '.join(sorted(invalid))}")
        sys.exit(1)

    return {
        "database_path": database_path,
        "output_report_path": config.get("output_report_path", "classification_report.json"),
        "image_extensions": image_extensions,
        "exclude_categories": set(excluded),
        "force_reclassify": config.get("force_reclassify", False),
    }


def ensure_column(conn, column, column_type):
    cursor = conn.execute("PRAGMA table_info(located_files)")
    existing = {row[1] for row in cursor.fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE located_files ADD COLUMN {column} {column_type}")
        conn.commit()


def category_for_score(score):
    """Turn a likelihood score into the five deliberate, user-facing bands."""
    if score >= 85:
        return "certain_yes"
    if score >= 65:
        return "likely_yes"
    if score >= 35:
        return "unknown"
    if score >= 15:
        return "likely_not"
    return "certain_not"


def classify_media(evidence):
    """Return a score, category, and explanation for one already-indexed file.

    The public shape mirrors analyze_date: callers provide a ``file_path`` and
    receive a plain, JSON-friendly result.  Image-specific observation lives
    in image_tools so document/video tools can be added without complicating
    this orchestration layer.
    """
    file_path = evidence["file_path"]
    extension = Path(file_path).suffix.lower()
    image_extensions = evidence.get("image_extensions", set())

    if extension not in image_extensions:
        return {
            "media_score": 50,
            "media_category": "unknown",
            "media_reason": f"No classifier is implemented yet for {extension or 'files without an extension'}.",
        }

    observation = inspect_image(file_path)
    if observation["error"]:
        return {
            "media_score": 50,
            "media_category": "unknown",
            "media_reason": f"Could not inspect image safely: {observation['error']}",
        }

    score = 50
    reasons = []
    name_and_path = str(file_path).lower()

    if observation["camera_exif"]:
        score += 45
        reasons.append("camera EXIF make/model metadata")

    if observation["camera_filename"]:
        score += 15
        reasons.append("camera-style filename")

    if observation["asset_name"]:
        score -= 50
        reasons.append("web-asset filename/path")

    width, height = observation["width"], observation["height"]
    smallest_side = min(width, height)
    pixels = width * height
    if smallest_side <= 128:
        score -= 45
        reasons.append(f"very small dimensions ({width}x{height})")
    elif smallest_side <= 320:
        score -= 25
        reasons.append(f"small dimensions ({width}x{height})")
    elif pixels >= 4_000_000:
        score += 15
        reasons.append("high-resolution image")
    elif pixels >= 1_000_000:
        score += 10
        reasons.append("photo-sized image")

    if observation["file_size"] < 10_000:
        score -= 20
        reasons.append("very small file size")
    elif observation["file_size"] >= 250_000:
        score += 5
        reasons.append("substantial file size")

    if observation["palette_or_binary"]:
        score -= 25
        reasons.append(f"{observation['mode']} palette/binary color mode")
    elif observation["low_color_count"]:
        score -= 20
        reasons.append("very limited sampled color palette")
    elif observation["high_color_count"]:
        score += 10
        reasons.append("photographic color variation")

    if observation["scan_like"]:
        score += 30
        reasons.append("high-DPI, photo-sized scan-like image")

    # A real camera make/model is stronger evidence than generic small-image
    # heuristics.  Some legitimate photos have been resized for sharing or
    # are camera-generated thumbnails; retain them for later review unless a
    # direct web-asset clue also contradicts the metadata.
    if observation["camera_exif"] and not observation["asset_name"]:
        score = max(score, 65)

    score = max(0, min(100, score))
    category = category_for_score(score)
    reason = "; ".join(reasons) if reasons else "No strong camera, scan, or web-asset signal found."
    return {"media_score": score, "media_category": category, "media_reason": reason}


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 classify_media/classify_media.py <config.json>")
        sys.exit(1)

    config = load_config(sys.argv[1])
    print(f"Loading configuration from: {sys.argv[1]}")
    print(f"Database: {config['database_path']}")
    print(f"Excluded categories: {', '.join(sorted(config['exclude_categories'])) or '(none)'}")
    print("-" * 60)

    conn = sqlite3.connect(config["database_path"])
    conn.row_factory = sqlite3.Row
    ensure_column(conn, "media_score", "INTEGER")
    ensure_column(conn, "media_category", "TEXT")
    ensure_column(conn, "media_reason", "TEXT")
    ensure_column(conn, "media_excluded", "INTEGER DEFAULT 0")

    where = "status = 'located'"
    if not config["force_reclassify"]:
        where += " AND media_category IS NULL"
    else:
        # Revisit normal files and files *this classifier* excluded, but never
        # revive a row excluded later by Importer's independent filters.
        where = "(status = 'located' OR media_excluded = 1)"
    rows = conn.execute(f"SELECT * FROM located_files WHERE {where}").fetchall()
    if not rows:
        print("No files need classification. Nothing to do.")
        conn.close()
        return

    counts = Counter()
    failures = []
    for index, row in enumerate(rows, 1):
        print(f"[{index}/{len(rows)}] {row['file_path']}")
        try:
            result = classify_media({
                "file_path": row["file_path"],
                "image_extensions": config["image_extensions"],
            })
            classifier_excluded = int(result["media_category"] in config["exclude_categories"])
            new_status = "excluded" if classifier_excluded else "located"
            conn.execute(
                """UPDATE located_files
                   SET media_score = ?, media_category = ?, media_reason = ?, media_excluded = ?, status = ?
                   WHERE id = ?""",
                (result["media_score"], result["media_category"], result["media_reason"], classifier_excluded, new_status, row["id"]),
            )
            conn.commit()
            counts[result["media_category"]] += 1
            print(f"    {result['media_category']} ({result['media_score']}/100): {result['media_reason']}")
        except Exception as error:
            failures.append({"file_path": row["file_path"], "error": str(error)})
            print(f"    FAILED: {error}")

    report = {
        "classification_timestamp": datetime.now().isoformat(),
        "database_path": config["database_path"],
        "summary": {
            "processed": len(rows) - len(failures),
            "failed": len(failures),
            "categories": {category: counts[category] for category in CATEGORIES},
            "excluded": sum(counts[category] for category in config["exclude_categories"]),
        },
        "failures": failures,
    }
    with open(config["output_report_path"], "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=4)
    conn.close()
    print("-" * 60)
    print(f"Classified: {report['summary']['processed']}; excluded: {report['summary']['excluded']}; failed: {len(failures)}")
    print(f"Report written to: {config['output_report_path']}")


if __name__ == "__main__":
    main()
