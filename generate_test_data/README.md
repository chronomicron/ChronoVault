# generate_test_data

`generate_test_data.py` builds a realistic, messy fixture tree for exercising Indexer → Classify Media → Condition Database → Importer → Audit Archive → Duplicate Finder without using real personal media. The bulk date-analysis JPEGs are tiny and fast; the optional classification fixtures use larger, more realistic dimensions and include TIFF, BMP, GIF, PNG, THM, unusual, mislabeled, and corrupt inputs.

The generator covers EXIF, GPS, XMP, filename, folder-name, and filesystem date behavior. It does not generate a native TIFF `DateTime` fixture or an OCR date-stamp fixture, so it does not cover every `analyze_date` signal. It also has no `--other-format-samples` option and creates no real camera RAW file.

## Usage

```
python3 generate_test_data/generate_test_data.py
python3 generate_test_data/generate_test_data.py --output-dir test_data --count 256
python3 generate_test_data/generate_test_data.py --seed 42
```

| Option | Default | Description |
|---|:---:|---|
| `--output-dir` | `test_data` | Folder to generate files into. |
| `--count` | `256` | Approximate number of *base* JPEG images (the 4 EXIF-only scenarios below). |
| `--duplicate-sets` | `5` | How many `match` files get duplicated into backup folders. |
| `--junk-videos` | `5` | How many fake unreadable `.mp4` files. |
| `--metadata-samples` | `3` | How many of each GPS/XMP scenario (7 scenarios total). |
| `--euro-date-samples` | `3` | How many filename-only, day-first (European-style) date files, no EXIF at all. |
| `--hidden-samples` | `5` | How many files placed in **each** dot-prefixed hidden folder (there are 2 such folders — see below). |
| `--french-month-samples` | `3` | How many filename-only, no-EXIF files placed inside a French month-name folder (`Old_Backup_1/février 2022`). |
| `--classification-samples` | `1` | How many copies of each media-classification fixture family to generate; `0` omits these fixtures. |
| `--seed` | *(random)* | Stabilizes pseudo-random choices. Timestamps are still based on the current time, so separate seeded runs are not byte-for-byte identical. |

## Scenarios Generated

**Base JPEG, EXIF DateTimeOriginal only** (`--count`-scaled):

| Category | Roughly | Expected result |
|---|:---:|---|
| `match` | 30% | EXIF near filesystem time; normally high confidence and a dated folder. |
| `mismatch` | 38% | Past EXIF date disagrees with filesystem time; normally still dateable, but confidence can fall below 50 if another signal also disagrees. |
| `no_exif` | 25% | Filesystem-only unless a randomly selected containing folder supplies a date; normally routed to `_review_needed/`. |
| `implausible` | 7% | EXIF before the plausibility cutoff or in the future; chosen implausible dates are capped at confidence 5. |

Because files are scattered randomly across `SUBFOLDERS`, some land under `Phone_Backup/2025` or `Phone_Backup/2026`. Those names are active `path_folder_pattern` signals and may add an agreement bonus or mismatch penalty. The confidence values below are therefore expected primaries/rough outcomes, not exact assertions for every generated file.

**GPS and XMP scenarios** (`--metadata-samples` of each):

| Category | Expected result |
|---|---|
| `gps_agree` | `source=exif_gps`; GPS and EXIF confirm each other. |
| `gps_disagree` | `source=exif_gps` still wins despite EXIF disagreeing (simulated bad camera clock) |
| `gps_only` | `source=exif_gps`, with no EXIF capture date. |
| `xmp_agree` | `source=exif_original`, confirmed by XMP CreateDate |
| `xmp_disagree` | `source=exif_original` still wins despite XMP disagreeing (simulated later reprocessing) |
| `xmp_only` | `source=xmp_create_date`, with no EXIF capture date. |
| `xmp_modify_only` | Usually `source=filesystem_fallback`, which outranks `xmp_modify_date`; a dated containing folder can instead become primary. Normally routed to `_review_needed/`. |

**Filename-date and hidden-folder scenarios** (fixed sample counts, not scaled by `--count`):

