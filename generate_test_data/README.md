# generate_test_data

`generate_test_data.py` builds a realistic, messy folder tree of small fake files for testing ChronoVault end-to-end — Indexer → Importer → Audit Archive → Duplicate Finder, and every signal source `analyze_date` currently supports — without needing real photos. Every file is tiny, so a full run copies fast, but each one is deliberately built to land in a specific confidence scenario.

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
| `--other-format-samples` | `3` | How many of each TIFF/BMP/RAW/THM scenario (5 scenarios total). |
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

**TIFF, BMP, RAW, THM scenarios** (`--other-format-samples` of each):

| Category | Expected result |
|---|---|
| `tiff_with_date` | `source=tiff_datetime`, confidence ~65–90 |
| `tiff_no_date` | no TIFF tag written, `filesystem_fallback` only, confidence 30 |
| `bmp` | **always** `filesystem_fallback` — BMP has no metadata container of any kind, confirmed directly |
| `raw_stub` | **APPROXIMATE ONLY** — see caveat below |
| `thm_sidecar` | `source=exif_original`, confidence ~70 (JPEG-style EXIF, `.thm` extension) |

**Plus:** duplicate sets (`match` files copied byte-for-byte into 3 backup folders) and junk `.mp4` files (garbage bytes, exercises Importer's unreadable-file handling) — same as before, unchanged.

### A Real Caveat: `raw_stub` Is Not a Real RAW File

True manufacturer RAW formats (Canon `.CR2`, Nikon `.NEF`, Sony `.ARW`) have proprietary sensor-data structures Pillow cannot create. `raw_stub` actually writes a **TIFF-structured file with a `.raw` extension** — defensible because Adobe's DNG format genuinely *is* TIFF-based, but this is **not proof `analyze_date` can correctly read an actual camera RAW file**. It only tests the pipeline's handling of the extension and TIFF-style tags in isolation. Testing against real RAW files from an actual camera is still necessary before trusting this format is handled — this generator can't substitute for that.

### Totals

With all defaults (`--count 256`, `--duplicate-sets 5`, `--junk-videos 5`, `--metadata-samples 3`, `--other-format-samples 3`): 256 base + 15 duplicate copies + 5 junk + 21 (7 metadata scenarios × 3) + 15 (5 format scenarios × 3) = **312 files total**. `--count` only ever scales the 4 base categories — everything else is a fixed multiple of its own sample-count argument.

## How EXIF (and TIFF, and XMP) Are Written

JPEG EXIF is written using a hand-rolled, minimal EXIF (TIFF) byte builder (`build_exif_bytes()`), not Pillow's higher-level `Image.Exif()`/`get_ifd()` class. That higher-level API's handling of sub-IFDs (where `DateTimeOriginal` and GPS data actually live) behaved inconsistently across Pillow versions in real testing — files saved without any error, but came back with no EXIF readable at all on some installs. The hand-rolled version only depends on the plain `img.save(path, "jpeg", exif=<raw bytes>)` call, stable in Pillow for well over a decade.

**TIFF is the one exception** — `make_tiff()` *does* use `Image.Exif()` + `tiffinfo=`, verified directly to round-trip correctly through `getexif()` for the one tag actually needed (baseline `DateTime`, 306). This is a narrower, simpler use of that API than the JPEG sub-IFD case that caused problems, and was tested before being relied on.

**XMP** uses Pillow's plain `xmp=<bytes>` save parameter — confirmed reliable (no sub-IFD offset math involved at all, just an opaque byte blob Pillow embeds directly).

If a whole batch of `match`/`mismatch`/`gps_*`/`xmp_*` files ever comes back with no metadata readable (all landing in `_review_needed/` when they shouldn't), that's the exact symptom the hand-rolled EXIF builder was built to avoid — worth checking first if it ever resurfaces.

## Filesystem Dates Are Effectively "Now"

`analyze_date`'s filesystem-fallback signal reads a file's `ctime`, and on Linux there's no reliable way to backdate that — `os.utime()` only controls `mtime`/`atime`. Every file this script generates has a filesystem date of whenever the script actually ran, regardless of what EXIF/GPS/XMP/TIFF date was written into it. This doesn't limit test coverage: since the embedded dates are fully controllable, varying them against "now" already exercises every confidence scenario without needing to control the filesystem side at all.

## Regenerating

The output folder is meant to be thrown away and rebuilt on demand — not committed to git. Add it to `.gitignore` (e.g. `test_data/`) if you haven't already.
