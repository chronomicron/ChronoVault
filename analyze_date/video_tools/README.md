# video_tools

This directory is reserved for video-container date evidence. It is not implemented or used by `analyze_date` yet.

`container_tools.py` contains only a placeholder module docstring describing possible MP4/QuickTime `creation_time` extraction. There is no callable extractor, no video extension dispatch in `gather_signals()`, and no video-specific entry in `BASE_CONFIDENCE`. Video files can still receive the type-independent filename and containing-folder signals, followed by the filesystem fallback.

The placeholder mentions `mutagen` or `ffprobe` as possible dependencies, but no dependency or implementation has been selected.
