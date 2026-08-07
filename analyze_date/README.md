# analyze_date

`analyze_date` figures out the most likely date a media file was created, how confident it is in that date, and why. It's not a standalone tool you run from the terminal — it's a small package that other tools (currently Importer, plus the `test_functions/` debugging scripts) import and call.

## Architecture

`analyze_date.py` itself is now just the **orchestration layer** — it decides which evidence-gathering functions to call for a given file type, and combines whatever they find into one scored answer. The actual per-format extraction logic lives in `image_tools/`, one file per source:

```
analyze_date/
├── analyze_date.py       -- orchestration: dispatch, scoring, combination. No format-specific code.
├── image_tools/
│   ├── exif_tools.py      -- EXIF DateTimeOriginal / DateTimeDigitized
│   ├── gps_tools.py        -- EXIF GPSDateStamp / GPSTimeStamp
│   ├── xmp_tools.py        -- XMP CreateDate / ModifyDate (Photoshop, Lightroom, etc.)
│   ├── tiff_tools.py       -- TIFF's own baseline DateTime tag
│   └── ocr_tools.py        -- OCR corner-stamp scanning (opt-in, see below)
├── audio_tools/            -- empty placeholders, future MP3/ID3 work
└── video_tools/            -- empty placeholders, future MP4 container-metadata work
```

This split happened after the module had grown to cover five different evidence sources in one file — each one now lives in its own testable, independently-reusable module, and `analyze_date.py` only needs to know *that* a source exists and how much to trust it, not *how* it works.

## Why It's Separate From Importer

The interface is deliberately generic: hand it whatever evidence you have about a file, get back a scored, explained answer. That shape isn't specific to dates — a future AI labeling tool (people, places, things in a photo) is expected to follow the same pattern: evidence in, a scored and explained conclusion out.

## Usage

```python
from analyze_date.analyze_date import analyze_date

result = analyze_date({
    'file_path': source,              # required
    'readable_exif': readable_exif,   # dict of EXIF tags, or {} if none -- only used for JPEG-family files
    'mismatch_threshold_days': 1,     # how many days apart before two signals "disagree"
    'file_type': None,                # optional -- overrides extension-based type detection
    'try_ocr': False,                 # optional -- opt in to (slow) OCR corner-stamp scanning
})
```

Returns a dict:

```python
{
    'date_taken': datetime or None,
    'date_source': 'exif_gps' | 'exif_original' | 'exif_digitized' | 'tiff_datetime'
                    | 'xmp_create_date' | 'xmp_modify_date' | 'ocr_corner_stamp'
                    | 'filesystem_fallback' | None,
    'filesystem_creation_date': datetime or None,
    'confidence': int,      # 0-100
    'reason': str,          # short human-readable explanation
    'date_uncertain': bool, # confidence < 50, kept for convenience
}
```

## File Type Dispatch

Different file types carry date evidence in completely different places, so `gather_signals()` only calls the evidence-gathering functions relevant to the file's actual type:

| `file_type` | Signals checked |
|---|---|
| `.jpg`, `.jpeg`, `.thm` | GPS, EXIF, XMP (+ OCR, if `try_ocr=True`) |
| `.tif`, `.tiff` | TIFF's baseline DateTime tag (+ OCR, if `try_ocr=True`) |
| anything else | filesystem date only, for now |

`file_type` is inferred from the file's own extension unless explicitly overridden in the evidence dict — pass this when a caller already knows the real type and it might not match the extension (e.g. a DNG file, which is genuinely TIFF-structured, passed as `file_type='.tiff'`).

`.thm` is included with the JPEG family deliberately: Canon-style sidecar thumbnail files are structurally JPEGs with their own EXIF, often mirroring the main video's date.

**Not included:** `.raw` is deliberately *not* mapped to TIFF automatically. Adobe DNG really is TIFF-based, but Canon CR2 / Nikon NEF / Sony ARW are not, and the `.raw` extension alone doesn't tell you which one you have — guessing wrong here would be worse than not guessing. A caller that knows it's dealing with DNG specifically should pass the override explicitly.

## Strategy

Every date signal gathered for a file (from whichever `image_tools/` module found it) is treated as one entry in a list, not as a special case — the combination logic doesn't hardcode "check EXIF, then check GPS." It collects however many signals are available and combines them the same way regardless of how many there are:

