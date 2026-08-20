# multi_tools

Evidence-gathering functions that apply to **any file type**, unlike `image_tools`/`audio_tools`/`video_tools` (each specific to one media type — what this project calls a "multitool," in the sense of a self-contained toolkit for one job). A filename or folder-path pattern means the same thing whether the file is a photo, an MP3, or a PDF, so these live here instead of inside any type-specific folder.

Like every other `analyze_date` evidence source, neither of these is meant to be imported directly by anything outside `analyze_date` — `gather_signals()` is the single place that decides which sources to call and combines whatever they find.

## `analyze_filename.py`

`get_date_from_filename(file_path)` — extracts a date from the file's own filename. Handles two distinct kinds of pattern:

- **Fixed-convention camera/phone filenames** (`IMG_20240315_143022.jpg`, `Screenshot_20240315-143022.png`) — always year-first (YYYYMMDD), a well-documented, worldwide-consistent convention regardless of the user's regional date format. Trusted as unambiguous.
- **Bare numeric dates** (`03-15-2024.jpg`, `15-03-2024.jpg`, `2024-03-15.pdf`) — genuinely ambiguous when the year comes last, since it could be US-style (month-day-year) or European-style (day-month-year). Both readings are tried; whichever is *structurally valid* wins (e.g. `25-12-2023` can only be day-first, since there's no 25th month); when both orderings would be valid, the US/month-first reading is used as the default.

**Known, honestly-documented tradeoff:** a filename like `chapter-1-2-2020.docx` is structurally identical to a real date pattern and gets read as one (`2020-01-02`), even though it's plausibly just sequential numbering. This is exactly why `filename_pattern`'s base confidence (70) is moderate rather than high — a single ambiguous filename match isn't meant to dominate on its own; agreement or disagreement with other signals is what actually settles it.

## `analyze_folder.py`

`get_date_from_path(file_path)` — extracts a date from one of the file's containing folder names, checked from the immediate parent outward. Recognizes a folder literally named a year (`2024`), a year-month (`2024-03`), or a month name and year (`March 2024`, `Mar 2024`).

Deliberately a **weaker** signal than the filename (confidence 40, the same tier as the filesystem fallback) — a folder named `2024` is just as likely to reflect when someone *sorted* or *imported* files as when they were actually taken. Always day-level precision at best (a folder can't tell you a time), often only month or year precision.

## Shared Design Notes

- Both modules use the same disambiguation-by-plausibility approach already proven in `image_tools/ocr_tools.py`: when a match could be read more than one way, whichever reading produces a real, valid date wins; when both are valid, a sensible default is used rather than refusing to answer.
- Both reject implausible years (before 1990, or in the future) before accepting a match — the same protection against a coincidental digit run (a folder literally named `1080` for video resolution, say) being misread as a date.
- Neither raises on a file/path with no usable pattern — that's the normal, expected case, not an error.

## Future Additions

**Adjacent-files inference** was discussed as a next candidate for this folder (or somewhere similar) — the idea that a file with no other evidence might reasonably inherit a date from other, already-dated files sitting in the same folder. Not yet built, and it's architecturally different from everything else here: it needs access to *other* files' already-resolved dates, not just this one file's own path or metadata. Whether that means a `multi_tools` function that accepts pre-fetched sibling data as a parameter, or a second pass built into `condition_database.py` (which already has natural database access while it's conditioning a batch of files), is still an open design question — see `ROADMAP.md`.
