# test_functions

Throwaway verification and debugging scripts — not permanent ChronoVault tools, and not part of the core pipeline. Each one exists to answer a specific "does this actually work?" question quickly, without running the full `chronovault.sh` sequence or writing one-off terminal commands by hand each time.

All of them are meant to be run from the `ChronoVault/` project root:
```
python3 test_functions/<script_name>.py
```

## `test_env.py`

Checks that every dependency the current tools actually need is installed and reachable — Python version, Pillow, NumPy, OpenCV, the Tesseract binary and its language packs, pytesseract, write permissions, and database integrity if `located_files.db`/`archive_database.db` already exist. Run this first on a new machine, or whenever something mysteriously doesn't work, instead of chasing dependency issues by hand.

## `test_retrieve_data.py`

Confirms `retrieve_data.py`'s two read-only functions (`list_review_items`, `get_file_details`) work against your real archive, and — the actual point of that module's design — that the results genuinely serialize to JSON with no errors.

## `test_write_data.py`

Applies real corrections to a few review-bucket files, then compares a fresh Audit Archive report taken immediately before and after, so you can see exactly what changed. Checks for an existing `audit_result.json` first and refuses to proceed without one, since there's nothing meaningful to compare against otherwise.

## `test_ocr_date.py`

Runs OCR corner-stamp detection (`analyze_date/image_tools/ocr_tools.py`) against every image in an `OCR_test_images/` folder you provide, showing the raw OCR text and confidence for every corner/rotation/preprocessing-variant combination tried — not just the final answer. Also saves every crop actually fed to OCR to `OCR_test_images/_debug_crops/`, which is the single most useful thing to look at when OCR is reading pure garbage: is the crop even landing on the stamp at all?

Originally pointed at a standalone `ocr_date/` folder; now imports from `analyze_date/image_tools/ocr_tools.py` after that migration.

## `test_analyze_date.py`

Shows what `analyze_date()` resolves for one file at a time — chosen date, source, confidence, and reasoning — without running the whole Importer pipeline. Supports `--type` to override extension-based file-type detection, and `--try-ocr` to opt in to OCR scanning for that one file. This is a debugging convenience only — it does **not** mean `analyze_date` itself has become a terminal app; it stays a library, called by Importer exactly the same way regardless of this script existing.

## A Note on What's Missing

There's currently no test script for the two remaining `analyze_date` signal sources with no real implementation yet — `audio_tools/` and `video_tools/` are still empty placeholders (see their own READMEs), so there's nothing to test there yet. A future `test_id3_tools.py` or similar would follow the same pattern as everything here once that code exists.
