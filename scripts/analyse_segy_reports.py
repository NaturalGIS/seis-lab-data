#!/usr/bin/env python3
"""Analyse the CSV reports produced by validate_extractors.py for SEG-Y.

Reads every CSV in a reports directory (one per chunk, same header) and prints
the checks agreed for the archive scan, so the analysis is reproducible instead
of ad-hoc. Pure standard library, like the validator itself. The rules encoded
here are the ones the extractor's coverage/bbox decisions rest on, so a fresh
archive scan can be re-audited the same way:

  - geographic files (the only ones that draw a map rectangle) by units code,
    never by a non-empty min_lon;
  - every row with garbage_count > 0, and every bbox built from a sliver of
    accepted points;
  - metres-box magnitude per family, so a mis-scaled folder stands out;
  - partial-metadata rows by signature, errors split by size, suspect dates.

Usage:  python3 scripts/analyse_segy_reports.py --reports <dir> [--top N]
"""

import argparse
import collections
import csv
import datetime as dt
import glob
import os

# Portugal geographic window: a loose sanity box, deliberately wide enough for
# the whole EEZ (real deep-water lines reach lon -15.7), so "outside" is a
# prompt to look, not a verdict.
GEO_LON = (-16.0, -5.0)
GEO_LAT = (34.0, 44.0)
# Loose projected-metres envelope for an offshore-Portugal survey (TM06-centric;
# UTM rows legitimately fall outside, which the per-family view separates out).
MET_X = (-400_000.0, 400_000.0)
MET_Y = (-500_000.0, 800_000.0)
SMALL_ACCEPTED = 5
GEO_UNIT_LABELS = {"arc-seconds", "degrees", "dms"}


def fnum(s):
    if s is None or s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def units_has_geographic(units_counts):
    # units_counts like "1:98;2:2" - a code 2 (arc-seconds), 3 (degrees) or
    # 4 (dms) token means at least one geographic trace was sampled.
    for token in units_counts.split(";"):
        if token and token.split(":", 1)[0] in ("2", "3", "4"):
            return True
    return False


def folder_key(path, depth=3):
    return "/".join(path.split("/")[:depth])


def load_reports(reports_dir):
    rows = []
    for path in sorted(glob.glob(os.path.join(reports_dir, "*.csv"))):
        chunk = os.path.basename(path)[:-4]
        with open(path) as fh:
            for row in csv.DictReader(fh):
                row["_chunk"] = chunk
                rows.append(row)
    return rows


