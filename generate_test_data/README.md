# generate_test_data

`generate_test_data.py` builds a realistic, messy folder tree of small fake images for testing ChronoVault end-to-end — Indexer → Importer → Audit Archive → Duplicate Finder — without needing real photos. Every file is a tiny 20×20 pixel JPEG (a few hundred bytes), so a full run copies fast, but each one is deliberately built to land in a specific `analyze_date` confidence scenario.

## Usage

```
python3 generate_test_data/generate_test_data.py
python3 generate_test_data/generate_test_data.py --output-dir test_data --count 256
python3 generate_test_data/generate_test_data.py --seed 42
```

| Option              | Default        | Description                                                        |
|----------------------|-----------------|--------------------------------------------------------------------|
| `--output-dir`       | `test_data`     | Folder to generate files into.                                     |
| `--count`            | `256`           | Approximate number of *base* images (the four scenarios below). Duplicate copies and junk files are added on top of this, so the actual total generated will be somewhat higher — see **Totals**, below. |
| `--duplicate-sets`   | `5`             | How many `match` files get duplicated into backup folders.         |
| `--junk-videos`      | `5`             | How many fake unreadable `.mp4` files to create.                   |
| `--seed`             | *(random)*      | Pass a number for a reproducible run — same seed, same files, useful for comparing two versions of a tool against identical input. |

## Scenarios Generated

| Category      | Roughly | What it tests                                                                 | Expected result                        |
|----------------|:-------:|----------------------------------------------------------------------------------|-------------------------------------------|
| `match`        | 30%     | EXIF `DateTimeOriginal` close to "now" — agrees with the filesystem date         | confidence ~100, normal `YYYY/MM/DD` folder |
| `mismatch`     | 38%     | EXIF present but far in the past — disagrees with the filesystem date            | confidence ~70, still a `YYYY/MM/DD` folder, just flagged less certain |
| `no_exif`      | 25%     | No EXIF at all — filesystem fallback only                                        | confidence 30 → `_review_needed/`        |
| `implausible`  | 7%      | EXIF date before cameras existed, or in the future                               | confidence capped very low → `_review_needed/` |

On top of those four, two more sets get added:

- **Duplicate sets** — `--duplicate-sets` `match` files (5 by default) get copied byte-for-byte into 3 backup-style folders each, so Duplicate Finder has real cross-folder duplicates to find.
- **Junk videos** — `--junk-videos` files (5 by default) with a `.mp4` extension but garbage bytes inside, so Importer's handling of a genuinely unreadable file gets exercised (`Image.open()` fails on these exactly the way it would on a corrupt or unsupported file — no crash, just no EXIF).

Files are scattered at random across a simulated messy folder layout (`DCIM/Camera`, `Phone_Backup/2025`, `Old_Backup_1`, `Downloads`, `Screenshots`, etc.) — similar to the kind of sprawl Indexer has to crawl through on a real machine.

### Totals

`--count` only controls the four base categories, which do sum to that number. Duplicate copies and junk videos are added as fixed extras on top, so the actual file count ends up a bit higher than `--count` — with the defaults (`--count 256`, 5 duplicate sets × 3 copies, 5 junk videos), that's 256 base + 15 duplicate copies + 5 junk = **276 files total**. Worth knowing if you're eyeballing totals against what you asked for.

## How EXIF Is Written

Dates are written using a hand-rolled, minimal EXIF (TIFF) byte builder (`build_exif_bytes()`), not Pillow's higher-level `Image.Exif()`/`get_ifd()` class. That higher-level API's handling of the Exif sub-IFD (where `DateTimeOriginal` actually lives) turned out to behave inconsistently across Pillow versions in real testing — files saved without any error, but came back with no EXIF readable at all on some installs. The hand-rolled version only depends on the plain `img.save(path, "jpeg", exif=<raw bytes>)` call, which has been stable in Pillow for a very long time, so it should behave identically regardless of which Pillow version is installed. If you ever see a whole batch of `match`/`mismatch` files coming back with no EXIF (all landing at confidence 30 in `_review_needed/` when they shouldn't), that's the exact symptom this was built to avoid — worth checking first if it ever resurfaces.

## Filesystem Dates Are Effectively "Now"

`analyze_date`'s filesystem-fallback signal reads a file's `ctime`, and on Linux there's no reliable way to backdate that — `os.utime()` only controls `mtime`/`atime`. So every file this script generates will have a filesystem date of whenever the script was actually run, regardless of what EXIF date was written into it. This doesn't limit test coverage in practice: since EXIF dates are fully controllable, varying EXIF against "now" already exercises every confidence scenario (agreement, disagreement, absence, implausibility) without needing to control the filesystem side at all.

## Regenerating

The output folder is meant to be thrown away and rebuilt on demand — it isn't (and shouldn't be) committed to git. Add it to `.gitignore` (e.g. `test_data/`) if you haven't already.
