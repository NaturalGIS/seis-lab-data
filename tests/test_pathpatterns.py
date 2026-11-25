"""Path patterns of the asset discovery configuration

Asset discovery finds the files of a survey mission by matching their paths in the
archive against the path patterns of the asset discovery configuration. Only the
directories named by the patterns are searched, and the archive is divided into sections
that are processed in a consistent order.
"""

import re

import anyio
import pytest

from seis_lab_data import pathpatterns


@pytest.mark.parametrize(
    "relative_path_regexp, relative_path, expected",
    [
        pytest.param(r"s01/.*\.tif", "s01/a/b/x.tif", True, id="any depth"),
        pytest.param(r"s01/.*\.tif", "s02/s01/x.tif", False, id="fixed prefix"),
        pytest.param(r"s01/.*\.tif", "s01/x.tif.aux.xml", False, id="anchored name"),
        pytest.param(r".*_Data/.*\.kmall", "02_Data/x/f.kmall", True, id="directory"),
        pytest.param(r".*_Data/.*\.kmall", "f.kmall", False, id="missing directory"),
        pytest.param("s01/grid.tif", "s01/grid.tif", True, id="literal"),
        pytest.param(r"/s01/.*\.tif", "s01/x.tif", True, id="leading slash"),
        pytest.param(r"s01/(.*\.tif", "s01/x.tif", False, id="invalid regexp"),
        pytest.param(r"s01/.*\.se?gy", "s01/x.segy", True, id="similar extension"),
        pytest.param(r"s01/.*\.se?gy", "s01/x.sgy", True, id="similar extension 2"),
        pytest.param(
            r"(s08|s10)/raw/.*\.sgy", "s10/raw/x.sgy", True, id="alternative paths"
        ),
        pytest.param(
            r"x/s08|s10/.*\.sgy", "x/s08-old/y.sgy", False, id="directory alternatives"
        ),
        pytest.param(
            r"x/s08|s10/.*\.sgy",
            "x/old-s10/y.sgy",
            False,
            id="directory alternatives 2",
        ),
        pytest.param(
            r"x/s10/.*\.sgy|segy", "x/s10/y.segy", False, id="name alternatives"
        ),
        pytest.param(
            r"x/s10/a\.sgy|segy", "x/s10/a.sgy.bak", False, id="name alternatives 2"
        ),
    ],
)
def test_path_matches_pattern(relative_path_regexp, relative_path, expected):
    """A file path matches a path pattern only when the whole path, from its first
    directory to the end of the file name, fits the pattern; a leading slash in the
    pattern is ignored, and an invalid pattern matches nothing. Alternatives within a
    directory or file name always apply to the whole name.
    """
    assert (
        pathpatterns.path_matches_pattern(relative_path_regexp, relative_path)
        is expected
    )


def test_compile_path_pattern_rejects_an_invalid_regexp():
    """An invalid path pattern is reported as an error."""
    with pytest.raises(re.error):
        pathpatterns.compile_path_pattern(r"s01/(.*\.tif")


async def _collect_relative_file_paths(root, *relative_path_regexps):
    pattern_set = pathpatterns.PathPatternSet(
        [pathpatterns.compile_path_pattern(p) for p in relative_path_regexps]
    )
    return [
        relative_path
        async for relative_path in pathpatterns.iter_relative_file_paths(
            anyio.Path(root), pattern_set.prefixes
        )
    ]


@pytest.fixture
def file_tree(tmp_path):
    """Create empty files in two survey directories and at the root, plus a symlink loop
    in `s01`.
    """
    for relative_path in ("s01/a.tif", "s01/sub/b.tif", "s02/c.tif", "d.tif"):
        (tmp_path / relative_path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative_path).write_bytes(b"")
    # a loop, which must be followed only once
    (tmp_path / "s01/loop").symlink_to(tmp_path / "s01")
    return tmp_path


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "relative_path_regexps, expected",
    [
        pytest.param(
            [r"s01/.*\.tif"], ["s01/a.tif", "s01/sub/b.tif"], id="literal prefix"
        ),
        pytest.param(
            [r".*\.tif"],
            ["d.tif", "s01/a.tif", "s01/sub/b.tif", "s02/c.tif"],
            id="no literal prefix",
        ),
        pytest.param(["s02/c.tif"], ["s02/c.tif"], id="literal path"),
        pytest.param(
            [r"s01/sub/.*\.tif", r"s02/.*\.tif"],
            ["s01/sub/b.tif", "s02/c.tif"],
            id="several prefixes",
        ),
        pytest.param([r"s99/.*\.tif"], [], id="missing directory"),
    ],
)
async def test_iter_relative_file_paths(file_tree, relative_path_regexps, expected):
    """Searching the archive finds every file below the fixed leading directories of the
    path patterns, or in the whole archive when a pattern has none, and finds nothing
    for a directory that does not exist. A directory reached again through a symbolic
    link is searched only once.
    """
    found = await _collect_relative_file_paths(file_tree, *relative_path_regexps)

    assert sorted(found) == expected


