"""
generate_test_data.py

Generates a realistic, messy folder tree of small fake image files for
testing ChronoVault end-to-end (Indexer -> Importer -> Audit -> Duplicate
Finder) without needing real photos.

Every file is tiny (a 20x20 pixel JPEG, a few hundred bytes) so a full run
copies fast, but each one is built to deliberately land in a specific
analyze_date() scenario:

    match        - EXIF DateTimeOriginal close to "now" -> agrees with the
                   filesystem date -> confidence ~100, files land in a
                   normal YYYY/MM/DD folder.
    mismatch     - EXIF DateTimeOriginal far in the past -> disagrees with
                   the filesystem date -> confidence ~70, still lands in a
                   YYYY/MM/DD folder (just flagged as less certain).
    no_exif      - no EXIF at all -> filesystem fallback only ->
                   confidence 30 -> routed to the review bucket.
    implausible  - EXIF date before cameras existed, or in the future ->
                   confidence capped very low -> routed to the review
                   bucket regardless of source.

A handful of "match" files are additionally copied byte-for-byte into
several backup-style folders (same filename, same content, different
location) to exercise Duplicate Finder. A handful of junk files with
video extensions but no real video content are also created, to exercise
Importer's graceful handling of unreadable EXIF (Image.open() will fail
on these, the same way it would on a corrupt or unsupported file).

NOTE on filesystem dates: on Linux there's no reliable way to backdate a
file's ctime (which is what analyze_date's filesystem-fallback signal
reads) -- os.utime() only controls mtime/atime. So every generated file's
filesystem date will effectively be "now" (whenever this script runs).
That's fine for testing: since EXIF dates are fully controllable, varying
EXIF against "now" already exercises every confidence scenario.

Usage:
    python3 generate_test_data/generate_test_data.py
    python3 generate_test_data/generate_test_data.py --output-dir test_data --count 256
    python3 generate_test_data/generate_test_data.py --seed 42   (reproducible run)

The output folder is meant to be regenerated on demand, not committed to
git -- add it to .gitignore (e.g. "test_data/").
"""

import argparse
import random
import struct
import sys
from pathlib import Path
from datetime import datetime, timedelta

from PIL import Image

# Mirrors analyze_date.EARLIEST_PLAUSIBLE_DATE so the "implausible" category
# reliably lands on the wrong side of that line.
EARLIEST_PLAUSIBLE_DATE = datetime(1972, 7, 26)

# A handful of made-up camera make/model pairs for variety in the archive
# (Importer records these when present, purely cosmetic for testing).
CAMERAS = [
    ("Canon", "EOS 90D"),
    ("Nikon", "D7500"),
    ("Sony", "A6400"),
    ("Google", "Pixel 9"),
    ("Apple", "iPhone 15"),
    (None, None),  # no camera info at all, also realistic
]

# Simulated messy real-world folder layout. Files are scattered across
# these at random, similar to the kind of sprawl Indexer has to crawl
# through on a real machine (DCIM folders, old phone backups, downloads).
SUBFOLDERS = [
    "DCIM/Camera",
    "DCIM/Camera/100CANON",
    "Phone_Backup/2025",
    "Phone_Backup/2026",
    "Old_Backup_1",
    "Old_Backup_2",
    "Downloads",
    "Screenshots",
    "Documents/Misc",
]

# Folders used specifically for the duplicate-copy set, simulating the
# kind of repeated backup-of-a-backup mess that produced real duplicates
# in actual testing (archive.2, archive.3, archive.4 style).
DUPLICATE_FOLDERS = [
    "Old_Backup_1/Trash_Copy_A",
    "Old_Backup_1/Trash_Copy_B",
    "Old_Backup_2/Trash_Copy_C",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Generate fake test data for ChronoVault.")
    parser.add_argument(
        "--output-dir", default="test_data",
        help="Folder to generate test files into (default: test_data)"
    )
    parser.add_argument(
        "--count", type=int, default=256,
        help="Approximate number of base images to generate (default: 256)"
    )
    parser.add_argument(
        "--duplicate-sets", type=int, default=5,
        help="How many 'match' files get duplicated into backup folders (default: 5)"
    )
    parser.add_argument(
        "--junk-videos", type=int, default=5,
        help="How many fake unreadable .mp4 files to create (default: 5)"
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for a reproducible run (default: random each time)"
    )
    return parser.parse_args()


def random_color():
    return (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))


