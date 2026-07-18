# scripts

One-off utility scripts. Run Python scripts with `uv run python scripts/<name>` (or `python3 scripts/<name>`), shell scripts with `bash scripts/<name>.sh`. Python scripts accept `--help`.

- **`quick-get-sample-data.sh`** — download a sample of the survey archive from the production server (rsync over ssh). Usage: `bash scripts/quick-get-sample-data.sh <archive-root>`.
- **`recreate_dirs.py`** — recreate an empty directory tree from a `tree -d` listing. Usage: `python3 scripts/recreate_dirs.py <tree-file> <target-root>` (e.g. with `sample-file-tree.txt`).
- **`survey_extensions.py`** — aggregate file extensions per `.example-survey` template folder, from a list of file paths. Usage: `python3 scripts/survey_extensions.py --file-list <list> --template-dir sample-data/.example-survey --output survey-extensions.txt`.
- **`emodnet.py`** — download EMODNet bathymetry tiles.
- **`mbtiles.py`** — build an MBTiles file from a `z/x/y` directory of PNG tiles.
- **`screenshotter.py`** — render a MapLibre map to a PNG (Playwright), for use as a project / survey mission / record image. Uses `map-template.j2.html`.

Data files: `sample-file-tree.txt` (input for `recreate_dirs.py`), `survey-extensions.txt` (output of `survey_extensions.py`).