@pytest.mark.parametrize(
    "relative_path, expected",
    [
        pytest.param("s01/sub/x.tif", 0, id="first of several matches"),
        pytest.param("s01/x.txt", 1, id="only match"),
        pytest.param("s02/x.tif", 2, id="no literal prefix"),
        pytest.param("s02/x.txt", None, id="no match"),
    ],
)
def test_path_pattern_set_first_match(relative_path, expected):
    """When several path patterns match a file path, the first of them in the
    configuration applies, and a path that matches none is left unmatched.
    """
    pattern_set = pathpatterns.PathPatternSet(
        [
            pathpatterns.compile_path_pattern(p)
            for p in (r"s01/.*\.tif", r"s01/.*", r".*\.tif")
        ]
    )

    assert pattern_set.first_match(relative_path) == expected


@pytest.fixture
def sectioned_tree(tmp_path):
    """Create empty files at the root and in three top-level directories, mixing files
    and subdirectories.
    """
    for relative_path in (
        "root.tif",
        "s01/a.tif",
        "s01/sub/b.tif",
        "s02/z-file",
        "s02/a-dir/c.tif",
        "s03/d.tif",
    ):
        (tmp_path / relative_path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative_path).write_bytes(b"")
    return tmp_path


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "relative_path_regexps, expected",
    [
        pytest.param(
            [r"s01/sub/.*\.tif", r"s01/.*\.tif", r"s03/.*\.tif"],
            [("s01",), ("s03",)],
            id="nested prefixes fold",
        ),
        pytest.param(
            [r"s99/.*\.tif", r"s03/.*\.tif"], [("s03",)], id="missing prefix dropped"
        ),
        pytest.param(
            [r".*\.tif", r"s01/.*\.tif"],
            [("s01",), ("s02",), ("s03",)],
            id="root prefix replaced by its subdirectories",
        ),
        pytest.param(
            [r"s02/a-dir/.*\.tif", "s02/z-file"],
            [("s02", "z-file"), ("s02", "a-dir")],
            id="a directory's files come before its subdirectories",
        ),
        pytest.param([r"s99/.*\.tif"], [], id="no section"),
    ],
)
async def test_list_path_groups(sectioned_tree, relative_path_regexps, expected):
    """The archive is divided into sections, one for each existing leading directory or
    file named by the path patterns, with nested directories included in their parent's
    section and missing ones left out. A pattern without a fixed leading directory gives
    one section per top-level directory, and within a directory, files come before
    subdirectories.
    """
    pattern_set = pathpatterns.PathPatternSet(
        [pathpatterns.compile_path_pattern(p) for p in relative_path_regexps]
    )

    groups = await pathpatterns.list_path_groups(
        anyio.Path(sectioned_tree), pattern_set.prefixes
    )

    assert [group.parts for group in groups] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "relative_path_regexps",
    [
        pytest.param([r".*\.tif"], id="root prefix"),
        pytest.param(
            [r"s02/a-dir/.*\.tif", "s02/z-file", r"s01/.*\.tif", r"s03/.*\.tif"],
            id="file and directory prefixes",
        ),
    ],
)
async def test_list_path_groups_follows_the_walk_order(
    sectioned_tree, relative_path_regexps
):
    """The archive search finds files in the same order as its sections, so that each
    section is completed before the next one begins.
    """
    pattern_set = pathpatterns.PathPatternSet(
        [pathpatterns.compile_path_pattern(p) for p in relative_path_regexps]
    )
    groups = await pathpatterns.list_path_groups(
        anyio.Path(sectioned_tree), pattern_set.prefixes
    )

    walked = await _collect_relative_file_paths(sectioned_tree, *relative_path_regexps)

    # the walk goes through the groups in order, and its paths sort by walk key
    walked_keys = [
        pathpatterns.build_walk_order_key(path.split("/"), is_file=True)
        for path in walked
    ]
    assert walked_keys == sorted(walked_keys)
    walked_groups = [
        next(
            index
            for index, group in enumerate(groups)
            if tuple(path.split("/")[: len(group.parts)]) == group.parts
        )
        for path in walked
        if path != "root.tif"
    ]
    assert walked_groups == sorted(walked_groups)
