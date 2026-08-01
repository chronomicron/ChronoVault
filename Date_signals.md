# ChronoVault — Date Signals Catalog

A reference for every practical way ChronoVault can (or could) determine when media was created or recorded. This document packages research and design notes for future work on `analyze_date` and related extractors. It is **not** a claim that all of these are implemented yet.

**Related code / docs:**

- `analyze_date/` — confidence-scored combination of signals (implemented)
- `ocr_date/` — corner-stamp OCR proof of concept (not wired in)
- `Database_schema.md` — how chosen dates are stored on archive rows
- `README.md` — pipeline overview and roadmap

**Design rule (unchanged):** extract candidate datetimes as named signals → hand them to `analyze_date` → get back a scored, explained answer. Prefer **capture time** over **encode/export time** over **tag-edit time** over **filesystem time**. Low confidence still goes to `archive/_review_needed/`.

---

## 1. Big picture: where dates live

| Layer | Examples | Typical trust |
|-------|----------|---------------|
| **Camera / capture metadata** | EXIF DateTimeOriginal, GPS timestamp, QuickTime `creation_time` | High |
| **Editor / workflow metadata** | XMP CreateDate / DateTimeOriginal, IPTC, Photoshop IRB | Medium–high (sometimes “when edited”) |
| **Container headers** | MP4 `mvhd`, MKV `DateUTC`, MP3 ID3 `TDRC` | Medium (often encode/export time) |
| **Sidecars / companions** | `.xmp`, Google Takeout JSON, `.THM` | High when clearly present and matched |
| **Filename / path** | `IMG_20240115_…`, `Meeting 2024-03-12.mp3` | Medium (excellent when embedded metadata is empty) |
| **Filesystem** | ctime / mtime / birthtime | Low on Linux (inode change ≠ creation) |
| **Content inference** | visual year guess, ASR “today is Monday” | Low / experimental — suggestions only, never auto-file |

---

## 2. Currently implemented (baseline)

As of the pipeline that uses `analyze_date`:

| Signal (source name) | Base confidence | Notes |
|----------------------|:---------------:|-------|
| `exif_gps` | 98 | Satellite-derived time from EXIF GPS block; independent of camera clock |
| `exif_original` | 95 | EXIF `DateTimeOriginal` |
| `exif_digitized` | 85 | EXIF `DateTimeDigitized` |
| `filesystem_fallback` | 30 | Best-effort FS date (`st_ctime` on Linux is metadata-change time, not true birth time) |

**Combination logic (already in `analyze_date`):**

1. Collect all available signals.
2. Pick the highest base-confidence signal as primary.
3. Other signals within `mismatch_threshold_days` **agree** (+5 each); farther apart **disagree** (−25 each).
4. Implausible dates (before 1972-07-26, or in the future) are capped at confidence **5**.
5. Confidence &lt; **50** → `date_uncertain = true` → Importer routes to `_review_needed/`.

**Still planned as signals, not yet wired:** filename patterns, `.THM` sidecars, OCR stamps (`ocr_date/`), XMP/IPTC, audio tags, Takeout JSON, hash-twins, etc.

---

## 3. Images beyond JPEG

JPEG is not special — it is only where EXIF is most common. Other formats hide dates in EXIF-like IFDs, XMP packets, text chunks, or container atoms.

### 3.1 Format map

| Format | Date sources | Notes for ChronoVault |
|--------|--------------|------------------------|
| **JPEG / JPG** | EXIF, IPTC, XMP, Photoshop IRB, GPS | EXIF + GPS already used; IPTC/XMP still untapped |
| **TIFF / DNG** | Full EXIF IFDs, XMP | Same mental model as JPEG; often richer |
| **RAW** (CR2, NEF, ARW, ORF, RW2, …) | Maker notes + EXIF | Pillow is weak here; prefer ExifTool / pyexiv2 / raw-aware libs |
| **HEIC / HEIF** | EXIF + QuickTime-style metadata | Default iPhone still format — first-class candidate |
| **WebP** | EXIF + XMP chunks | Common in web/export workflows |
| **PNG** | `eXIf` chunk, `tEXt`/`iTXt` **Creation Time**, XMP | Screenshots/exports often lack true capture time; Creation Time is frequently *export* time |
| **GIF / BMP / SVG** | Almost never useful capture dates | Filename / filesystem only, or skip dating ambition |
| **JPEG XL / AVIF** | EXIF/XMP possible | Niche for a personal vault today; easy to add later |

