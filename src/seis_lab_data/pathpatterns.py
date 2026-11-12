"""Path patterns: paths whose segments may be regular expressions.

A pattern such as `s01/.*_Data/.*\\.tif` has a literal prefix (`s01`), made of
the segments before the first one with regexp metacharacters. Each remaining
segment matches a path segment in order, the last one the file name, and any
number of directories may be skipped before, between or after the matched ones.
A pattern without regexp segments matches only the path it spells.
"""

import dataclasses
import logging
import os
import re
from collections.abc import (
    AsyncIterator,
    Collection,
    Sequence,
)

from anyio import (
    Path,
    to_thread,
)

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class PathPattern:
    """A compiled relative path pattern."""

    prefix_parts: tuple[str, ...]
    directory_regexes: tuple[re.Pattern, ...]
    # None for a pattern without regexp segments
    file_name_regex: re.Pattern | None

    def matches(self, relative_path: str) -> bool:
        """Check whether a relative file path matches the pattern.

        Matching is purely lexical, without filesystem access. A leading slash on
        the path is ignored.
        """
        path_parts = Path(relative_path.lstrip("/")).parts
        if path_parts[: len(self.prefix_parts)] != self.prefix_parts:
            return False
        remaining_parts = path_parts[len(self.prefix_parts) :]
        if self.file_name_regex is None:
            return remaining_parts == ()
        if not remaining_parts:
            return False
        *directories, file_name = remaining_parts
        if not self.file_name_regex.match(file_name):
            return False
        # each directory pattern consumes the directories up to the one it matches
        unmatched_directories = iter(directories)
        for regex in self.directory_regexes:
            if not any(regex.match(directory) for directory in unmatched_directories):
                return False
        return True


class PathPatternSet:
    """An ordered collection of compiled path patterns, indexed by literal prefix."""

    def __init__(self, patterns: Sequence[PathPattern]):
        self.patterns = tuple(patterns)
        self._indices_by_prefix: dict[tuple[str, ...], list[int]] = {}
        for index, pattern in enumerate(self.patterns):
            self._indices_by_prefix.setdefault(pattern.prefix_parts, []).append(index)

    @property
    def prefixes(self) -> set[tuple[str, ...]]:
        """Return the literal prefixes of the patterns."""
        return set(self._indices_by_prefix)

    def first_match(self, relative_path: str) -> int | None:
        """Return the index of the first pattern that matches a relative file path.

        Only the patterns whose literal prefix is an ancestor of the path are
        checked. Returns None if no pattern matches.
        """
        path_parts = Path(relative_path.lstrip("/")).parts
        candidate_indices = sorted(
            index
            for length in range(len(path_parts) + 1)
            for index in self._indices_by_prefix.get(path_parts[:length], ())
        )
        return next(
            (
                index
                for index in candidate_indices
                if self.patterns[index].matches(relative_path)
            ),
            None,
        )


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


def compile_path_pattern(relative_path_regexp: str) -> PathPattern:
    """Compile a relative path pattern.

    A leading slash on the pattern is ignored. Raises `re.error` if a segment is
    not a valid regular expression.
    """
    prefix, pattern = split_pattern_path(relative_path_regexp.lstrip("/"))
    if not pattern:
        return PathPattern(
            prefix_parts=prefix.parts, directory_regexes=(), file_name_regex=None
        )
    *directory_patterns, file_name_pattern = Path(pattern).parts
    # match rather than fullmatch, as `^a|b$` is not the same as `a|b` in full
    return PathPattern(
        prefix_parts=prefix.parts,
        directory_regexes=tuple(re.compile(f"^{p}$") for p in directory_patterns),
        file_name_regex=re.compile(f"^{file_name_pattern}$"),
    )


def path_matches_pattern(relative_path_regexp: str, relative_path: str) -> bool:
    """Check whether a relative file path matches a relative path pattern.

    Matching is purely lexical, without filesystem access. A leading slash on
    either argument is ignored. A pattern containing an invalid regular expression
    is logged and matches no path.
    """
    try:
        pattern = compile_path_pattern(relative_path_regexp)
    except re.error as err:
        logger.warning("Invalid path pattern %r: %s", relative_path_regexp, err)
        return False
    return pattern.matches(relative_path)


def _scan_directory(path: str) -> tuple[tuple[int, int], list[str], list[str]]:
    """List a directory's subdirectories and files, following symbolic links.

    Returns the directory's identity, as its device and inode numbers, along with
    the sorted names of its subdirectories and of its files.
    """
    stat_result = os.stat(path)
    directory_names = []
    file_names = []
    with os.scandir(path) as entries:
        for entry in entries:
            if entry.is_dir():
                directory_names.append(entry.name)
            elif entry.is_file():
                file_names.append(entry.name)
    return (
        (stat_result.st_dev, stat_result.st_ino),
        sorted(directory_names),
        sorted(file_names),
    )


async def iter_relative_file_paths(
    root: Path, prefixes: Collection[tuple[str, ...]]
) -> AsyncIterator[str]:
    """Yield the relative paths of the files under `root` within the given prefixes.

    Each prefix is a tuple of path segments, relative to `root`. Only the
    directories along or below some prefix are scanned, each one once even if
    symbolic links lead to it more than once. A directory that cannot be read is
    logged and skipped.
    """
    prefixes = set(prefixes)
    prefix_ancestors = {
        prefix[:length] for prefix in prefixes for length in range(len(prefix) + 1)
    }

    visited_directories = set()
    pending_directories: list[tuple[str, ...]] = [()]
    while pending_directories:
        directory_parts = pending_directories.pop()
        try:
            identity, directory_names, file_names = await to_thread.run_sync(
                _scan_directory, str(root.joinpath(*directory_parts))
            )
        except OSError as err:
            logger.warning(
                "Could not read directory %r: %s", "/".join(directory_parts), err
            )
            continue
        if identity in visited_directories:
            continue
        visited_directories.add(identity)
        for file_name in file_names:
            file_parts = (*directory_parts, file_name)
            if any(
                file_parts[:length] in prefixes for length in range(len(file_parts) + 1)
            ):
                yield "/".join(file_parts)
        # reversed, so that the stack yields the subdirectories in name order
        for directory_name in reversed(directory_names):
            subdirectory_parts = (*directory_parts, directory_name)
            if subdirectory_parts in prefix_ancestors or any(
                subdirectory_parts[:length] in prefixes
                for length in range(len(subdirectory_parts) + 1)
            ):
                pending_directories.append(subdirectory_parts)
