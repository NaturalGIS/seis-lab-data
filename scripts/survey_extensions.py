#!/usr/bin/env python3
"""Aggregate file extensions per template folder across all surveys.

Reads a list of file paths (one per line, relative to the surveys root, e.g.
``./owf-seism-2024/s06-mbes/s02-raw-data/file.kmall``) produced on the server with:

    cd /mnt/seislab_data/surveys && find . -type f > survey-files.txt

For every file it finds the deepest folder of the ``.example-survey`` template that
is an ancestor of (or equal to) the file's directory, and records the file's
extension there. Files that live in extra (non-template) subfolders therefore roll
up to the nearest template folder. The result is the union of extensions per
template folder across all surveys, with no per-survey identification.

Output (default): a tree of the whole template with the extensions (and file
counts) annotated on each folder, plus a global list of all extensions by count.
Aggregation is kept separate from rendering, so emitting CSV/Excel later is trivial.

Usage:
    python3 scripts/survey_extensions.py --file-list survey-files.txt \\
        --template-dir sample-data/.example-survey --output survey-extensions.txt

    # or read the list from stdin (single command):
    ssh seis-lab-data-production 'cd /mnt/seislab_data/surveys && find . -type f' \\
        | python3 scripts/survey_extensions.py --template-dir sample-data/.example-survey
"""

from __future__ import annotations

import argparse
import collections
import os
import sys

# OS noise that is never worth indexing.
JUNK_NAMES = {".ds_store", "thumbs.db"}


def load_template_folders(template_dir: str) -> set:
    """Return the set of folder paths (relative, posix) inside the template."""
    folders = set()
    for dirpath, _, _ in os.walk(template_dir):
        rel = os.path.relpath(dirpath, template_dir).replace(os.sep, "/")
        if rel != ".":
            folders.add(rel)
    return folders


def extension_of(filename: str) -> str:
    """Lowercased extension including the dot, or ``(no-ext)``.

    Uses the last dotted component, so ``x.tif.aux.xml`` -> ``.xml``. A leading dot
    with no other dot (hidden file) counts as no extension.
    """
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot > 0 else "(no-ext)"


def aggregate(lines, template_folders):
    """Map each file to its nearest template folder and count extensions.

    Returns ``(per_folder, outside, n_files, surveys)`` where ``per_folder`` is
    ``folder -> Counter(ext)`` and ``outside`` holds files with no template ancestor.
    """
    per_folder = collections.defaultdict(collections.Counter)
    outside = collections.Counter()
    surveys = set()
    n_files = 0
    rollup_cache = {}

    def rollup(reldir):
        cached = rollup_cache.get(reldir, 0)
        if cached != 0:
            return cached
        cur = reldir
        while cur:
            if cur in template_folders:
                rollup_cache[reldir] = cur
                return cur
            cur = cur.rsplit("/", 1)[0] if "/" in cur else ""
        rollup_cache[reldir] = None
        return None

    for line in lines:
        path = line.rstrip("\n")
        if path.startswith("./"):
            path = path[2:]
        sep = path.find("/")
        if sep < 0:
            continue  # a file directly under the surveys root, with no survey - skip
        rest = path[sep + 1 :]
        slash = rest.rfind("/")
        reldir, filename = (
            (rest[:slash], rest[slash + 1 :]) if slash >= 0 else ("", rest)
        )
        if filename.lower() in JUNK_NAMES:
            continue
        n_files += 1
        surveys.add(path[:sep])
        ext = extension_of(filename)
        folder = rollup(reldir) if reldir else None
        if folder is None:
            outside[ext] += 1
        else:
            per_folder[folder][ext] += 1
    return per_folder, outside, n_files, surveys


def render_tree(template_folders, per_folder):
    """Render the whole template as an indented tree annotated with extensions."""
    # Build a nested dict from the template folder paths.
    root = {}
    for folder in template_folders:
        node = root
        for part in folder.split("/"):
            node = node.setdefault(part, {})

    lines = []

    def walk(node, parts, prefix):
        names = sorted(node)
        for i, name in enumerate(names):
            last = i == len(names) - 1
            connector = "└── " if last else "├── "
            counter = per_folder.get("/".join(parts + [name]))
            exts = (
                "  " + ", ".join(f"{e}({c})" for e, c in counter.most_common())
                if counter
                else ""
            )
            lines.append(f"{prefix}{connector}{name}/{exts}")
            walk(node[name], parts + [name], prefix + ("    " if last else "│   "))

    walk(root, [], "")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--file-list", help="file with one path per line (default: stdin)"
    )
    parser.add_argument(
        "--template-dir", required=True, help="the .example-survey template directory"
    )
    parser.add_argument("--output", help="output file (default: stdout)")
    args = parser.parse_args()

    template_folders = load_template_folders(args.template_dir)

    source = (
        open(args.file_list, encoding="utf-8", errors="replace")
        if args.file_list
        else sys.stdin
    )
    try:
        per_folder, outside, n_files, surveys = aggregate(source, template_folders)
    finally:
        if args.file_list:
            source.close()

    # Global extension universe across all folders - handy for spotting noise.
    universe = collections.Counter()
    for counter in per_folder.values():
        universe.update(counter)
    universe.update(outside)

    out = []
    out.append("# Survey file extensions per .example-survey folder")
    out.append(
        f"# files: {n_files:,} | surveys: {len(surveys)} | "
        f"template folders: {len(template_folders)} | folders with files: {len(per_folder)} | "
        f"distinct extensions: {len(universe)}"
    )
    out.append(
        "# Each folder lists ext(file_count), aggregated across all surveys (no per-survey detail)."
    )
    out.append(
        "# Review and delete the extensions that are noise; what remains is what to index."
    )
    out.append("")
    out.append("## All extensions, by file count")
    out.extend(f"  {ext}\t{count}" for ext, count in universe.most_common())
    out.append("")
    out.append("## Template tree (.example-survey)")
    out.append(".example-survey/")
    out.extend(render_tree(template_folders, per_folder))
    if outside:
        out.append("")
        out.append("## Files outside the template (no template ancestor)")
        out.extend(f"  {ext}\t{count}" for ext, count in outside.most_common())

    text = "\n".join(out) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(
            f"wrote {args.output}: {n_files:,} files, {len(per_folder)} folders with extensions, "
            f"{len(universe)} distinct extensions",
            file=sys.stderr,
        )
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
