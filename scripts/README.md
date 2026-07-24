# scripts

One-off utility scripts. Run Python scripts with `uv run python scripts/<name>` (or `python3 scripts/<name>`), shell scripts with `bash scripts/<name>.sh`. Python scripts accept `--help`.

- **`quick-get-sample-data.sh`** — download a sample of the survey archive from the production server (rsync over ssh). Usage: `bash scripts/quick-get-sample-data.sh <archive-root>`.
- **`validate_extractors.py`** — validate the metadata extractors against a whole archive, header-only and read-only, writing one CSV row per file. Pure standard library so it runs on any `python3` without installing anything; the KMALL and SEG-Y parsing mirrors `tasks/extractors/kmall.py` and `segy.py` and must be kept in sync with them. Usage: `python3 scripts/validate_extractors.py --root <archive-root> --extension .kmall --output report.csv`.
- **`run-archive-validation.sh`** — run the validator against the production archive in chunks, over ssh, leaving nothing on the server (the validator is streamed in, the CSV streamed back). One report per chunk, so a dropped connection costs one chunk rather than a whole multi-hour run. Usage: `bash scripts/run-archive-validation.sh <kmall|segy-previews|segy-rest>`; see the script for the chunk tables and the `SLD_VALIDATION_*` overrides.
- **`analyse_segy_reports.py`** — analyse the `validate_extractors.py` CSV reports for SEG-Y, printing the agreed checks (geographic files by units code, garbage/partial coverage, small-support and mis-scaled boxes, partial-metadata signatures, errors by size, suspect dates). Pure standard library; encodes the analysis rules so a fresh archive scan is re-audited the same way rather than ad-hoc. Usage: `python3 scripts/analyse_segy_reports.py --reports <dir>`.
- **`probe_coords.py`** — read-only forensic probe that dumps the sampled src/cdp coordinate distribution of one or more SEG-Y files, to tell apart a real line stretched by a burst of bad-nav traces from a coordinate field that is wholly noise. Pure standard library; stream it to a host that holds the files (`ssh <host> "python3 - /path/a.sgy" < scripts/probe_coords.py`). Usage: `python3 scripts/probe_coords.py <file.sgy> [...]`.
- **`recreate_dirs.py`** — recreate an empty directory tree from a `tree -d` listing. Usage: `python3 scripts/recreate_dirs.py <tree-file> <target-root>` (e.g. with `sample-file-tree.txt`).
- **`survey_extensions.py`** — aggregate file extensions per `.example-survey` template folder, from a list of file paths. Usage: `python3 scripts/survey_extensions.py --file-list <list> --template-dir sample-data/.example-survey --output survey-extensions.txt`.
- **`emodnet.py`** — download EMODNet bathymetry tiles.
- **`mbtiles.py`** — build an MBTiles file from a `z/x/y` directory of PNG tiles.
- **`screenshotter.py`** — render a MapLibre map to a PNG (Playwright), for use as a project / survey mission / record image. Uses `map-template.j2.html`.

Data files: `sample-file-tree.txt` (input for `recreate_dirs.py`), `survey-extensions.txt` (output of `survey_extensions.py`).
