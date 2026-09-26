# ChronoVault Date Signals

This document separates the date evidence ChronoVault uses today from possible future sources. The implementation in `analyze_date/` is authoritative for current behavior; the later research catalog is planning material only.

ChronoVault's design is evidence-in, scored-result-out: small extractors produce named candidate dates, `analyze_date()` chooses and scores a result, and callers decide what to do with low-confidence output. The date analyzer does not copy, move, rename, or update files or databases.

## Current implementation

### API and dispatch

`analyze_date(evidence)` accepts:

| Key | Required | Default | Meaning |
|---|---:|---|---|
| `file_path` | yes | none | File to inspect. |
| `readable_exif` | no | `{}` | EXIF mapping already read by the caller. |
| `mismatch_threshold_days` | no | `1` | Maximum integer-day difference counted as agreement. |
| `file_type` | no | file suffix | Optional dispatch override such as `.tiff`. |
| `try_ocr` | no | `false` | Enables slow OCR for supported image types. |

The return mapping contains `date_taken`, `date_source`, `filesystem_creation_date`, `confidence`, `reason`, and `date_uncertain`.

Evidence gathering currently dispatches as follows:

- `.jpg`, `.jpeg`, and `.thm`: GPS, EXIF original/digitized, and embedded XMP.
- `.tif` and `.tiff`: the TIFF baseline `DateTime` tag. JPEG-style EXIF/GPS/XMP extraction is not also run for TIFF.
- JPEG-family and TIFF files: optional corner-stamp OCR when `try_ocr` is true.
- every file type: filename, containing-folder, and filesystem signals.
- audio and video: no format-specific metadata extractors yet; only the type-independent signals apply.

Manufacturer RAW formats are not treated as TIFF. A caller that knows a file is TIFF-compatible can explicitly pass `file_type='.tiff'`.

### Implemented sources and confidence

| Source name | Base | Extraction behavior |
|---|---:|---|
| `exif_gps` | 98 | EXIF GPS date and time from the caller-supplied EXIF mapping. |
| `exif_original` | 95 | EXIF `DateTimeOriginal`. |
| `tiff_datetime` | 90 | TIFF baseline `DateTime` tag. |
| `exif_digitized` | 85 | EXIF `DateTimeDigitized`. |
| `xmp_create_date` | 80 | Embedded XMP `CreateDate` or Photoshop `DateCreated`. |
| `filename_pattern` | 70 | A recognized date in the filename. |
| `ocr_corner_stamp` | 60 | Opt-in OCR of rotated/preprocessed image corners. |
| `path_folder_pattern` | 40 | A recognized date in a containing folder. |
| `filesystem_fallback` | 30 | `Path.stat().st_ctime`; on Linux this is inode-change time, not birth time. |
| `xmp_modify_date` | 20 | Embedded XMP `ModifyDate`, treated as weak edit-time evidence. |

The source names above are the complete current set that may be returned in `date_source`. Some source-code comments and docstrings still describe an older, smaller set.

### Filename and folder patterns

Filename parsing recognizes camera-style and general numeric dates, including forms such as `IMG_20240115_123000`, `2024-01-15`, and ambiguous year-last forms. For ambiguous month/day values it tries month-day-year before day-month-year. Years must be between 1990 and the current year plus one.

Folder parsing searches from the immediate parent outward and recognizes:

- a four-digit year;
- `YYYY-MM` and `YYYY_MM`;
- English or French month names combined with a year.

It does not currently recognize every locale or date notation; for example, Japanese year/month folder names are unsupported. A nearer matching folder wins over a more distant one.

### Scoring

1. The available signal with the highest base confidence becomes primary.
2. Each other signal whose date is within `mismatch_threshold_days` adds 5 points.
3. Each other signal outside that threshold subtracts 25 points.
4. The score is clamped to 0–100.
5. A primary date before 1972-07-26 or later than the current time is capped at 5.
6. A result below 50 sets `date_uncertain=true`.

Agreement currently compares `abs((other - primary).days)`. Because `timedelta.days` is an integer floor rather than an exact duration, the default threshold does not behave like a precise 24-hour tolerance around the primary date. This is an implementation limitation, not an intended statistical rule.

