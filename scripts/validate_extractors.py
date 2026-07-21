#!/usr/bin/env python3
"""Standalone extractor validation harness for production-side runs.

Walks archive files with header-only reads and writes a CSV report, one row per
file. Pure standard library on purpose: it must run on any python3 (e.g. the
production server) without installing anything, so it does NOT import the
seis_lab_data package. The KMALL parsing below mirrors
src/seis_lab_data/tasks/extractors/kmall.py - keep the two in sync.

Typical production run (read-only, low priority, resumable):

    nice -n 19 ionice -c3 python3 validate_extractors.py \
        --root /mnt/seislab_data/surveys \
        --extension .kmall \
        --output ~/kmall-report.csv \
        --resume

Interrupt at will; --resume skips files already present in the output.
"""

import argparse
import csv
import datetime as dt
import math
import os
import struct
import sys
import time

# numBytesDgm, dgmType, dgmVersion, systemID, echoSounderID, time_sec, time_nanosec
_DATAGRAM_HEADER = struct.Struct("<I4sBBHII")
_MIN_DATAGRAM_BYTES = _DATAGRAM_HEADER.size + 4
_POSITION_DATAGRAMS = (b"#SPO", b"#CPO")
_SENSOR_DATA_LATLON_OFFSET = 12
_POSITION_BODY_BYTES = 64

_CSV_COLUMNS = [
    "path",
    "size_bytes",
    "status",
    "error",
    "walk_seconds",
    "datagram_count",
    "position_count",
    "position_source",
    "echo_sounder_id",
    "dgm_versions",
    "min_lon",
    "min_lat",
    "max_lon",
    "max_lat",
    "date_begin",
    "date_end",
]


def validate_kmall(path):
    """Mirror of extract_kmall_metadata, returning a plain report dict."""
    size = os.path.getsize(path)
    datagram_count = 0
    min_time = max_time = None
    echo_sounder_id = None
    versions = {}
    boxes = {dgm_type: None for dgm_type in _POSITION_DATAGRAMS}
    fix_counts = {dgm_type: 0 for dgm_type in _POSITION_DATAGRAMS}

    with open(path, "rb") as fh:
        position = 0
        while position + _DATAGRAM_HEADER.size <= size:
            fh.seek(position)
            (
                num_bytes,
                dgm_type,
                dgm_version,
                _system_id,
                sounder_id,
                time_sec,
                time_nanosec,
            ) = _DATAGRAM_HEADER.unpack(fh.read(_DATAGRAM_HEADER.size))
            if (
                num_bytes < _MIN_DATAGRAM_BYTES
                or position + num_bytes > size
                or not dgm_type.startswith(b"#")
            ):
                if datagram_count == 0:
                    raise ValueError("does not look like a KMALL file")
                break
            datagram_count += 1
            versions.setdefault(dgm_type, set()).add(dgm_version)
            timestamp = time_sec + time_nanosec / 1e9
            if echo_sounder_id is None:
                echo_sounder_id = sounder_id
            min_time = timestamp if min_time is None else min(min_time, timestamp)
            max_time = timestamp if max_time is None else max(max_time, timestamp)
            if dgm_type in _POSITION_DATAGRAMS:
                body = fh.read(
                    min(num_bytes - _DATAGRAM_HEADER.size, _POSITION_BODY_BYTES)
                )
                fix = _parse_position_fix(body)
                if fix is not None:
                    lon, lat = fix
                    fix_counts[dgm_type] += 1
                    box = boxes[dgm_type]
                    boxes[dgm_type] = (
                        (lon, lat, lon, lat)
                        if box is None
                        else (
                            min(box[0], lon),
                            min(box[1], lat),
                            max(box[2], lon),
                            max(box[3], lat),
                        )
                    )
            position += num_bytes

    if datagram_count == 0:
        raise ValueError("does not look like a KMALL file")

    bbox = None
    position_count = 0
    position_source = ""
    for dgm_type in _POSITION_DATAGRAMS:
        if boxes[dgm_type] is not None:
            bbox = boxes[dgm_type]
            position_count = fix_counts[dgm_type]
            position_source = dgm_type.decode()
            break

    return {
        "datagram_count": datagram_count,
        "position_count": position_count,
        "position_source": position_source,
        "echo_sounder_id": echo_sounder_id,
        "dgm_versions": ";".join(
            f"{k.decode()}:{','.join(str(v) for v in sorted(vals))}"
            for k, vals in sorted(versions.items())
        ),
        "min_lon": bbox[0] if bbox else "",
        "min_lat": bbox[1] if bbox else "",
        "max_lon": bbox[2] if bbox else "",
        "max_lat": bbox[3] if bbox else "",
        "date_begin": _utc_date(min_time),
        "date_end": _utc_date(max_time),
    }