### 3.2 Photoshop / Adobe “hidden” data

Adobe does not invent a secret calendar. It reuses standard metadata bags that many tools already read (especially **ExifTool**):

1. **XMP** (XML packet inside the file)
   - `xmp:CreateDate`, `xmp:ModifyDate`, `xmp:MetadataDate`
   - `photoshop:DateCreated`
   - `exif:DateTimeOriginal` (often mirrored into XMP even when classic EXIF is messy)
   - **Trust:** Original / DateCreated ≈ capture or digitalization; **ModifyDate ≈ last edit — do not file by ModifyDate alone**

2. **IPTC-IIM** (often inside JPEG APP13 “Photoshop 3.0” segment)
   - Date Created / Time Created
   - Common in news, agency, and older Lightroom-style workflows

3. **Photoshop IRB** (Image Resource Blocks)
   - May hold IPTC and other resources; ExifTool flattens these
   - Rarely better than EXIF/XMP when those already exist

4. **PNG + Photoshop**
   - Often XMP + text **Creation Time**; classic capture EXIF only if an `eXIf` chunk was written

### 3.3 Practical still-image signal set (target)

```text
exif_gps
exif_original
exif_digitized
xmp_datetime_original / xmp_create
iptc_date_created
png_creation_time          (lower base confidence)
filename
filesystem_fallback
```

---

## 4. Audio — MP3 meetings and friends

### 4.1 MP3: yes, headers can carry dates (ID3)

The MPEG audio frames themselves have **no reliable “recorded at” field**. Dates live in **ID3 tags**:

| Tag | Meaning | Usefulness for meeting recordings |
|-----|---------|-----------------------------------|
| **TDRC** (ID3v2.4) | Recording time | Best when present — often set by recorder apps |
| **TDOR** | Original release / recording | Occasional |
| **TDRL** | Release time | Usually “published”, not “when we met” |
| **TYER** / **TDAT** / **TIME** (older v2.3) | Year / date / time | Common on older files |
| **TDTG** | Tagging time | When tags were written — **weak** |
| **COMM** | Comments (free text) | Sometimes “Recorded 2024-03-12…” — parse carefully |

**Libraries:** Python **mutagen** is the usual choice; **ExifTool** also reads ID3 well.

**Caveats that matter for meetings:**

- Some voice-recorder / phone apps **do** write `TDRC` (or at least a year).
- Many “Save as MP3”, WhatsApp, or Telegram exports **strip** tags and leave only filesystem + filename.
- Re-encoding (Audacity export, cloud convert) often sets dates to **export time**, not meeting time.
- Treat ID3 as a **medium** signal: useful, but below a clear filename like `Standup_2024-03-12.mp3`, and far below camera EXIF for photos.

### 4.2 Other audio containers (often better than MP3)

| Format | Where the date is | Notes |
|--------|-------------------|--------|
| **M4A / AAC / MP4 audio** | QuickTime `©day`, `creation_time` in `mvhd` / `tkhd` | iPhone Voice Memos, many dictation apps — often excellent |
| **WAV** | BWF `bext.originationDate` + `originationTime`; LIST/INFO `ICRD` | Field recorders, Zoom H-series, serious mics — strong when BWF present |
| **FLAC / OGG** | Vorbis comments `DATE`, `YEAR` | Good when tagged; free-form strings |
| **AIFF** | Similar metadata families to WAV-ish workflows | Less common for casual meetings |
| **WMA** | ASF creation attributes | Rare in typical Linux personal workflows |

**For “meetings and such,” prefer this order:**

1. Filename / folder (`Meetings/2024/03/…`)
2. M4A / WAV container dates when the recorder wrote them honestly
3. ID3 `TDRC` on MP3
4. Filesystem last

Also watch for **companion files** some apps drop (`.json`, `.xml`, or a matching `.wav` + `.mp3` pair).

### 4.3 Suggested policy for meeting audio

```text
if filename has a clear date     → strong signal
elif ID3 TDRC present + plausible → medium signal
elif parent folder looks like a date → weak signal
else → _review_needed
```

Do **not** invent a calendar day from mtime alone for a nameless `recording.mp3` — that is exactly the failure mode `_review_needed` exists to prevent.

---

## 5. Video

ChronoVault already imports `mp4` / `mov`. Container dates deserve the same multi-signal treatment as photos.

