# image_tools

Every image-format evidence-gathering function `analyze_date` uses lives here, one file per source. All five contain implemented code; this is not a placeholder folder like `audio_tools/` or `video_tools/`.

None of these are meant to be imported directly by anything outside `analyze_date` — `analyze_date.py`'s `gather_signals()` is the single place that decides which of these to call for a given file, and combines whatever they find. See `analyze_date/README.md` for the full dispatch table and confidence scoring.

## `exif_tools.py`

`get_photo_date_from_exif(readable_exif)` — pulls `DateTimeOriginal` or `DateTimeDigitized` out of an already-parsed EXIF dict. Doesn't read files itself; takes the dict Importer already built.

## `gps_tools.py`

`get_gps_datetime(readable_exif)` — pulls a date/time from EXIF's `GPSDateStamp`/`GPSTimeStamp`. Independently verified against satellite time, not the camera's own clock — the highest-confidence signal currently implemented (98).

## `xmp_tools.py`

`get_xmp_datetime(file_path)` — reads `xmp:CreateDate`, `photoshop:DateCreated`, or `xmp:ModifyDate` from a JPEG's embedded XMP packet (Photoshop, Lightroom, etc.). The parser searches namespaced XML elements containing text; it does not read the common RDF form where these values are attributes on `rdf:Description`. Uses `xml.etree.ElementTree` rather than Pillow's `getxmp()` convenience method; see the module docstring for the rationale.

## `tiff_tools.py`

`get_tiff_datetime(file_path)` — reads TIFF's own baseline `DateTime` tag (306), via `getexif()` rather than `_getexif()` (which doesn't exist on TIFF images at all — confirmed directly, not assumed).

## `ocr_tools.py`

`find_date_in_corners(file_path, debug_dir=None)` — scans image corners for a printed/imprinted date, for photos with weak or no other evidence. By far the largest and most heavily-iterated module here: wide-but-short crop geometry, rotation checking, Otsu preprocessing, confidence-aware acceptance, and a punctuation-aware confidence threshold were all found necessary through extensive real-world testing, not designed upfront. **Deliberately opt-in** (`try_ocr=True` in `analyze_date`'s evidence dict) — never runs automatically. See this file's own docstring and `analyze_date/README.md`'s "OCR Is Opt-In" section for the full design history and known limitations (Japanese/kanji stamps and dot-matrix CCTV fonts are both still genuinely unsolved).

Originally a separate top-level `ocr_date/` folder; migrated here once the `image_tools/` split happened. If an old `ocr_date/` folder still exists in your project, it's superseded — safe to delete.

OCR requires Pillow plus Tesseract, `pytesseract`, OpenCV, and NumPy. The latter three Python packages are imported only when OCR runs, so they are not dependencies for the other extractors.

## Common Pattern

The metadata extractors take either a pre-parsed EXIF dict or a file path and return `None` (or `(None, None)`) when no usable metadata is found. OCR instead returns a detailed result dictionary containing the accepted match and every attempted crop. It can raise when the image cannot be opened or when an optional OCR dependency or the Tesseract executable is unavailable.
