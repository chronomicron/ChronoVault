# generate_test_data

`generate_test_data.py` builds a realistic, messy folder tree of small fake files for testing ChronoVault end-to-end — Indexer → Importer → Audit Archive → Duplicate Finder, and every signal source `analyze_date` currently supports — without needing real photos. Every file is tiny, so a full run copies fast, but each one is deliberately built to land in a specific confidence scenario.

**Documentation correction:** an earlier version of this README described TIFF, BMP, RAW-stub, and THM sidecar scenarios plus an `--other-format-samples` argument. None of that exists in the actual script — no such generation code or argument is present. This README now describes only what the code actually does. Whether those formats are still wanted as a future addition is an open question, not something silently dropped by this correction.

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
| `--seed` | *(random)* | Pass a number for a reproducible run. |

## Scenarios Generated

**Base JPEG, EXIF DateTimeOriginal only** (`--count`-scaled):

| Category | Roughly | Expected result |
|---|:---:|---|
| `match` | 30% | confidence ~100, normal `YYYY/MM/DD` folder |
| `mismatch` | 38% | confidence ~70, still dated, flagged less certain |
| `no_exif` | 25% | confidence 30 → `_review_needed/` |
| `implausible` | 7% | confidence ~5 → `_review_needed/` |

**GPS and XMP scenarios** (`--metadata-samples` of each):

| Category | Expected result |
|---|---|
| `gps_agree` | `source=exif_gps`, confidence ~100+ (GPS + EXIF confirm each other) |
| `gps_disagree` | `source=exif_gps` still wins despite EXIF disagreeing (simulated bad camera clock) |
| `gps_only` | `source=exif_gps`, no EXIF date present at all |
| `xmp_agree` | `source=exif_original`, confirmed by XMP CreateDate |
| `xmp_disagree` | `source=exif_original` still wins despite XMP disagreeing (simulated later reprocessing) |
| `xmp_only` | `source=xmp_create_date`, confidence ~80, no EXIF at all |
| `xmp_modify_only` | `source=filesystem_fallback` (its base confidence, 30, outranks `xmp_modify_date`'s 20) — low confidence, → `_review_needed/` |

**Filename-date and hidden-folder scenarios** (fixed sample counts, not scaled by `--count`):

| Category | Count | Expected result |
|---|:---:|---|
| `euro_date` | `--euro-date-samples` | **No EXIF/GPS/XMP at all** — filename is `euro_DD-MM-YYYY.jpg` with `DD` forced to 13–28, so it's unambiguously day-first (a month can never be 13–28). `source=filename_pattern`; check `date_taken`'s day/month against the filename with `test_analyze_date.py` to confirm `analyze_filename.py`'s day-first (DMY) branch parsed it correctly, rather than misreading it as month-first. Often lands in `_review_needed/` since the filename date and "now" (the filesystem fallback) rarely agree within `mismatch_threshold_days` — that's expected, not a bug; this category is about verifying the *parsed date itself*, not where it gets filed. |
| `hidden` | `--hidden-samples` × 2 folders | Same evidence as `match` (confidence ~100) — the point isn't the date, it's the **location**. Placed in two dot-prefixed folders: `.hidden_root_backup/` (directly under the search root) and `Old_Backup_2/.hidden_nested/` (nested inside an otherwise-normal folder, to confirm Indexer's walk recurses *past* a normal folder into a hidden one, not just spots one sitting in plain sight). If these don't show up in `located_files.db` after an Indexer run, `Path.rglob` is not walking into dot-prefixed folders and Indexer needs a real fix — not just a doc update. |

**Plus:** duplicate sets (`match` files copied byte-for-byte into 3 backup folders) and junk `.mp4` files (garbage bytes, exercises Importer's unreadable-file handling).

### Totals

With all defaults (`--count 256`, `--duplicate-sets 5`, `--junk-videos 5`, `--metadata-samples 3`, `--euro-date-samples 3`, `--hidden-samples 5`): 256 base + 15 duplicate copies + 5 junk + 21 (7 metadata scenarios × 3) + 3 (euro_date) + 10 (hidden, 5 × 2 folders) = **310 files total**. `--count` only ever scales the 4 base categories — everything else is a fixed multiple of its own sample-count argument.

## How EXIF (and XMP) Are Written

JPEG EXIF is written using a hand-rolled, minimal EXIF (TIFF) byte builder (`build_exif_bytes()`), not Pillow's higher-level `Image.Exif()`/`get_ifd()` class. That higher-level API's handling of sub-IFDs (where `DateTimeOriginal` and GPS data actually live) behaved inconsistently across Pillow versions in real testing — files saved without any error, but came back with no EXIF readable at all on some installs. The hand-rolled version only depends on the plain `img.save(path, "jpeg", exif=<raw bytes>)` call, stable in Pillow for well over a decade.

**XMP** uses Pillow's plain `xmp=<bytes>` save parameter — confirmed reliable (no sub-IFD offset math involved at all, just an opaque byte blob Pillow embeds directly).

If a whole batch of `match`/`mismatch`/`gps_*`/`xmp_*` files ever comes back with no metadata readable (all landing in `_review_needed/` when they shouldn't), that's the exact symptom the hand-rolled EXIF builder was built to avoid — worth checking first if it ever resurfaces.

## Filesystem Dates Are Effectively "Now"

`analyze_date`'s filesystem-fallback signal reads a file's `ctime`, and on Linux there's no reliable way to backdate that — `os.utime()` only controls `mtime`/`atime`. Every file this script generates has a filesystem date of whenever the script actually ran, regardless of what EXIF/GPS/XMP date was written into it, or what date is embedded in an `euro_date` filename. This doesn't limit test coverage: since the embedded/filename dates are fully controllable, varying them against "now" already exercises every confidence scenario without needing to control the filesystem side at all.

## Regenerating

The output folder is meant to be thrown away and rebuilt on demand — not committed to git. When run via `chronovault.sh`, it's generated inside `chronovault_test/`, which is already gitignored as a whole folder.

## Known Gaps / Future Additions

- **TIFF, BMP, RAW-stub, and THM sidecar scenarios** were previously documented here but don't currently exist in the code — worth deciding whether to actually build them or leave this script focused on JPEG-family scenarios only.
- **French-language month-name folders** (e.g. `mars 2024`), to exercise `analyze_folder.py`'s planned French `MONTH_NAMES` support once that's built — tracked in `roadmap.md`, not yet added here.
