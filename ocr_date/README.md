# ocr_date

`ocr_date` scans the corners of an image for a printed/imprinted date -- the kind old date-stamp cameras burn directly into a photo, or that a scanned print carries from the original film. This is a real signal specifically for the files that need it most: old or scanned photos with no EXIF at all, where a printed date may be the *only* evidence of when a photo was actually taken.

**This is meant to be opt-in, not automatic.** It should only ever run against files already sitting in `_review_needed/` with weak or no other evidence -- a deliberate "look for more clues" action, not something applied to every file on every import. OCR is slow (scanning multiple corners at multiple rotations and preprocessing variants adds up) and unnecessary for the majority of files that already have solid EXIF. Wiring this in as that kind of opt-in step (in Importer, or eventually a GUI button) is still unbuilt -- this module only provides the underlying mechanism so far.

## Setup

Three separate things need installing, none of which are optional:

```
sudo apt install tesseract-ocr          # the actual OCR engine (system binary)
pip install pytesseract --break-system-packages   # Python bindings for it (or: apt install python3-pytesseract)
pip install opencv-python-headless --break-system-packages   # image preprocessing (Otsu thresholding)
```

For `pytesseract`, try `apt install python3-pytesseract` first -- if it's available in your distro's repos, it avoids `--break-system-packages` entirely. `opencv-python-headless` is used deliberately over plain `opencv-python`, since this is a script, not a GUI app, and headless skips a lot of unnecessary GUI-toolkit dependencies.

## Usage

```python
from ocr_date.ocr_date import find_date_in_corners

result = find_date_in_corners("old_photo.jpg")
# {'date': datetime(1999, 7, 15) or None, 'corner': 'bottom_right' or None,
#  'rotation': 0 or None, 'variant': 'raw' or 'otsu' or None,
#  'raw_text': '...' or None, 'ocr_confidence': 62.0 or None,
#  'checked': [...]}  # every corner/rotation/variant combo actually tried
```

Pass `debug_dir="some/folder"` to also save every crop actually fed to OCR as a PNG -- the single most useful tool for diagnosing a failure, since it shows you exactly what the algorithm saw rather than making you guess.

## How It Works

For each of the 4 corners, in order (`bottom_right`, `bottom_left`, `top_right`, `top_left` -- most to least likely location):

1. Crop a **wide, short strip** along that edge (95% width, 25% height) -- date stamps live in a thin band, not a square region. An earlier square-ish crop diluted the tiny text with too much unrelated photo content.
2. Upscale 3x (Tesseract reads larger text more reliably).
3. Try each rotation in turn: 0°, 90°, 180°, 270° -- 0° first, since most stamps are upright and this keeps the common case fast.
4. At each rotation, try both the **raw grayscale** crop and an **Otsu-thresholded** (auto black/white) version -- Otsu dramatically helps small, low-contrast dot-matrix stamps (the kind security cameras and baby monitors burn in), but isn't always better for a clean, high-contrast stamp, so both get a chance.
5. OCR is run with a character whitelist (digits + date punctuation only) to cut down on garbage, and confidence-aware (`image_to_data`, not `image_to_string`) so a date-shaped match from very uncertain OCR can be rejected rather than trusted.

Stops at the first corner/rotation/variant combination that produces both a valid date *and* meets `MIN_OCR_CONFIDENCE`.

## Known Limitations (Found by Real-World Testing, Not Assumed)

- **Colon means time, not date.** A colon-separated group in a stamp reliably means clock time, not a date -- deliberately excluded from the date-separator set, since parsing a time as a date risks a confident false match.
- **Confidence, not just regex-matching, gates acceptance.** A narrow character whitelist can make Tesseract guess a plausible-looking but *wrong* digit sequence out of pure noise, rather than honestly failing. `MIN_OCR_CONFIDENCE` exists specifically to catch this.
- **A structurally valid but implausible year stops the search entirely for that text**, rather than falling through to a weaker date pattern. Found necessary live: a single OCR digit misread (`2024` -> `1024`) was correctly rejected for its implausible year, but the code then tried a *different* pattern on the same text and matched leftover time digits into a second, different, also-wrong date. One bad read shouldn't invite a worse one.
- **Japanese (and likely other non-Latin) date stamps are not supported yet.** Real testing turned up two examples using kanji (年/月/日) instead of numeric separators. This needs a Tesseract language pack (`tesseract-ocr-jpn`) not installed by default, explicit language selection per OCR call, and new parsing patterns -- a distinctly bigger piece of work, not yet started.
- **Even with all of the above, real-world accuracy on genuinely hard cases (small, low-contrast, dot-matrix, noisy) is limited.** Out of 9 real downloaded test photos, most needed multiple rounds of real fixes to get even close, and several remain unresolved. This is a genuinely hard OCR problem, not a quick win -- treat any date this module returns as a *candidate* worth a person's glance, never as trusted as a clean EXIF read.

## Future Evidence Sources Worth Adding

Not part of this module, but related: **XMP and IPTC metadata** (embedded by editors like Photoshop and Lightroom, separate from EXIF) can carry their own `CreateDate`/`ModifyDate` fields, and are a legitimate additional signal for `analyze_date` alongside filename parsing and `.THM` sidecar files -- worth tracking in `analyze_date`'s README as another future signal source once there's time to build it.
