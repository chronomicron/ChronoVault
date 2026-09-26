# audio_tools

This directory is reserved for audio-specific date evidence. It is not implemented or used by `analyze_date` yet.

`id3_tools.py` is currently an empty placeholder. There is no ID3 parser, no audio extension dispatch in `gather_signals()`, and no audio-specific entry in `BASE_CONFIDENCE`. Audio files can still receive the type-independent filename and containing-folder signals, followed by the filesystem fallback.

Planned work discussed elsewhere in the repository includes reading MP3 ID3 recording dates (likely with `mutagen`) and eventually handling date metadata in formats such as M4A, WAV, FLAC, and OGG. Those are plans, not current capabilities.