| Category | Count | Expected result |
|---|:---:|---|
| `euro_date` | `--euro-date-samples` | **No EXIF/GPS/XMP at all** — filename is `euro_DD-MM-YYYY.jpg` with `DD` forced to 13–28, so it's unambiguously day-first (a month can never be 13–28). `source=filename_pattern`; check `date_taken`'s day/month against the filename with `test_analyze_date.py` to confirm `analyze_filename.py`'s day-first (DMY) branch parsed it correctly, rather than misreading it as month-first. Often lands in `_review_needed/` since the filename date and "now" (the filesystem fallback) rarely agree within `mismatch_threshold_days` — that's expected, not a bug; this category is about verifying the *parsed date itself*, not where it gets filed. |
| `hidden` | `--hidden-samples` × 2 folders | Same evidence as `match` (confidence ~100) — the point isn't the date, it's the **location**. Placed in two dot-prefixed folders: `.hidden_root_backup/` (directly under the search root) and `Old_Backup_2/.hidden_nested/` (nested inside an otherwise-normal folder, to confirm Indexer's walk recurses *past* a normal folder into a hidden one, not just spots one sitting in plain sight). If these don't show up in `located_files.db` after an Indexer run, `Path.rglob` is not walking into dot-prefixed folders and Indexer needs a real fix — not just a doc update. |
| `french_month` | `--french-month-samples` | **No EXIF at all** — placed inside `Old_Backup_1/février 2022/`, a real, accented French month-name folder. `source=path_folder_pattern`; the folder date usually disagrees with "now" (the filesystem fallback) by more than `mismatch_threshold_days`, so confidence often lands below the base 40 — same caveat as `euro_date`. What matters here is `date_taken`'s **month** coming out as February, confirming `analyze_folder.py`'s French `MONTH_NAMES` actually matched an accented folder name rather than silently failing to match at all (a real bug found and fixed while adding this — see `multi_tools/README.md`). |
| `archives` | 2 (fixed) | Two **real** archives, built from already-generated `match` files (not placeholder files with the right extension) — `Archives/old_photos_backup.zip` (3 photos inside) and `Archives/old_photos_backup.tar.gz` (2 different photos inside, non-overlapping with the zip). Exercises Indexer's archive detection (always on) and opt-in content-listing (`look_inside_archives: true`) — see `indexer/README.md`. Confirmed directly: both archives are detected regardless of the flag, and with it on, the exact filenames inside each are correctly listed in `located_archives.matching_files`, with neither archive's contents ever extracted. |

**Plus:** duplicate sets (`match` files copied byte-for-byte into 3 backup folders) and junk `.mp4` files (garbage bytes, exercises Importer's unreadable-file handling).

### Media-classification fixtures

Each `--classification-samples` copy adds explicit cases for `classify_media`, rather than relying on the deliberately tiny date-analysis JPEGs:

| Fixture family | Files included | Why it exists |
|---|---|---|
| Personal-photo positives | Full-size camera-EXIF JPEG, small EXIF-retaining shared copy, metadata-stripped full-size export | Ensures EXIF, camera filenames, dimensions, and stripped photos are weighed together conservatively. |
| Scans | 300-DPI color TIFF and 300-DPI grayscale TIFF | A scan has no camera EXIF but is still personal media worth archiving. |
| Clear web assets | 64×64 palette favicon, palette GIF logo, transparent button overlay under web-like paths | Expected strong negatives for the web/graphic classifier. |
| Ambiguous and unusual inputs | Medium grayscale BMP, CMYK JPEG, PNG bytes saved with a `.jpg` extension, JPEG-formatted `.thm`, truncated JPEG | Confirms nonstandard or corrupt input is classified safely rather than crashing. |

These files live under `Classification/`, visibly separate from the date-analysis scenarios. The generated default dataset therefore exercises both kinds of work: fast, tiny JPEGs for date scoring and a small number of realistic larger files for media classification.

### Totals

With all defaults (`--count 256`, `--duplicate-sets 5`, `--junk-videos 5`, `--metadata-samples 3`, `--euro-date-samples 3`, `--hidden-samples 5`, `--french-month-samples 3`, `--classification-samples 1`): 256 base + 15 duplicate copies + 5 junk + 21 (7 metadata scenarios × 3) + 3 (euro_date) + 10 (hidden, 5 × 2 folders) + 3 (french_month) + 13 classification fixtures + 2 (archives) = **328 files total**. `--count` only ever scales the 4 base categories — everything else is a fixed multiple of its own sample-count argument (`archives` is always exactly 2, not currently configurable via a CLI flag).

## How EXIF (and XMP) Are Written

JPEG EXIF is written using a hand-rolled, minimal EXIF (TIFF) byte builder (`build_exif_bytes()`), not Pillow's higher-level `Image.Exif()`/`get_ifd()` class. That higher-level API's handling of sub-IFDs (where `DateTimeOriginal` and GPS data actually live) behaved inconsistently across Pillow versions in real testing — files saved without any error, but came back with no EXIF readable at all on some installs. The hand-rolled version only depends on the plain `img.save(path, "jpeg", exif=<raw bytes>)` call, stable in Pillow for well over a decade.

**XMP** uses Pillow's plain `xmp=<bytes>` save parameter — confirmed reliable (no sub-IFD offset math involved at all, just an opaque byte blob Pillow embeds directly).

If a whole batch of `match`/`mismatch`/`gps_*`/`xmp_*` files ever comes back with no metadata readable (all landing in `_review_needed/` when they shouldn't), that's the exact symptom the hand-rolled EXIF builder was built to avoid — worth checking first if it ever resurfaces.

## Filesystem Dates Are Effectively "Now"

`analyze_date`'s filesystem-fallback signal reads a file's `ctime`, and on Linux there's no reliable way to backdate that — `os.utime()` only controls `mtime`/`atime`. Every file this script generates has a filesystem date of whenever the script actually ran, regardless of what EXIF/GPS/XMP date was written into it, or what date is embedded in an `euro_date` filename. This doesn't limit test coverage: since the embedded/filename dates are fully controllable, varying them against "now" already exercises every confidence scenario without needing to control the filesystem side at all.

## Regenerating and Safety

The output folder is meant to be disposable and not committed. The script creates the directory if needed and overwrites same-named generated files, but it does **not** clean the directory first; stale or unrelated files already there remain in place and can make observed totals exceed the printed total. Use a dedicated disposable directory and clean it separately when a truly fresh fixture set is required. When run through `chronovault.sh`, output belongs under the contained `chronovault_test/` tree.

The script writes only beneath `--output-dir`. It requires Python 3 with Pillow; ZIP and TAR creation use the standard library.

## Known Gaps / Future Additions

- **RAW-camera scenarios** (CR2/ARW/DNG) still need real fixture files or a format-aware test strategy; empty files with a raw extension would only test error handling, not metadata extraction.
- **Valid MP4/MOV fixtures** are intentionally deferred. The existing junk-video files cover corrupt-input handling only; future video-date/classification work needs genuine containers with known metadata.
