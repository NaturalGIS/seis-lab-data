"""Path patterns: paths whose segments may be regular expressions.

A pattern such as `s01/.*_Data/.*\\.tif` has a literal prefix (`s01`), made of
the segments before the first one with regexp metacharacters. Each remaining
segment matches a path segment in order, the last one the file name, and any
number of directories may be skipped before, between or after the matched ones.
"""

import logging
import re
from collections.abc import AsyncIterator

from anyio import Path

logger = logging.getLogger(__name__)


def split_pattern_path(regexp_path: str) -> tuple[Path, str]:
    """Split a path pattern into its literal prefix and its remaining segments.

    Returns the literal prefix as a Path and the remaining segments as a string,
    empty if the pattern has no regexp segments.
    """
    _re_meta = re.compile(r"[.*+?^${}()\[\]|\\]")
    parts = Path(regexp_path).parts
    plain_parts = []
    for i, part in enumerate(parts):
        if _re_meta.search(part):
            pattern = str(Path(*parts[i:])) if parts[i:] else ""
            return Path(*plain_parts) if plain_parts else Path("."), pattern
        plain_parts.append(part)
    return Path(regexp_path), ""


async def walk_pattern(
    current: Path, remaining: tuple[str, ...]
) -> AsyncIterator[Path]:
    """Yield the files under `current` that the remaining pattern segments match."""
    if not remaining:
        if await current.is_file():
            yield current
        return

    head, *tail = remaining
    tail = tuple(tail)
    regex = re.compile(f"^{head}$")
    try:
        async for entry in current.iterdir():
            if await entry.is_dir():
                async for matched in walk_pattern(entry, remaining):
                    yield matched
            if regex.match(entry.name):
                if tail:
                    async for matched in walk_pattern(entry, tail):
                        yield matched
                else:
                    if await entry.is_file():
                        yield entry
    # a directory that is missing or cannot be read has no matches
    except (FileNotFoundError, PermissionError, NotADirectoryError):
        return


def path_matches_pattern(relative_path_regexp: str, relative_path: str) -> bool:
    """Check whether a relative file path matches a relative path pattern.

    Matching is purely lexical, without filesystem access. It applies the
    matching rules of `walk_pattern` from the pattern's literal prefix.
    A leading slash on either argument is ignored. A pattern containing an
    invalid regular expression is logged and matches no path.
    """
    # a leading slash is ignored, as when the pattern is joined to a root directory
    prefix, pattern = split_pattern_path(relative_path_regexp.lstrip("/"))
    path_parts = Path(relative_path.lstrip("/")).parts
    prefix_parts = prefix.parts
    if path_parts[: len(prefix_parts)] != prefix_parts:
        return False
    remaining_parts = path_parts[len(prefix_parts) :]
    if not pattern:
        return remaining_parts == ()
    if not remaining_parts:
        return False
    *directory_patterns, file_name_pattern = Path(pattern).parts
    *directories, file_name = remaining_parts
    try:
        file_name_regex = re.compile(f"^{file_name_pattern}$")
        directory_regexes = [re.compile(f"^{p}$") for p in directory_patterns]
    except re.error as err:
        logger.warning("Invalid path pattern %r: %s", relative_path_regexp, err)
        return False
    if not file_name_regex.match(file_name):
        return False
    # each directory pattern consumes the directories up to the one it matches
    unmatched_directories = iter(directories)
    for regex in directory_regexes:
        if not any(regex.match(directory) for directory in unmatched_directories):
            return False
    return True