def section(title):
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reports", required=True, help="directory of validate_extractors CSVs"
    )
    parser.add_argument(
        "--top", type=int, default=25, help="max rows to list per finding"
    )
    args = parser.parse_args()

    rows = load_reports(args.reports)
    if not rows:
        parser.error(f"no CSV reports found in {args.reports}")
    ok = [r for r in rows if r["status"] == "ok"]
    err = [r for r in rows if r["status"] == "error"]

    section("PER-CHUNK COUNTS")
    per_chunk = collections.Counter(r["_chunk"] for r in rows)
    for chunk in sorted(per_chunk):
        chunk_rows = [r for r in rows if r["_chunk"] == chunk]
        n_ok = sum(1 for r in chunk_rows if r["status"] == "ok")
        n_er = sum(1 for r in chunk_rows if r["status"] == "error")
        print(f"  {chunk:24s} {len(chunk_rows):6d} rows  {n_ok:6d} ok  {n_er:3d} err")
    print(f"  {'TOTAL':24s} {len(rows):6d} rows  {len(ok):6d} ok  {len(err):3d} err")

    # ---- geographic files (the only ones that draw a map rectangle) ------
    section("GEOGRAPHIC FILES (units code 2/3/4 present, or geographic label)")
    geo = [
        r
        for r in ok
        if units_has_geographic(r.get("units_counts", ""))
        or r.get("coordinate_units", "") in GEO_UNIT_LABELS
    ]
    print(f"  {len(geo)} of {len(ok)} ok rows carry any geographic trace")
    for r in geo[: args.top]:
        lo, la, xo, xa = (
            fnum(r["min_lon"]),
            fnum(r["min_lat"]),
            fnum(r["max_lon"]),
            fnum(r["max_lat"]),
        )
        window = ""
        if None not in (lo, la, xo, xa):
            inside = (
                GEO_LON[0] <= lo <= GEO_LON[1]
                and GEO_LON[0] <= xo <= GEO_LON[1]
                and GEO_LAT[0] <= la <= GEO_LAT[1]
                and GEO_LAT[0] <= xa <= GEO_LAT[1]
            )
            window = " window:OK" if inside else " window:OUTSIDE(suspect)"
        print(
            f"    [{r['_chunk']}] units={r['units_counts']!r} cov={r['coverage']}"
            f" lonlat=({r['min_lon']},{r['min_lat']})..({r['max_lon']},{r['max_lat']})"
            f"{window}  {r['path']}"
        )

    # ---- units distribution ---------------------------------------------
    section("UNITS: dominant coordinate_units across ok rows")
    for label, n in collections.Counter(
        r.get("coordinate_units", "") or "(none)" for r in ok
    ).most_common():
        print(f"  {label:18s} {n:6d}")

    # ---- garbage / partial coverage (junk-navigation net) ---------------
    section("GARBAGE / PARTIAL COVERAGE")
    garb = [r for r in ok if (fnum(r.get("garbage_count")) or 0) > 0]
    partial = [r for r in ok if r.get("coverage") == "partial"]
    print(f"  garbage_count > 0 : {len(garb)}    coverage=partial : {len(partial)}")
    hist = collections.Counter(int(fnum(r.get("garbage_count")) or 0) for r in ok)
    print("  garbage_count histogram:", {k: hist[k] for k in sorted(hist)})
    for tag, group in (("garbage>0", garb), ("partial", partial)):
        clusters = collections.Counter(folder_key(r["path"]) for r in group)
        if clusters:
            print(f"  {tag} by folder (3-seg):")
            for folder, n in clusters.most_common(args.top):
                print(f"    {n:5d}  {folder}")

    # ---- small-support bboxes (accepted below the flag floor) -----------
    section(f"SMALL-SUPPORT BBOXES (0 < accepted_count < {SMALL_ACCEPTED}, box kept)")
    small = [
        r
        for r in ok
        if 0 < (fnum(r.get("accepted_count")) or 0) < SMALL_ACCEPTED
        and (r.get("native_min_x") or r.get("min_lon"))
    ]
    print(f"  {len(small)} rows")
    for r in small[: args.top]:
        print(
            f"    a={r['accepted_count']} p={r['parsed_count']} "
            f"({r['native_min_x']},{r['native_min_y']})"
            f"..({r['native_max_x']},{r['native_max_y']}) {r['path']}"
        )

    # ---- metres-box magnitude, per family -------------------------------
    section("METRES BBOX MAGNITUDE (per-family centres; envelope outliers)")
    metres = [
        r
        for r in ok
        if r.get("coordinate_units") in ("metres", "unset") and r.get("native_min_x")
    ]
    outliers = 0
    families = collections.defaultdict(list)
    for r in metres:
        x0, y0, x1, y1 = (
            fnum(r["native_min_x"]),
            fnum(r["native_min_y"]),
            fnum(r["native_max_x"]),
            fnum(r["native_max_y"]),
        )
        if None in (x0, y0, x1, y1):
            continue
        if not (
            MET_X[0] <= x0 and x1 <= MET_X[1] and MET_Y[0] <= y0 and y1 <= MET_Y[1]
        ):
            outliers += 1
        families[folder_key(r["path"], 2)].append(((x0 + x1) / 2, (y0 + y1) / 2))
    print(f"  {len(metres)} metres/unset boxes; {outliers} outside the loose envelope")
    for family in sorted(families):
        centres = families[family]
        xs = sorted(c[0] for c in centres)
        ys = sorted(c[1] for c in centres)
        print(
            f"    {family:28s} n={len(centres):5d}  "
            f"x[{xs[0]:>12.0f}..{xs[-1]:>12.0f}]  y[{ys[0]:>12.0f}..{ys[-1]:>12.0f}]"
        )

    # ---- partial-metadata rows by signature -----------------------------
    section("PARTIAL-METADATA (ok rows with no bbox) by signature")
    nobbox = [r for r in ok if not r.get("native_min_x") and not r.get("min_lon")]
    sig = collections.Counter()
    example = {}
    for r in nobbox:
        fmt, spt, tc = (
            r.get("sample_format", ""),
            r.get("samples_per_trace", ""),
            r.get("trace_count", ""),
        )
        if fmt.startswith("format code") or fmt.startswith("format "):
            key = "unknown-sample-format"
        elif spt == "":
            key = "samples_per_trace=0"
        elif tc == "":
            key = "rev2-bailout-or-no-traces"
        elif (fnum(tc) or 0) == 0:
            key = "trace_count=0"
        else:
            key = "no-usable-navigation"
        sig[key] += 1
        example.setdefault(key, r)
    print(f"  {len(nobbox)} ok rows without any bbox")
    for key, n in sig.most_common():
        print(f"    {n:6d}  {key}  e.g. {example[key]['path']}")

    # ---- errors, split by size ------------------------------------------
    section("ERRORS split by size_bytes")
    too_small = [r for r in err if (fnum(r.get("size_bytes")) or 0) < 3840]
    unrecognised = [r for r in err if (fnum(r.get("size_bytes")) or 0) >= 3840]
    print(f"  < 3840 bytes (too small / empty) : {len(too_small)}")
    for r in too_small[: args.top]:
        print(f"    size={r['size_bytes']} {r['path']}")
    print(f"  >= 3840 (header unrecognised)     : {len(unrecognised)}")
    for r in unrecognised[: args.top]:
        print(f"    size={r['size_bytes']} {r['path']}")

    # ---- suspect dates --------------------------------------------------
    section("DATES: date_begin before 2016 or span > 60 days")
    suspect = []
    for r in ok:
        begin = r.get("date_begin", "")
        if not begin:
            continue
        try:
            d0 = dt.date.fromisoformat(begin)
            d1 = dt.date.fromisoformat(r["date_end"]) if r.get("date_end") else d0
        except ValueError:
            continue
        if d0.year < 2016 or (d1 - d0).days > 60:
            suspect.append((r, d0, d1))
    print(f"  {len(suspect)} suspect")
    for r, d0, d1 in suspect[: args.top]:
        print(f"    {d0}..{d1} ({(d1 - d0).days}d) {r['path']}")


if __name__ == "__main__":
    main()
