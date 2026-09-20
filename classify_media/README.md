# classify_media

`classify_media` runs after Indexer and before Condition Database. It decides whether an already-indexed file is likely to be personal camera/scanned media or a web/graphic asset, before ChronoVault spends time hashing it.

It is deliberately conservative. A stripped camera photo or scan must not be discarded merely because it lacks EXIF. By default, only `certain_not` files are marked `excluded`; all other classifications remain `located` and proceed to Condition Database.

## Usage

```text
python3 classify_media/classify_media.py classify_media/config.json
```

`config.json` has the same path conventions as the other command-line tools: `database_path` and report paths are resolved from the directory where the command is run.

## Results

The tool adds three columns to `located_files.db` automatically:

| Column | Meaning |
|---|---|
| `media_score` | 0–100 likelihood that the file is personal media worth archiving. |
| `media_category` | `certain_yes`, `likely_yes`, `unknown`, `likely_not`, or `certain_not`. |
| `media_reason` | Concise list of the evidence that affected the score. |
| `media_excluded` | `1` only when this classifier itself set `status` to `excluded`; prevents a later reclassification from undoing an Importer exclusion. |

The score bands are 85–100 `certain_yes`, 65–84 `likely_yes`, 35–64 `unknown`, 15–34 `likely_not`, and 0–14 `certain_not`.

## Initial Image Evidence

For configured image extensions, `image_tools/image_inspection.py` gathers small, independently understandable signals: camera EXIF make/model fields, camera-like filename prefixes, image dimensions, file size, palette/binary color mode, sampled color diversity, DPI evidence for a scan, and web-asset filename/path terms such as `favicon`, `icon`, or `sprite`.

It does not yet classify video, audio, or documents. Those files receive `unknown` with a neutral score and remain eligible for later type-specific tools.

## Safety and Re-running

The normal mode classifies only rows whose `media_category` is `NULL`, so reruns are safe. Set `force_reclassify` to `true` after changing thresholds or code; this reevaluates normal files plus files previously excluded by this classifier, without undoing exclusions made later by Importer. To make a more aggressive policy later, add `likely_not` to `exclude_categories`, but the default should remain cautious.

Candidate review is not built yet. Until it exists, `unknown` and `likely_not` remain eligible for conditioning/import rather than being silently hidden.