1. **Pick a primary signal.** The signal with the highest base confidence becomes the date actually used.
2. **Check the others for agreement.** Any other signal within `mismatch_threshold_days` of the primary confirms it; anything further off disagrees.
3. **Adjust the score.** Confidence starts at the primary signal's base score, then gets a bonus for each agreeing signal and a penalty for each disagreeing one.
4. **Cap implausible dates.** If the resulting date is before cameras existed, or in the future, confidence is capped very low no matter what the signals said.

## Confidence Thresholds

**Base confidence, by signal source** (before any agreement/mismatch adjustment):

| Source | Base confidence | Why |
|---|:---:|---|
| `exif_gps` | 98 | From the satellite signal at capture time, not the camera's own (sometimes wrong) clock |
| `exif_original` | 95 | |
| `tiff_datetime` | 90 | TIFF's own native timestamp field |
| `exif_digitized` | 85 | |
| `xmp_create_date` | 80 | `xmp:CreateDate` or `photoshop:DateCreated` |
| `ocr_corner_stamp` | 60 | Already passed OCR's own internal confidence gate (see `ocr_tools.py`), but inherently less reliable than direct metadata |
| `filesystem_fallback` | 30 | |
| `xmp_modify_date` | 20 | Reflects a *later* edit, not original creation — a meaningfully weaker claim than CreateDate |

**Adjustments:**

| Situation | Effect |
|---|---|
| Another signal agrees (within `mismatch_threshold_days`) | **+5** per agreeing signal |
| Another signal disagrees | **−25** per disagreeing signal |
| Date is implausible (before 1972-07-26, or in the future) | capped at **5**, regardless of source or agreement |
| No date evidence at all | confidence **0** |

Confidence is always clamped to 0–100. Below **50**, `date_uncertain` is `True` — the threshold Importer uses to decide between a normal `YYYY/MM/DD` folder and `archive/_review_needed/`.

## OCR Is Opt-In, Not Automatic

`try_ocr` defaults to `False`. OCR scanning is slow — multiple corners, multiple rotations, multiple preprocessing variants per file — and only useful for exactly the files that already have weak or no other evidence. It should be triggered deliberately (a person or a future GUI choosing "look for more clues" on a specific low-confidence file), never run automatically on every import. See `image_tools/ocr_tools.py` for the full design history, setup requirements, and known limitations (confirmed via real-world testing: Japanese/kanji stamps aren't supported yet, and dot-matrix CCTV-style fonts remain genuinely hard).

## Adding a New Evidence Source

1. Write a new function in the relevant `*_tools.py` (or a new one, for a new media type), following the existing shape: take whatever raw input it needs, return `None` if nothing found.
2. Add a `BASE_CONFIDENCE` entry for it in `analyze_date.py`.
3. Add a branch to `gather_signals()`'s type dispatch that calls it and appends a signal, for whichever `file_type`(s) it applies to.

Nothing in `analyze_date()`'s actual combination logic needs to change — it already works for however many signals show up.

**Realistic future sources**, not yet implemented:
- **Filename-derived dates** — cameras/phones often bake the date into the filename (e.g. `IMG_20260720_123957.jpg`).
- **Camera sidecar files** — some cameras write per-shot metadata files beyond `.THM`.
- **ID3 tags (MP3)** and **container metadata (MP4)** — `audio_tools/` and `video_tools/` exist as empty placeholders for exactly this; genuinely new work, not a migration.

## Media Independence

The scoring engine doesn't know or care what kind of file it's dating — only `gather_signals()`'s dispatch is type-aware. This is deliberate: the eventual goal is archiving more than just photos and video (e.g. MP3 recordings of meetings), and each new media type should only need its own evidence-gathering, not its own scoring logic.

## Design History

This module has gone through several deliberate stages: a plain move of Importer's old EXIF-vs-filesystem logic into its own file; confidence scoring and the signals-list design; GPS, XMP, and TIFF support added one at a time, each tested against real and synthetic data; OCR corner-stamp detection built and iterated on extensively against real downloaded photos; and finally, once the module had grown past a single reasonable file, the split into `image_tools/` seen here. Each stage was tested before the next began.