def pick_camera():
    return random.choice(CAMERAS)


def build_exif_bytes(date_str=None, make=None, model=None):
    """
    Hand-build a minimal raw EXIF (TIFF) blob byte-by-byte with struct,
    rather than using Pillow's higher-level Image.Exif()/get_ifd() class.

    That higher-level API's sub-IFD offset handling has behaved
    inconsistently across Pillow versions in practice -- files can save
    without error but come back with no readable EXIF at all. Building
    the bytes directly avoids depending on that machinery; the only thing
    relied on here is JPEG save(..., exif=<raw bytes>), which is old and
    stable, plus the standard TIFF/EXIF byte layout, which isn't going to
    change.

    Layout: "Exif\\x00\\x00" marker + little-endian TIFF header + IFD0
    (Make/Model, plus a pointer to the Exif sub-IFD if there's a date) +
    Exif sub-IFD (DateTimeOriginal).
    """
    def ascii_field(text):
        return text.encode('ascii') + b'\x00'

    ifd0_fields = []
    if make:
        ifd0_fields.append((271, ascii_field(make)))   # Make
    if model:
        ifd0_fields.append((272, ascii_field(model)))  # Model

    exif_fields = []
    if date_str:
        exif_fields.append((36867, ascii_field(date_str)))  # DateTimeOriginal

    # +1 entry in IFD0 for the ExifOffset pointer, only if we actually have
    # an Exif sub-IFD to point to.
    n0 = len(ifd0_fields) + (1 if exif_fields else 0)
    ifd0_size = 2 + 12 * n0 + 4
    ifd0_offset = 8  # right after the 8-byte TIFF header
    cursor = ifd0_offset + ifd0_size

    ifd0_extra = bytearray()
    ifd0_entries = []
    for tag, val in ifd0_fields:
        count = len(val)
        if count <= 4:
            value_field = val + b'\x00' * (4 - count)
        else:
            value_field = struct.pack('<I', cursor)
            ifd0_extra += val
            cursor += count
        ifd0_entries.append((tag, 2, count, value_field))  # type 2 = ASCII

    exif_ifd_offset = cursor
    exif_ifd_size = 2 + 12 * len(exif_fields) + 4
    cursor2 = exif_ifd_offset + exif_ifd_size

    exif_extra = bytearray()
    exif_entries = []
    for tag, val in exif_fields:
        count = len(val)
        if count <= 4:
            value_field = val + b'\x00' * (4 - count)
        else:
            value_field = struct.pack('<I', cursor2)
            exif_extra += val
            cursor2 += count
        exif_entries.append((tag, 2, count, value_field))

    if exif_fields:
        ifd0_entries.append((0x8769, 4, 1, struct.pack('<I', exif_ifd_offset)))  # ExifOffset, type 4 = LONG

    ifd0_entries.sort(key=lambda e: e[0])   # TIFF requires tags sorted ascending within an IFD
    exif_entries.sort(key=lambda e: e[0])

    out = bytearray()
    out += b'Exif\x00\x00'
    out += b'II' + struct.pack('<H', 42) + struct.pack('<I', ifd0_offset)

    out += struct.pack('<H', len(ifd0_entries))
    for tag, typ, count, value_field in ifd0_entries:
        out += struct.pack('<HHI', tag, typ, count) + value_field
    out += struct.pack('<I', 0)  # no next IFD
    out += ifd0_extra

    if exif_fields:
        out += struct.pack('<H', len(exif_entries))
        for tag, typ, count, value_field in exif_entries:
            out += struct.pack('<HHI', tag, typ, count) + value_field
        out += struct.pack('<I', 0)
        out += exif_extra

    return bytes(out)


