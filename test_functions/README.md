# test_functions

Throwaway verification and debugging scripts — not permanent ChronoVault tools, and not part of the core pipeline. Each one exists to answer a specific "does this actually work?" question quickly, without running the full `chronovault.sh` sequence or writing one-off terminal commands by hand each time.

Run them from the `ChronoVault/` project root unless a script's notes say otherwise. They do not share one uniform argument shape:

```text
python3 test_functions/test_env.py
python3 test_functions/test_analyze_date.py path/to/file.jpg [--type .tiff] [--try-ocr]
python3 test_functions/test_ocr_date.py
python3 test_functions/test_retrieve_data.py test_functions/test_retrieve_data_config.json
python3 test_functions/test_write_data.py
```

## `test_env.py`

Checks Python (3.8+), SQLite, Pillow, optional OCR components, optional `pycdlib`, optional PySide6, and forward-looking `ffmpeg`/ExifTool availability. It also checks project-root writability with `os.access()` and runs SQLite integrity checks only for the conventional root-level `located_files.db` and `archive/archive_database.db` paths when present. It does not inspect every tool config, custom archive location, or real write capability. Missing optional components do not cause a nonzero exit; failed required checks do.

## `test_retrieve_data.py`

Loads `archive_root` from the required JSON argument, calls `list_review_items()` and `get_file_details()`, checks a nonexistent ID, and verifies the returned list serializes to JSON. It prints diagnostics but does not use assertions or a failing exit status when the two returned records differ.

## `test_write_data.py`

**Mutating script.** Applies date corrections to as many as three real review rows, physically moving those archive files through `write_data`, then compares fresh Audit Archive summaries before and after. Use it only with disposable data. It hardcodes `ARCHIVE_ROOT = "archive"` and `audit_result.json` relative to the current working directory, but invokes Audit Archive with the repository's `audit_archive/config.json`. Those locations must describe the same archive/report context or the comparison is invalid. It also refuses to start unless an old `audit_result.json` already exists, even though it immediately generates a fresh before-report.

## `test_ocr_date.py`

Runs OCR corner-stamp detection against supported images directly inside the project-root `OCR_test_images/` directory (it does not recurse), printing every attempted crop/rotation/variant and saving debug crops under `OCR_test_images/_debug_crops/`. It requires Pillow plus the optional OCR stack and propagates OCR/dependency errors.

Originally pointed at a standalone `ocr_date/` folder; now imports from `analyze_date/image_tools/ocr_tools.py` after that migration.

## `test_analyze_date.py`

Shows what `analyze_date()` resolves for one file at a time without running the pipeline. It builds readable EXIF only for JPEG-family types, supports `--type` for dispatch override, and supports `--try-ocr`. The final "Full result" is display-oriented: every value is converted with `str()`, so it is not a type-faithful serialization of the returned dictionary.

## A Note on What's Missing

There are no formal automated tests or assertions here, and no all-tests runner in this directory. There are also no focused scripts for Classify Media, Indexer archive listing, Condition Database, Importer, Duplicate Finder, or the unimplemented audio/video metadata extractors. `chronovault.sh` provides the broader contained manual pipeline workflow.