The primary signal is selected by base confidence, not by the adjusted final score. A strong signal can therefore remain the chosen date even after several disagreement penalties.

### Known interpretation limits

- GPS timestamps are UTC-like while ordinary EXIF dates are normally camera-local and timezone-free. The analyzer compares naive values without timezone reconciliation.
- XMP date strings with offsets are parsed and then made naive; the value is not converted to a common timezone first.
- The XMP reader examines XML element text. Common RDF attribute forms may not be found.
- Filesystem `st_ctime` is a weak and platform-dependent fallback.
- OCR requires Tesseract plus `pytesseract`, OpenCV, and NumPy. It is lazy-loaded and opt-in, but when enabled it is attempted even if stronger evidence already exists.
- The repository's `analyze_date/config.json` is currently a draft/reference file; `analyze_date.py` does not load it.

## Current consumers

### Condition Database

Condition Database calls the analyzer for eligible source-inventory rows and stores `date_taken`, `date_source`, `confidence`, and `date_reason` in `located_files`. Its `try_ocr` setting is passed through for all supported image rows, not only rows already known to be uncertain.

### Importer

Importer analyzes each selected source again rather than consuming Condition Database's stored decision. It stores its result in `archive_files` and routes confidence below 50 to `_review_needed/`. Importer does not enable OCR, so a row conditioned with OCR can receive a different result during import.

### Other tools

The focused scripts under `test_functions/` exercise date and OCR behavior. Audit Archive does not call this shared analyzer; its extra-file recommendation uses a separate EXIF/filesystem heuristic, so its recommendation can differ from Importer and Condition Database.

## Planned and researched signals

Everything in this section is unimplemented unless explicitly listed in the current table above.

### Still images and sidecars

Potential high-value additions include broader TIFF/EXIF traversal, IPTC Date Created, XMP RDF attributes, HEIC/HEIF, RAW formats, WebP and PNG metadata, external `.xmp` files, `.THM` pairing, and export sidecars such as Google Takeout supplemental JSON. Sidecars should be evidence for a media item rather than automatically archived as media themselves.

Capture-oriented fields should outrank edit/export fields. `xmp:ModifyDate`, PNG creation text, and similar workflow timestamps should remain weak unless corroborated.

### Audio

Possible sources include:

| Format | Candidate metadata | Caution |
|---|---|---|
| MP3 | ID3 `TDRC`; older `TYER`/`TDAT`/`TIME` | Re-encoding and messaging exports often remove or rewrite tags. |
| M4A/AAC | QuickTime `creation_time`, `©day` | May describe encoding rather than recording. |
| WAV | BWF origination date/time; LIST/INFO `ICRD` | Strong when written by a recorder. |
| FLAC/OGG | Vorbis `DATE`/`YEAR` | Free-form and workflow-dependent. |

Filename and folder evidence is often valuable for meeting recordings. A nameless recording should not be assigned a confident calendar day from filesystem time alone.

### Video

Candidates include MP4/QuickTime `mvhd`/`tkhd` creation times, `©day`, `com.apple.quicktime.creationdate`, MKV `DateUTC`, and embedded GPS. Re-exported video may carry export time rather than capture time.

### Cross-file inference

Potential signals include an identical hash already associated with a high-confidence or user-corrected archive date, paired sidecars, and carefully constrained sequence/burst inference. Visual era estimation or speech recognition should, at most, produce review suggestions rather than automatic filing decisions.

## Design guidance for future work

- Add format-specific evidence in a small extractor and register a distinct source name/base confidence; keep the generic combination logic stable.
- Preserve provenance and the unadjusted evidence so a person can understand a result.
- Normalize timezone-aware values before comparing them, without inventing a timezone for naive camera timestamps.
- Keep slow or speculative techniques opt-in and direct weak results to review.
- Prefer a shared analyzer for Condition Database, Importer, and audit recommendations so identical evidence produces consistent results.
- Consider ExifTool or format-aware libraries for broad RAW, HEIC, audio, video, Adobe, and sidecar coverage rather than assuming Pillow exposes all metadata.

No current code reads audio tags, video container dates, IPTC, external sidecars, Takeout JSON, or known-date hash twins. Those capabilities must not be described as part of the working pipeline until implemented.
