# classify_media

`classify_media` runs after Indexer and before Condition Database. It decides whether an already-indexed file is likely to be personal camera/scanned media or a web/graphic asset, before ChronoVault spends time hashing it.

It is deliberately conservative. A stripped camera photo or scan must not be discarded merely because it lacks EXIF. By default, only `certain_not` files are marked `excluded`; all other classifications remain `located` and proceed to Condition Database.

## Usage

```text
python3 classify_media/classify_media.py classify_media/config.json
```

Run this after Indexer has created `located_files.db`; pointing at a nonexistent path creates an empty SQLite file and then fails because the `located_files` table is absent. Relative database and report paths are resolved from the process working directory.

| Option | Default | Meaning |
|---|---|---|
| `database_path` | *(required)* | Indexer's source-inventory database. |
| `output_report_path` | `classification_report.json` | JSON summary and per-file failures. |
| `image_extensions` | common Pillow-readable image extensions | Extensions handled by the image classifier; values may include or omit a leading dot and are case-insensitive. |
| `exclude_categories` | `["certain_not"]` | Valid result categories that should change a row's status to `excluded`. |
| `force_reclassify` | `false` | Revisit located rows and rows this classifier previously excluded. |

## Results

The tool adds four columns to the `located_files` table automatically:

| Column | Meaning |
|---|---|
| `media_score` | 0–100 likelihood that the file is personal media worth archiving. |
| `media_category` | `certain_yes`, `likely_yes`, `unknown`, `likely_not`, or `certain_not`. |
| `media_reason` | Concise list of the evidence that affected the score. |
| `media_excluded` | `1` only when this classifier itself set `status` to `excluded`; prevents a later reclassification from undoing an Importer exclusion. |

The score bands are 85–100 `certain_yes`, 65–84 `likely_yes`, 35–64 `unknown`, 15–34 `likely_not`, and 0–14 `certain_not`.

## Initial Image Evidence

For configured image extensions, `image_tools/image_inspection.py` uses Pillow to gather small, independently understandable signals: camera EXIF make/model/lens/serial tags; filename prefixes (`img_`, `dsc_`, `pxl_`, `photo_`, `scan_`); dimensions and file size; palette/binary mode; sampled color diversity; high-DPI scan evidence; and web-asset terms anywhere in the path (`favicon`, `icon`, `logo`, `sprite`, `thumbnail`, `thumb`, `avatar`, or `button`). Unreadable images receive a neutral `unknown` result rather than aborting the run.

It does not yet classify video, audio, or documents. Those files receive `unknown` with a neutral score and remain eligible for later type-specific tools.

## Safety and Re-running

The normal mode classifies only rows whose `media_category` is `NULL`, so reruns are safe. Set `force_reclassify` to `true` after changing thresholds or code; this reevaluates normal files plus files previously excluded by this classifier, without undoing exclusions made later by Importer. To make a more aggressive policy later, add `likely_not` to `exclude_categories`, but the default should remain cautious.

Candidate review is not built yet. Until it exists, `unknown` and `likely_not` remain eligible for conditioning/import rather than being silently hidden.

Each processed row is committed immediately. The JSON report records the timestamp, database path, processed/failed totals, counts for all five categories, the excluded count, and any per-file exceptions. If there are no eligible rows, the tool exits without writing a new report.

Runtime dependencies are Python's standard library plus Pillow. Classification reads source files for inspection and updates only the source-inventory database; it does not move, copy, or delete media.
