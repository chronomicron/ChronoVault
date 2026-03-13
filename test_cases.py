# ChronoVault - Test Case Generator
# Description: Creates fake directory structures with mock image files that contain
# controlled EXIF metadata. Useful for development, debugging and automated tests
# without needing real photo libraries.
#
# Can generate folders like:
#   test_photos/2023/06/12/IMG_001.jpg (with EXIF date)
#   test_photos/unknown/IMG_noexif.png
#
# Version History:
#   0.1.1 – Initial placeholder – creates empty folders + dummy text files

from pathlib import Path
import datetime
import os


def create_test_structure(base_dir: str = "test_photos", count_per_year: int = 5):
    """
    Very simple initial version: create year/month/day folders and place dummy files.
    Later versions will embed real-looking EXIF using Pillow.
    """
    base = Path(base_dir)
    base.mkdir(exist_ok=True)

    years = [2022, 2023, 2024]

    for year in years:
        for month in range(1, 13, 3):  # every 3 months to keep it small
            for day in [5, 15, 25]:
                folder = base / f"{year:04d}/{month:02d}/{day:02d}"
                folder.mkdir(parents=True, exist_ok=True)

                for i in range(1, count_per_year + 1):
                    filename = f"TEST_{year}_{month:02d}_{day:02d}_{i:03d}.jpg"
                    filepath = folder / filename

                    # For now just create empty files or small text placeholder
                    with open(filepath, "w") as f:
                        f.write(f"Mock photo file - {filename}\n")
                        f.write(f"Would have EXIF date: {year}-{month:02d}-{day:02d} 14:30:00\n")

                    print(f"Created: {filepath}")

    # One unknown folder
    unknown = base / "unknown"
    unknown.mkdir(exist_ok=True)
    with open(unknown / "no_date_info.png", "w") as f:
        f.write("File without date metadata\n")


if __name__ == "__main__":
    print("Generating basic test photo structure...")
    create_test_structure()
    print("\nDone. Folder created/updated: ./test_photos/")
    print("Next step: enhance this script to write real EXIF tags using Pillow.")