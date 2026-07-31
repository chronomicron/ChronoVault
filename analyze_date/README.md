# analyze_date

`analyze_date` figures out the most likely date a media file was created, how confident it is in that date, and why. It's not a standalone tool you run from the terminal — it's a small package that other tools (currently just Importer) import and call.

## Why it's separate from Importer

Working out "when was this actually taken" turned out to be its own small, self-contained problem — worth its own module rather than living inline in Importer. The interface is deliberately generic: hand it whatever evidence you have about a file, get back a scored, explained answer. That shape isn't specific to dates — a future AI labeling tool (people, places, things in a photo) is expected to follow the same pattern: evidence in, a scored and explained conclusion out. Keeping `analyze_date` separate now means Importer never needs to know *how* the date was worked out, only what to do with the answer — the same way it won't need to know how a future labeler decided what's in a photo.

## Usage

```python
from analyze_date.analyze_date import analyze_date

result = analyze_date({
    'file_path': source,              # required
    'readable_exif': readable_exif,   # dict of EXIF tags, or {} if none
    'mismatch_threshold_days': 1,     # how many days apart before two signals "disagree"
})
```

Returns a dict:

```python
{
    'date_taken': datetime or None,
    'date_source': 'exif_original' | 'exif_digitized' | 'filesystem_fallback' | None,
    'filesystem_creation_date': datetime or None,
    'confidence': int,      # 0-100
    'reason': str,          # short human-readable explanation
    'date_uncertain': bool, # confidence < 50, kept for convenience
}
```

## Strategy

Every date `analyze_date` is given (from EXIF, from the filesystem, or from anything added later) is treated as one **signal** in a list, not as a special case. The logic doesn't hardcode "check EXIF, then check filesystem" — it collects however many signals are available and combines them the same way regardless of how many there are:

1. **Pick a primary signal.** The signal with the highest base confidence (see table below) becomes the date actually used.
2. **Check the others for agreement.** Any other signal within `mismatch_threshold_days` of the primary is treated as confirming it; anything further off is treated as disagreeing.
3. **Adjust the score.** Confidence starts at the primary signal's base score, then gets a bonus for each agreeing signal and a penalty for each disagreeing one.
4. **Cap implausible dates.** If the resulting date is before cameras existed, or in the future, confidence is capped very low no matter what the signals said — agreement on an impossible date doesn't make it likely.

This is why adding a new evidence source later (see below) doesn't require rewriting the scoring — it just means one more entry can show up in the signal list, and steps 1–4 already know what to do with it.

## Confidence Thresholds

**Base confidence, by signal source** (before any agreement/mismatch adjustment):

| Source                | Base confidence |
|------------------------|:---------------:|
| `exif_original`         | 95               |
| `exif_digitized`        | 85               |
| `filesystem_fallback`   | 30               |

**Adjustments:**

| Situation                                              | Effect                          |
|----------------------------------------------------------|----------------------------------|
| Another signal agrees (within `mismatch_threshold_days`)  | **+5** per agreeing signal       |
| Another signal disagrees                                   | **−25** per disagreeing signal   |
| Date is implausible (before 1972-07-26, or in the future) | capped at **5**, regardless of source or agreement |
| No date evidence at all                                    | confidence **0**                 |

Confidence is always clamped to the 0–100 range. Below **50**, `date_uncertain` is set `True` — this is the threshold Importer currently uses to decide whether a file goes into a normal `YYYY/MM/DD` folder or into `archive/_review_needed/` instead of a guessed placement.

**Worked examples:**

| Scenario                                             | Confidence | Reason string (example)                                                         |
|-------------------------------------------------------|:----------:|-----------------------------------------------------------------------------------|
| EXIF `DateTimeOriginal`, filesystem date agrees        | 100        | `EXIF (DateTimeOriginal) -- confirmed by filesystem creation date`               |
| EXIF `DateTimeOriginal` alone, nothing to compare against | 95      | `EXIF (DateTimeOriginal)`                                                         |
| EXIF `DateTimeOriginal`, filesystem date disagrees       | 70        | `EXIF (DateTimeOriginal) -- disagrees with filesystem creation date`             |
| No EXIF at all, filesystem date only                    | 30        | `filesystem creation date`                                                        |
| Any date before 1972 or in the future                    | ≤5         | `... -- date is implausible (before cameras existed, or in the future)`          |
| No evidence at all (no EXIF, file doesn't exist)          | 0          | `No date evidence available (no EXIF, no filesystem date)`                       |

## Adding a New Evidence Source (Future Work)

Realistic future sources, not yet implemented:

- **Filename-derived dates** — many cameras and phones bake the date into the filename itself (e.g. `IMG_20260720_123957.jpg`). When EXIF is missing, this could be a much better signal than the filesystem date alone.
- **Camera sidecar files** — some cameras (Canon SLRs, for instance) write a separate `.THM` file per shot with its own embedded metadata, independent of the main file's EXIF.
- **XMP / IPTC metadata** — editors like Photoshop and Lightroom embed their own metadata (separate from EXIF), often including `CreateDate`/`ModifyDate` fields. A photo edited even once in one of these tools may carry this alongside, or instead of, usable EXIF.
- **OCR corner-stamp detection** — a working proof-of-concept already exists in `ocr_date/` (see its README), for photos with a printed/imprinted date visible in a corner (old date-stamp cameras, scanned prints). Not yet wired in here, and deliberately meant to be an opt-in "look for more clues" step rather than run automatically — it's slow, and only useful for exactly the files that already have weak or no other evidence.

Adding any of these just means:

1. Add a base confidence entry to `BASE_CONFIDENCE` (there are commented-out placeholder entries already there for the first two).
2. In `gather_signals()`, read the new source and, if a date was found, append one more entry to the `signals` list — same shape as the existing EXIF/filesystem entries.

Nothing in `analyze_date()` itself needs to change — the primary-selection and agreement/mismatch logic already works for any number of signals. In particular, if EXIF, the filesystem date, *and* the filename all agree, that's automatically worth more (three agreement bonuses instead of one) without any special-case code for "three-way agreement."

## Notes on the Filesystem Signal

`get_filesystem_creation_date()` reads `st_ctime`. On Linux this is technically the inode's last metadata-change time, not a true creation time — there's no reliable, portable way to get real file creation time on Linux. It's used here as the best available proxy, same as before this module existed. Worth knowing if a filesystem-fallback date looks surprising (e.g. "creation" date is actually whenever the file was last copied or touched, not when it was first created).

## Design History

This module didn't start with confidence scoring — the first version was a straight move of Importer's old EXIF-vs-filesystem logic into its own file, with the same binary `date_uncertain` flag it always had. Confidence scoring, the `reason` string, and the signals-list design (built to support future evidence sources without a rewrite) were added as a deliberate second step, once the plumbing was proven to work end-to-end.
