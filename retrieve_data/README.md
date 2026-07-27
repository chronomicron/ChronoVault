# retrieve_data

`retrieve_data` is the read-only data-access layer over `archive_database.db`. It exists to answer one question — "what would a display panel need to know?" — without knowing or caring what that display panel actually is.

## Why It Exists

Every other tool in ChronoVault so far is a terminal script: run it, read printed output, done. That works fine for a person running commands, but a future GUI (Qt desktop app, or a web app, or both) needs the same underlying data as *structured values it can act on*, not text scraped from a `print()` statement. Rather than have a future GUI shell out to `audit_archive.py` and parse its output, `retrieve_data` queries the database directly and returns plain Python dicts — the same shape whether the caller is a one-off test script, a Qt widget, or a web server turning the result straight into a JSON response.

This module makes **no assumptions about desktop vs. web**. There's no Qt import, no HTML, no HTTP anywhere in it — just `sqlite3` and `pathlib`. Whatever consumes its output decides how to display it.

## What It Deliberately Does NOT Do

- **No image bytes, no thumbnails.** It hands back a resolved `absolute_path` for each file and stops there. A desktop app can open that path directly; a web layer would need its own route to read and stream the bytes. Different consumers reasonably want different things here, so it isn't baked into the shared layer.
- **No writing.** This module only ever reads. Moving files or changing the database is a deliberately separate, riskier concern — see `write_data/README.md`.

## Usage

```python
from retrieve_data.retrieve_data import list_review_items, get_file_details

items = list_review_items("archive")
for item in items:
    print(item["archive_path"], item["confidence"], item["date_reason"])

details = get_file_details("archive", file_id=12)
```

## Functions

### `list_review_items(archive_root)`

Returns every file currently sitting in the review bucket (`date_uncertain = 1`), most recently added first — the exact list a "files needing a decision" screen would show.

Returns a list of dicts. Each dict is every column from `archive_files` for that row, plus two computed fields:

| Field           | Description |
|------------------|--------------|
| `absolute_path`  | The file's location, resolved to an absolute path regardless of the caller's working directory. |
| `file_exists`    | `true`/`false` — whether the file is actually still there on disk. Lets a UI show "this file went missing" without a separate Audit Archive run. |

### `get_file_details(archive_root, file_id)`

Returns the full record for a single file by its database `id`, or `None` if that id doesn't exist. Same dict shape as `list_review_items()` — meant for a detail view once something's been selected from a list, so a UI never has to special-case "the list view" vs. "the detail view."

## Design Note: Everything Is JSON-Serializable

Date fields (`date_taken`, `filesystem_creation_date`, `date_added`, `user_corrected_date`, `corrected_at`) are already stored as ISO-format strings by Importer and `write_data`, not as Python `datetime` objects — so nothing this module returns ever needs special handling before `json.dumps()`. This was verified directly: the full output of `list_review_items()` round-trips through `json.dumps()` cleanly with no custom encoder. That's not incidental — it's the actual point of the design, since it means a web layer could return this data as an API response with zero adapter code in between.

## A Note on Naming

If you're looking for this in the filesystem and typing `read_data` out of habit — the folder is `retrieve_data`, matching its write-side twin `write_data`.
