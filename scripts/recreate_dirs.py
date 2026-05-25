#!/usr/bin/env python3
"""
Recreate the directory structure described by a `tree -d` command output.

Usage:
    python recreate_dirs.py <tree-output-file> <target-root>
    python recreate_dirs.py <tree-output-file> <target-root> --dry-run

The first line of the tree file is treated as the source root and discarded;
everything else is created relative to <target-root>.

The input must come from `tree -d` (directories only). The script does no
file/directory disambiguation - every entry is created as a directory.

The script is idempotent: re-running it on an existing tree is a no-op.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# `tree` uses fixed 4-character indent units (│ + 2 nbsp + space, or 4 nbsp/space),
# followed by a branch marker (├── or └──) and the entry name. The indent
# characters tree actually uses are the box-drawing vertical bar │, regular
# space, and U+00A0 non-breaking space - so the indent character class is
# permissive.
ENTRY_RE = re.compile(r"^(?P<indent>[│ \xa0]*)[├└]── (?P<name>.+)$")
INDENT_UNIT = 4


def iter_dir_paths(body: list[str]):
    """Yield each directory as a Path relative to the (omitted) source root."""
    stack: list[str] = []  # stack[d] = name of the ancestor at depth d
    for line in body:
        m = ENTRY_RE.match(line)
        if not m:
            continue  # footer summary, blanks, anything that isn't a tree entry
        depth = len(m["indent"]) // INDENT_UNIT
        del stack[depth:]
        stack.append(m["name"])
        yield Path(*stack)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tree_file", type=Path, help="file containing `tree -d` output")
    parser.add_argument("target_root", type=Path, help="where to create the tree")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the directories that would be created without creating them",
    )
    args = parser.parse_args()

    if not args.tree_file.is_file():
        print(f"error: {args.tree_file} is not a file", file=sys.stderr)
        return 2

    lines = args.tree_file.read_text(encoding="utf-8").splitlines()
    if not lines:
        print("error: tree file is empty", file=sys.stderr)
        return 2

    source_root, *body = lines
    dir_paths = list(iter_dir_paths(body))

    print(f"source root: {source_root.strip()}")
    print(f"target root: {args.target_root}")
    print(f"{len(dir_paths)} directories to create")

    if args.dry_run:
        for p in dir_paths:
            print(args.target_root / p)
        return 0

    args.target_root.mkdir(parents=True, exist_ok=True)
    created = 0
    for rel in dir_paths:
        full = args.target_root / rel
        if not full.exists():
            full.mkdir(parents=True, exist_ok=True)
            created += 1
    print(
        f"created {created} new directories (skipped {len(dir_paths) - created} existing)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