| Source | Notes |
|--------|--------|
| QuickTime / MP4 `mvhd` / `tkhd` `creation_time` | Often real capture time on phone video; can be encode time after re-export |
| `©day` / QuickTime UserData | Human-oriented date atom |
| `com.apple.quicktime.creationdate` | Common on iPhone |
| MKV `DateUTC` | Good when present |
| Embedded timecode | Relative to session start — **not** a calendar date unless day-zero is known |
| GPS in video metadata | Some phones; rare but high trust, similar to photo GPS |

---

## 6. Sidecars and ecosystem signals

In real personal libraries, exports often **strip** embedded metadata. Companions can be more trustworthy than the media file’s own headers.

| Companion | What you get |
|-----------|----------------|
| **Google Takeout** `*.supplemental-metadata.json` (or older `*.json`) | `photoTakenTime.timestamp` — often the **best** date when social apps stripped EXIF |
| **Apple / Photos export sidecars** | Varies; sometimes XMP |
| **`.xmp` next to the file** (Lightroom, darktable, etc.) | Full XMP CreateDate / DateTimeOriginal |
| **`.THM`** next to video/RAW | Mini-JPEG with EXIF (already on the roadmap) |
| **NAS / phone backup folder names** | e.g. `DCIM/Camera/2024/…` as a weak path signal |
| **Email / chat export context** | Usually out of scope unless parsing a known export format |

**Important:** index sidecars as **evidence for a media file**, not as first-class archive photos. Do not file Takeout JSON into `YYYY/MM/DD/` as if it were an image.

**Google Takeout JSON** deserves its own signal name (e.g. `takeout_json`) with **high** base confidence when the JSON is clearly paired with the media file.

---

## 7. Non-header approaches (still valid signals)

None of these replace metadata; they help the residual pile in `_review_needed`.

| Idea | How it helps | Risk |
|------|--------------|------|
| **Burst / sequence clustering** | Neighbor `IMG_0042` has solid EXIF → infer nearby files | Wrong if the folder is a mixed multi-year dump |
| **Same device + sequential numbers** | Camera `IMG_####` monotonic within a day | Breaks after renumber/export |
| **Hash twin already dated** | Identical bytes already archived with high confidence | Excellent — Duplicate Finder + archive DB almost enable this |
| **Folder name as signal** | ` magia/Italy 2019/` | Medium; false positives (`Scan 2019 of 1995 prints`) |
| **OCR date stamp** | Printed corner dates (`ocr_date/`) | Opt-in only; treat as candidate |
| **Audio ASR “today is March 12”** | Rarely said in meetings | Research curiosity — do not auto-file |
| **Visual year estimation (ML)** | Guess era from cars/UI chrome | Too wrong for an archive of record |

**Hash-twin → known date** is especially ChronoVault-native: if Importer sees a SHA-256 already in `archive_files` with high confidence (or a user correction), that date beats filesystem noise.

---

## 8. Suggested confidence tiers (for future `BASE_CONFIDENCE`)

Rough ordering aligned with ChronoVault’s philosophy. Numbers are design guidance, not yet all coded.

| Source | Suggested base | Comment |
|--------|:--------------:|---------|
| EXIF GPS timestamp | 98 | Implemented |
| Matched Takeout / sidecar capture time | 96–98 | When clearly “photo taken” |
| EXIF DateTimeOriginal | 95 | Implemented |
| HEIC / phone MP4 capture creation | 90–95 | If not obviously an export toolchain |
| XMP DateTimeOriginal / `photoshop:DateCreated` | 88–92 | |
| IPTC Date Created | 85–90 | |
| EXIF Digitized | 85 | Implemented |
| WAV BWF origination | 80–90 | Field recorders |
| M4A / MP4 `©day` / mvhd (audio or video) | 70–90 | App-dependent |
| Filename with clear ISO-like date | 70–80 | Strong for meetings |
| ID3 TDRC | 60–75 | Meetings; verify per recorder app |
| PNG Creation Time / weak XMP CreateDate | 40–55 | Often export time |
| ID3 TDTG / `xmp:ModifyDate` alone | 25–40 | Weak |
| Filesystem | 30 | Implemented |
| OCR stamp | 40–60 | Candidate only; person should glance |
| Any implausible date | cap **5** | Implemented |

Agreement / mismatch adjustments (+5 / −25 per signal) already in `analyze_date` remain the right combination model: filename `2024-03-12` agreeing with ID3 `TDRC` should beat either alone.

---

## 9. Extensions to consider for Indexer / Importer

**Current-ish focus:** `jpg`, `jpeg`, `mp4`, `mov`, plus some RAW extensions in indexer config.