def _parse_position_fix(body):
    if len(body) < 2:
        return None
    (num_bytes_common,) = struct.unpack_from("<H", body, 0)
    offset = num_bytes_common + _SENSOR_DATA_LATLON_OFFSET
    if offset + 16 > len(body):
        return None
    latitude, longitude = struct.unpack_from("<dd", body, offset)
    if not (math.isfinite(latitude) and math.isfinite(longitude)):
        return None
    if latitude == 0.0 and longitude == 0.0:
        return None
    if abs(latitude) > 90 or abs(longitude) > 180:
        return None
    return longitude, latitude


def _utc_date(timestamp):
    if timestamp is None:
        return ""
    return dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).date().isoformat()


_VALIDATORS = {
    ".kmall": validate_kmall,
    # ".sgy"/".segy" arrive with the SEG-Y extractor - same pattern
}


def iter_target_files(root, extension, file_list):
    if file_list:
        with open(file_list) as fh:
            for line in fh:
                candidate = line.rstrip("\n").split("\t")[-1]
                if candidate.lower().endswith(extension):
                    yield os.path.join(root, candidate.lstrip("./"))
    else:
        for dirpath, _dirnames, filenames in os.walk(root):
            for name in sorted(filenames):
                if name.lower().endswith(extension):
                    yield os.path.join(dirpath, name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="archive root directory")
    parser.add_argument("--extension", default=".kmall", choices=sorted(_VALIDATORS))
    parser.add_argument("--output", required=True, help="CSV report path")
    parser.add_argument(
        "--file-list",
        help="optional listing (plain paths, or size<TAB>path); paths are "
        "resolved against --root; when absent the root is walked",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="skip files already present in the output CSV",
    )
    parser.add_argument("--limit", type=int, help="stop after N files (trial runs)")
    args = parser.parse_args()

    validator = _VALIDATORS[args.extension]
    done = set()
    if args.resume and os.path.exists(args.output):
        with open(args.output) as fh:
            done = {row["path"] for row in csv.DictReader(fh)}

    mode = "a" if done else "w"
    processed = ok = failed = 0
    with open(args.output, mode, newline="") as out:
        writer = csv.DictWriter(out, fieldnames=_CSV_COLUMNS)
        if mode == "w":
            writer.writeheader()
        for path in iter_target_files(args.root, args.extension, args.file_list):
            relative = os.path.relpath(path, args.root)
            if relative in done:
                continue
            row = {"path": relative}
            started = time.perf_counter()
            try:
                row["size_bytes"] = os.path.getsize(path)
                row.update(validator(path))
                row["status"] = "ok"
                ok += 1
            except Exception as err:  # report and carry on - this is a survey
                row["status"] = "error"
                row["error"] = f"{type(err).__name__}: {err}"
                failed += 1
            row["walk_seconds"] = f"{time.perf_counter() - started:.2f}"
            writer.writerow(row)
            out.flush()
            processed += 1
            if processed % 50 == 0:
                print(
                    f"{processed} files ({ok} ok, {failed} errors)...",
                    file=sys.stderr,
                    flush=True,
                )
            if args.limit and processed >= args.limit:
                break

    print(f"done: {processed} files, {ok} ok, {failed} errors", file=sys.stderr)


if __name__ == "__main__":
    main()
