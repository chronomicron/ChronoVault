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
        "--metadata-samples", type=int, default=3,
        help="How many of each GPS/XMP category to generate (default: 3)"
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


def build_exif_bytes(date_str=None, make=None, model=None, gps_date_str=None, gps_time_tuple=None):
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
    (Make/Model, plus pointers to whichever sub-IFDs are present) + Exif
    sub-IFD (DateTimeOriginal) + GPS sub-IFD (GPSDateStamp, GPSTimeStamp).

    gps_time_tuple is (hour, minute, second) as plain integers -- written
    as EXIF RATIONAL values (numerator/denominator pairs, denominator 1),
    which is the type GPSTimeStamp requires.
    """
    def ascii_field(text):
        return text.encode('ascii') + b'\x00'

    def rational(numerator, denominator=1):
        return struct.pack('<II', numerator, denominator)

    ifd0_fields = []
    if make:
        ifd0_fields.append((271, 2, ascii_field(make)))   # Make
    if model:
        ifd0_fields.append((272, 2, ascii_field(model)))  # Model

    exif_fields = []
    if date_str:
        exif_fields.append((36867, 2, ascii_field(date_str)))  # DateTimeOriginal

    gps_fields = []
    if gps_date_str:
        gps_fields.append((29, 2, ascii_field(gps_date_str)))  # GPSDateStamp, ASCII
    if gps_time_tuple:
        hour, minute, second = gps_time_tuple
        gps_time_value = rational(hour) + rational(minute) + rational(second)
        gps_fields.append((7, 5, gps_time_value))  # GPSTimeStamp, type 5 = RATIONAL, 3 values

    # +1 entry in IFD0 for each sub-IFD pointer actually needed (ExifOffset, GPSInfo).
    n0 = len(ifd0_fields) + (1 if exif_fields else 0) + (1 if gps_fields else 0)
    ifd0_size = 2 + 12 * n0 + 4
    ifd0_offset = 8  # right after the 8-byte TIFF header
    cursor = ifd0_offset + ifd0_size

    def layout_fields(fields, cursor):
        """Lay out a list of (tag, type, value_bytes) into TIFF entries, external data if needed."""
        entries = []
        extra = bytearray()
        for tag, typ, val in fields:
            count = len(val) if typ == 2 else (len(val) // 8)  # ASCII: byte count; RATIONAL: 8 bytes/value
            if typ == 2 and count <= 4:
                value_field = val + b'\x00' * (4 - count)
            else:
                # RATIONAL is always >4 bytes, and any ASCII field over 4
                # bytes -- both always go to external "extra" data.
                value_field = struct.pack('<I', cursor)
                extra += val
                cursor += len(val)
            entries.append((tag, typ, count, value_field))
        return entries, extra, cursor

    ifd0_entries, ifd0_extra, cursor = layout_fields(ifd0_fields, cursor)

    exif_entries, exif_extra = [], bytearray()
    if exif_fields:
        exif_ifd_offset = cursor
        exif_ifd_size = 2 + 12 * len(exif_fields) + 4
        cursor = exif_ifd_offset + exif_ifd_size
        exif_entries, exif_extra, cursor = layout_fields(exif_fields, cursor)
        ifd0_entries.append((0x8769, 4, 1, struct.pack('<I', exif_ifd_offset)))  # ExifOffset, type 4 = LONG

    gps_entries, gps_extra = [], bytearray()
    if gps_fields:
        gps_ifd_offset = cursor
        gps_ifd_size = 2 + 12 * len(gps_fields) + 4
        cursor = gps_ifd_offset + gps_ifd_size
        gps_entries, gps_extra, cursor = layout_fields(gps_fields, cursor)
        ifd0_entries.append((0x8825, 4, 1, struct.pack('<I', gps_ifd_offset)))  # GPSInfo pointer, type 4 = LONG

    ifd0_entries.sort(key=lambda e: e[0])   # TIFF requires tags sorted ascending within an IFD
    exif_entries.sort(key=lambda e: e[0])
    gps_entries.sort(key=lambda e: e[0])

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

    if gps_fields:
        out += struct.pack('<H', len(gps_entries))
        for tag, typ, count, value_field in gps_entries:
            out += struct.pack('<HHI', tag, typ, count) + value_field
        out += struct.pack('<I', 0)
        out += gps_extra

    return bytes(out)


def build_xmp_packet(create_date=None, modify_date=None):
    """
    Build a minimal, realistic XMP packet as UTF-8 bytes, suitable for
    Image.save(..., xmp=<these bytes>). ISO 8601 timestamps, no timezone
    (matching get_xmp_datetime's expectation of naive datetimes).
    """
    fields = ""
    if create_date:
        fields += f"   <xmp:CreateDate>{create_date.strftime('%Y-%m-%dT%H:%M:%S')}</xmp:CreateDate>\n"
    if modify_date:
        fields += f"   <xmp:ModifyDate>{modify_date.strftime('%Y-%m-%dT%H:%M:%S')}</xmp:ModifyDate>\n"

    packet = f'''<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/">
{fields}  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''
    return packet.encode('utf-8')


def make_image(path, exif_date=None, gps_date=None, xmp_create_date=None, xmp_modify_date=None):
    """
    Create a tiny JPEG at `path`. exif_date, if given, is written as
    DateTimeOriginal (plus a random camera make/model). gps_date, if
    given, is written as GPSDateStamp/GPSTimeStamp. xmp_create_date and
    xmp_modify_date, if given, are written into an XMP packet. Any/all of
    these can be combined, or all left None for a plain image with no
    metadata at all.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new('RGB', (20, 20), color=random_color())

    save_kwargs = {}

    if exif_date is not None or gps_date is not None:
        make, model = pick_camera()
        save_kwargs["exif"] = build_exif_bytes(
            date_str=exif_date.strftime("%Y:%m:%d %H:%M:%S") if exif_date else None,
            make=make,
            model=model,
            gps_date_str=gps_date.strftime("%Y:%m:%d") if gps_date else None,
            gps_time_tuple=(gps_date.hour, gps_date.minute, gps_date.second) if gps_date else None,
        )

    if xmp_create_date is not None or xmp_modify_date is not None:
        save_kwargs["xmp"] = build_xmp_packet(create_date=xmp_create_date, modify_date=xmp_modify_date)

    img.save(path, "jpeg", **save_kwargs)


def make_junk_video(path):
    """Create a file with a video extension but no real video content inside."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'wb') as f:
        f.write(random.randbytes(200))


def random_subfolder(root):
    return root / random.choice(SUBFOLDERS)


def generate_category(root, category, filename_prefix, count, kwargs_fn):
    """
    Generate `count` images for one scenario category, scattered across
    folders. kwargs_fn(), called once per image, returns a dict of
    make_image() keyword arguments (exif_date, gps_date, xmp_create_date,
    xmp_modify_date -- any combination) -- or None for a plain image with
    no metadata at all.
    """
    created = []
    for i in range(1, count + 1):
        folder = random_subfolder(root)
        filename = f"{filename_prefix}_{i:04d}.jpg"
        path = folder / filename
        kwargs = kwargs_fn() if kwargs_fn else {}
        make_image(path, **(kwargs or {}))
        created.append(path)
    print(f"  {category:14s} {count:4d} file(s) -> e.g. {created[0].relative_to(root)}")
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
        lambda: {"exif_date": now - timedelta(minutes=random.randint(0, 30))}
    )

    generate_category(
        root, "mismatch", "mismatch", n_mismatch,
        lambda: {"exif_date": now - timedelta(days=random.randint(30, 1000))}
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
        lambda: {"exif_date": implausible_date()}
    )

    # GPS and XMP categories -- a smaller, fixed set each, specifically to
    # exercise the exif_gps and xmp_create_date/xmp_modify_date signals in
    # analyze_date. Not scaled by --count, same reasoning as duplicates/junk
    # video below: these are targeted feature tests, not bulk volume.
    n = args.metadata_samples

    generate_category(
        root, "gps_agree", "gpsagree", n,
        lambda: {"exif_date": (d := now - timedelta(days=random.randint(1, 60))), "gps_date": d}
    )

    generate_category(
        root, "gps_disagree", "gpsdisagree", n,
        # Simulates a camera with a wrong/never-set internal clock, but a
        # correct GPS receiver -- GPS should still win as primary.
        lambda: {"exif_date": now - timedelta(days=random.randint(500, 2000)),
                  "gps_date": now - timedelta(days=random.randint(1, 10))}
    )

    generate_category(
        root, "gps_only", "gpsonly", n,
        lambda: {"gps_date": now - timedelta(days=random.randint(1, 60))}
    )

    generate_category(
        root, "xmp_agree", "xmpagree", n,
        lambda: {"exif_date": (d := now - timedelta(days=random.randint(1, 60))), "xmp_create_date": d}
    )

    generate_category(
        root, "xmp_disagree", "xmpdisagree", n,
        # Simulates a photo re-exported/reprocessed long after it was
        # taken -- EXIF should still win as primary over XMP.
        lambda: {"exif_date": now - timedelta(days=random.randint(500, 2000)),
                  "xmp_create_date": now - timedelta(days=random.randint(1, 10))}
    )

    generate_category(
        root, "xmp_only", "xmponly", n,
        lambda: {"xmp_create_date": now - timedelta(days=random.randint(1, 60))}
    )

    generate_category(
        root, "xmp_modify_only", "xmpmodifyonly", n,
        # No CreateDate at all -- only the much-weaker ModifyDate signal.
        lambda: {"xmp_modify_date": now - timedelta(days=random.randint(1, 60))}
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
    print(f"  {'duplicates':14s} {dup_count:4d} file(s) -> {len(dup_originals)} original(s) x "
          f"{len(DUPLICATE_FOLDERS)} backup folder(s)")

    # Junk video files: exercise Importer's handling of files it can't read
    # EXIF from at all (Image.open() will raise, same as any unreadable file).
    for i in range(1, args.junk_videos + 1):
        folder = random_subfolder(root)
        make_junk_video(folder / f"junk_video_{i:04d}.mp4")
    print(f"  {'junk video':14s} {args.junk_videos:4d} file(s) -> unreadable .mp4 placeholders")

    total = (n_match + n_mismatch + n_no_exif + n_implausible + dup_count + args.junk_videos
             + n * 7)
    print("-" * 60)
    print(f"Total files generated: {total}")
    print()
    print("Expected behavior when you run this through ChronoVault:")
    print(f"  match            -> confidence ~100, normal YYYY/MM/DD folder")
    print(f"  mismatch         -> confidence ~70,  normal YYYY/MM/DD folder (flagged less certain)")
    print(f"  no_exif          -> confidence 30,   routed to _review_needed/")
    print(f"  implausible      -> confidence ~5,   routed to _review_needed/")
    print(f"  gps_agree        -> confidence ~100+, source=exif_gps (GPS + EXIF confirm each other)")
    print(f"  gps_disagree     -> source=exif_gps wins despite EXIF disagreeing (bad camera clock case)")
    print(f"  gps_only         -> source=exif_gps, no EXIF date present at all")
    print(f"  xmp_agree        -> source=exif_original, confirmed by XMP CreateDate")
    print(f"  xmp_disagree     -> source=exif_original wins despite XMP disagreeing (reprocessed later)")
    print(f"  xmp_only         -> source=xmp_create_date, confidence ~80, no EXIF at all")
    print(f"  xmp_modify_only  -> source=filesystem_fallback (outranks xmp_modify_date's low confidence),")
    print(f"                      low confidence overall, routed to _review_needed/")
    print(f"  duplicates       -> should be found and grouped by Duplicate Finder")
    print(f"  junk video       -> no EXIF readable, behaves like a no_exif file "
          f"(excluded if require_exif=true)")
    print()
    print(f"Point Indexer at: {root}")


if __name__ == "__main__":
    main()
    