**High-value expansions:**

```text
Images:  heic, heif, tiff, tif, webp, png, dng, cr2, arw, nef, …
Audio:   mp3, m4a, wav, flac, aac, ogg
Video:   m4v, avi, mkv, 3gp, webm
Sidecar: thm, xmp, json   (companions / evidence — not always “archive media”)
```

Filters and confidence policy should stay **config-driven** (same spirit as Importer’s size/path/EXIF filters).

---

## 10. Architecture sketch (still modular)

Keep extraction separate from scoring:

| Concern | Home |
|---------|------|
| “Read whatever dates this file type exposes” | Small extractor layer, e.g. evidence bundle builder used by Importer (and later enrich tools) |
| “Combine and score” | Existing `analyze_date` — append signals, do not special-case each format in the scorer |
| Audio tags (MP3/M4A/WAV/FLAC) | `mutagen` and/or ExifTool |
| Broad image/RAW/Adobe/phone coverage | **ExifTool** (CLI → JSON) is the pragmatic Swiss Army knife; pure Python will lag forever on edge formats |
| OCR stamps | Existing `ocr_date/` — opt-in only on low-confidence / review-bucket files |
| Manual override | Existing `write_data.apply_date_correction()` — preserves original algorithmic fields |

Personal-archive volumes are usually fine with one ExifTool invocation per file. Premature micro-optimization is unnecessary.

**Example future evidence bundle shape:**

```python
{
    "file_path": "...",
    "readable_exif": {...},          # existing
    "signals": [                     # or gathered inside analyze_date
        {"source": "filename_pattern", "date": "...", ...},
        {"source": "id3_tdrc", "date": "...", ...},
        {"source": "takeout_json", "date": "...", ...},
    ],
    "mismatch_threshold_days": 1,
}
```

Adding a source = one `BASE_CONFIDENCE` entry + one gather path. Scorer stays stable.

---

## 11. Implementation priority (signals only)

### Tier 1 — high payoff, fits current design

1. **Filename / path date parsing** (photos *and* mp3 / wav / m4a)
2. **XMP + IPTC** on JPEG / TIFF / PNG / WebP
3. **HEIC** and proper **MP4/MOV** container creation dates
4. **Hash-twin already in archive** (reuse known good / user-corrected date)

### Tier 2 — format expansion

5. **ID3** (mp3), **Vorbis** (flac/ogg), **BWF** (wav), **M4A** atoms
6. **Google Takeout JSON** sidecars
7. **`.xmp` / `.THM`** companions
8. **PNG `eXIf` + Creation Time** (low confidence)

### Tier 3 — residual / opt-in

9. **OCR stamps** (module exists; wire as deliberate enrich step)
10. **Burst / sequence inference**
11. **ML / ASR content guesses** — UI suggestions only, never auto-file

### Explicit non-goals (for auto-filing)

- Trusting `ModifyDate` / tagging time alone
- Filing nameless recordings from filesystem mtime
- Running OCR on every import
- Auto-deleting duplicates or auto-picking winners without a person

---

## 12. Optional follow-on product pieces (context)

These are not “signals,” but they are how signals become useful:

| Piece | Role |
|-------|------|
| **Enrich uncertain dates** tool | Only touches `_review_needed`; tries filename → optional OCR → re-score |
| **Terminal or GUI review** | Uses `retrieve_data` + `write_data` |
| **Hash-at-import skip** | Don’t grow the archive with identical bytes |
| **Duplicate “pick winner”** | When same hash sits in two date folders |
| **Apply audit fixes** | Act on Audit Archive JSON (dry-run first) |

---

## 13. Bottom line

- **JPEG is not the only place dates hide.** HEIC, RAW, TIFF, WebP, PNG (sometimes), and video containers all carry dates; Adobe mostly via **XMP/IPTC**, not magic private fields.
- **MP3: yes — ID3 (especially TDRC)** is real and useful for meetings, at **medium** trust; always combine with **filename/folder**. Prefer also supporting **M4A** and **WAV (BWF)** when you control the recorder.
- **Best non-header bets in real libraries:** Takeout/sidecar JSON, and **“this hash already has a good date.”**
- **ChronoVault’s existing scorer is already the right shape.** The work is mostly extractors + base confidence entries + opt-in enrich for the review bucket.

---

## Document history

- **2026-08-01** — Initial catalog packaged from design discussion (signals research; not an implementation commit by itself).