def make_image(path, exif_date=None):
    """
    Create a tiny JPEG at `path`. If exif_date is given, write it as
    DateTimeOriginal (plus a random camera make/model); if None, the
    image is saved with no EXIF data at all.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new('RGB', (20, 20), color=random_color())

    if exif_date is None:
        img.save(path, "jpeg")
        return

    make, model = pick_camera()
    exif_bytes = build_exif_bytes(
        date_str=exif_date.strftime("%Y:%m:%d %H:%M:%S"),
        make=make,
        model=model,
    )
    img.save(path, "jpeg", exif=exif_bytes)


def make_junk_video(path):
    """Create a file with a video extension but no real video content inside."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'wb') as f:
        f.write(random.randbytes(200))


def random_subfolder(root):
    return root / random.choice(SUBFOLDERS)


def generate_category(root, category, filename_prefix, count, exif_date_fn):
    """Generate `count` images for one scenario category, scattered across folders."""
    created = []
    for i in range(1, count + 1):
        folder = random_subfolder(root)
        filename = f"{filename_prefix}_{i:04d}.jpg"
        path = folder / filename
        exif_date = exif_date_fn() if exif_date_fn else None
        make_image(path, exif_date=exif_date)
        created.append(path)
    print(f"  {category:12s} {count:4d} file(s) -> e.g. {created[0].relative_to(root)}")
    return created


def main():
    args = parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    root = Path(args.output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)

    now = datetime.now()

    # Roughly split the requested count across the four scenarios.
    n_match = round(args.count * 0.30)
    n_mismatch = round(args.count * 0.38)
    n_no_exif = round(args.count * 0.25)
    n_implausible = args.count - n_match - n_mismatch - n_no_exif  # remainder, ~7%

    print(f"Generating test data in: {root}")
    print("-" * 60)

    match_files = generate_category(
        root, "match", "match", n_match,
        lambda: now - timedelta(minutes=random.randint(0, 30))
    )

    generate_category(
        root, "mismatch", "mismatch", n_mismatch,
        lambda: now - timedelta(days=random.randint(30, 1000))
    )

    generate_category(
        root, "no_exif", "noexif", n_no_exif,
        None
    )

    def implausible_date():
        if random.random() < 0.5:
            # Before cameras existed
            return EARLIEST_PLAUSIBLE_DATE - timedelta(days=random.randint(30, 20000))
        else:
            # In the future
            return now + timedelta(days=random.randint(30, 500))

    generate_category(
        root, "implausible", "implausible", n_implausible,
        implausible_date
    )

    # Duplicate set: take a few 'match' files and copy them (same filename,
    # identical bytes) into several backup-style folders, so Duplicate
    # Finder has real cross-folder duplicates to find.
    dup_originals = random.sample(match_files, min(args.duplicate_sets, len(match_files)))
    dup_count = 0
    for original in dup_originals:
        for backup_folder in DUPLICATE_FOLDERS:
            dest_dir = root / backup_folder
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / original.name
            dest.write_bytes(original.read_bytes())
            dup_count += 1
    print(f"  {'duplicates':12s} {dup_count:4d} file(s) -> {len(dup_originals)} original(s) x "
          f"{len(DUPLICATE_FOLDERS)} backup folder(s)")

    # Junk video files: exercise Importer's handling of files it can't read
    # EXIF from at all (Image.open() will raise, same as any unreadable file).
    for i in range(1, args.junk_videos + 1):
        folder = random_subfolder(root)
        make_junk_video(folder / f"junk_video_{i:04d}.mp4")
    print(f"  {'junk video':12s} {args.junk_videos:4d} file(s) -> unreadable .mp4 placeholders")

    total = n_match + n_mismatch + n_no_exif + n_implausible + dup_count + args.junk_videos
    print("-" * 60)
    print(f"Total files generated: {total}")
    print()
    print("Expected behavior when you run this through ChronoVault:")
    print(f"  match        -> confidence ~100, normal YYYY/MM/DD folder")
    print(f"  mismatch     -> confidence ~70,  normal YYYY/MM/DD folder (flagged less certain)")
    print(f"  no_exif      -> confidence 30,   routed to _review_needed/")
    print(f"  implausible  -> confidence ~5,   routed to _review_needed/")
    print(f"  duplicates   -> should be found and grouped by Duplicate Finder")
    print(f"  junk video   -> no EXIF readable, behaves like a no_exif file "
          f"(excluded if require_exif=true)")
    print()
    print(f"Point Indexer at: {root}")


if __name__ == "__main__":
    main()
    