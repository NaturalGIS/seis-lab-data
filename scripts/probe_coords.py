#!/usr/bin/env python3
"""Dump the sampled src/cdp coordinates of one or more SEG-Y files.

A read-only, standard-library forensic probe. It reads exactly the ~100 sampled
trace headers the extractor uses (segy.py) and prints, separately for the src
and cdp fields, how the scalco-scaled coordinates are distributed. The point is
to tell apart the two junk-navigation modes the archive holds:

  - a tight cluster with a few wild outliers  -> a REAL line stretched by a
    burst of bad-nav traces (the box should be discarded, the file is real);
  - a broad spread across many values         -> the coordinate field itself is
    noise (true junk navigation).

Stream it to a host that holds the files, so nothing is written there:

    ssh <host> "python3 - /path/a.sgy /path/b.sgy" < scripts/probe_coords.py

Usage:  python3 scripts/probe_coords.py <file.sgy> [<file2.sgy> ...]
"""

import argparse
import os
import statistics
import struct
import sys

_TEXTUAL = 3200
_BINHDR = 400
_TRHDR = 240
_DATA_START = _TEXTUAL + _BINHDR
_SAMPLE_TARGET = 100
_INT32_SENTINELS = (-(2**31), 2**31 - 1)
_SAMPLE_FORMATS = {1: 4, 2: 4, 3: 2, 5: 4, 6: 8, 8: 1, 10: 4, 11: 2, 16: 1}

# binary: sample_interval(16) samples_per_trace(20) sample_format(24) rev(300)
#         ext_header_count(304) extra_trace_headers(306)
_BIN_FMT = "16x H 2x H 2x H 274x H 2x h i"
_BIN = {">": struct.Struct(">" + _BIN_FMT), "<": struct.Struct("<" + _BIN_FMT)}
# trace: scalco(70) src_x(72) src_y(76) units(88) ... cdp_x(180) cdp_y(184)
_TR_FMT = "70x h i i 8x H 66x H H H H H 14x i i"
_TR = {">": struct.Struct(">" + _TR_FMT), "<": struct.Struct("<" + _TR_FMT)}


def scale(value, scalco):
    if scalco < 0:
        return value / -scalco
    if scalco > 0:
        return float(value * scalco)
    return float(value)


def sample_indices(n):
    if n <= _SAMPLE_TARGET:
        return list(range(n))
    last = n - 1
    return sorted({s * last // (_SAMPLE_TARGET - 1) for s in range(_SAMPLE_TARGET)})


def summarise(name, xs, ys):
    if not xs:
        print(f"    {name}: no usable points")
        return
    for axis, vals in (("x", xs), ("y", ys)):
        vals = sorted(vals)
        med = statistics.median(vals)
        near = sum(1 for v in vals if abs(v - med) <= 5000)
        print(
            f"    {name}.{axis}: n={len(vals):3d} min={vals[0]:12.1f} "
            f"med={med:12.1f} max={vals[-1]:12.1f}  "
            f"within5km_of_med={near} outliers={len(vals) - near}"
        )


def probe(path):
    size = os.path.getsize(path)
    print(f"\n{path}  ({size} bytes)")
    with open(path, "rb") as fh:
        fh.seek(_TEXTUAL)
        buf = fh.read(_BINHDR)
        order = None
        for candidate in (">", "<"):
            si, spt, fmt, rev, exth, extra = _BIN[candidate].unpack_from(buf)
            if 1 <= fmt <= 16:
                order = candidate
                break
        if order is None:
            print("    not a recognisable SEG-Y binary header")
            return
        bps = _SAMPLE_FORMATS.get(fmt)
        rev_major = rev >> 8 if rev > 0xFF else rev
        print(
            f"    order={order!r} fmt={fmt} bytes/sample={bps} "
            f"samples/trace={spt} rev={rev_major}"
        )
        if not bps or spt == 0:
            print("    cannot locate traces (unknown format or samples/trace 0)")
            return
        data_start = _DATA_START
        if (
            rev_major >= 1
            and 0 < exth <= 100
            and _DATA_START + exth * _TEXTUAL + _TRHDR <= size
        ):
            data_start = _DATA_START + exth * _TEXTUAL
        tlen = _TRHDR + spt * bps
        ntr = (size - data_start) // tlen
        print(f"    trace_count={ntr}")
        srcx, srcy, cdpx, cdpy = [], [], [], []
        scalcos, unit_codes = set(), set()
        for index in sample_indices(ntr):
            fh.seek(data_start + index * tlen)
            b = fh.read(_TRHDR)
            if len(b) < _TR[order].size:
                break
            scalco, sx, sy, units, *_rest, cx, cy = _TR[order].unpack_from(b)
            scalcos.add(scalco)
            unit_codes.add(units)
            if (
                sx not in _INT32_SENTINELS
                and sy not in _INT32_SENTINELS
                and not (sx == 0 and sy == 0)
            ):
                srcx.append(scale(sx, scalco))
                srcy.append(scale(sy, scalco))
            if (
                cx not in _INT32_SENTINELS
                and cy not in _INT32_SENTINELS
                and not (cx == 0 and cy == 0)
            ):
                cdpx.append(scale(cx, scalco))
                cdpy.append(scale(cy, scalco))
        print(
            f"    scalco seen={sorted(scalcos)}  units codes seen={sorted(unit_codes)}"
        )
        summarise("src", srcx, srcy)
        summarise("cdp", cdpx, cdpy)
        print(
            "    READING: within5km_of_med high + few outliers => real line + bad traces;"
        )
        print(
            "             values spread across many => the field itself is noise (junk)."
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", help="SEG-Y files to probe")
    args = parser.parse_args()
    for path in args.files:
        try:
            probe(path)
        except Exception as err:  # a survey - report and carry on
            print(f"\n{path}\n    ERROR {type(err).__name__}: {err}", file=sys.stderr)


if __name__ == "__main__":
    main()
