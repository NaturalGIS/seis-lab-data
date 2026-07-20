import datetime as dt
import logging
import math
import struct
from pathlib import Path

from .schemas import KmallMetadata

logger = logging.getLogger(__name__)

# numBytesDgm, dgmType, dgmVersion, systemID, echoSounderID, time_sec, time_nanosec
_DATAGRAM_HEADER = struct.Struct("<I4sBBHII")
# A datagram is at least the header plus the repeated length field at its tail.
_MIN_DATAGRAM_BYTES = _DATAGRAM_HEADER.size + 4
# #SPO is the primary position source; #CPO duplicates the same sensor feed
# (verified on the archive files) and only serves as a fallback.
_POSITION_DATAGRAMS = (b"#SPO", b"#CPO")
# The position datagram body starts with a common part whose length is the
# leading uint16; the sensor-data block after it opens with two uint32 times
# and a float32 fix quality, then the latitude/longitude doubles.
_SENSOR_DATA_LATLON_OFFSET = 12
_POSITION_BODY_BYTES = 64  # enough to reach the doubles in every revision seen


def extract_kmall_metadata(path: Path | str) -> KmallMetadata:
    """Extract metadata from a Kongsberg KMALL file by walking datagram headers.

    Reads only the 20-byte datagram headers plus the head of each position
    datagram - payloads are never loaded, so multi-GB files take seconds. A
    truncated tail (e.g. an acquisition crash) keeps the metadata gathered up
    to that point; a file whose first datagram is invalid raises ValueError.
    """
    p = Path(path)
    size = p.stat().st_size
    datagram_count = 0
    # running min/max, not first/last: real files interleave sensor datagrams
    # with header times backstepping up to ~3 s, which could shift a date at a
    # UTC midnight boundary
    min_time = max_time = None
    echo_sounder_id = None
    boxes: dict[bytes, tuple[float, float, float, float] | None] = {
        dgm_type: None for dgm_type in _POSITION_DATAGRAMS
    }
    fix_counts = {dgm_type: 0 for dgm_type in _POSITION_DATAGRAMS}

    with p.open("rb") as fh:
        position = 0
        while position + _DATAGRAM_HEADER.size <= size:
            fh.seek(position)
            (
                num_bytes,
                dgm_type,
                _dgm_version,
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
                    raise ValueError(f"{p.name} does not look like a KMALL file")
                logger.debug(
                    "Truncated or corrupt datagram at offset %d in %s - keeping "
                    "the metadata gathered so far",
                    position,
                    p,
                )
                break
            datagram_count += 1
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
        raise ValueError(f"{p.name} does not look like a KMALL file")

    bbox = None
    position_count = 0
    for dgm_type in _POSITION_DATAGRAMS:
        if boxes[dgm_type] is not None:
            bbox = boxes[dgm_type]
            position_count = fix_counts[dgm_type]
            break

    return KmallMetadata(
        driver="KMALL",
        # positions are geographic degrees from the GNSS feed; the format
        # declares no datum, WGS84-family in practice (sub-metre difference,
        # far below the bbox buffer) - documented approximation
        epsg=4326 if bbox is not None else None,
        crs_name="WGS 84" if bbox is not None else None,
        bbox_native=bbox,
        bbox_4326=bbox,
        temporal_extent_begin=_utc_date(min_time),
        temporal_extent_end=_utc_date(max_time),
        echo_sounder_id=echo_sounder_id,
        datagram_count=datagram_count,
        position_count=position_count,
    )


def _parse_position_fix(body: bytes) -> tuple[float, float] | None:
    """Best-effort (lon, lat) from a #SPO/#CPO body; None when unusable."""
    if len(body) < 2:
        return None
    (num_bytes_common,) = struct.unpack_from("<H", body, 0)
    offset = num_bytes_common + _SENSOR_DATA_LATLON_OFFSET
    if offset < 0 or offset + 16 > len(body):
        return None
    latitude, longitude = struct.unpack_from("<dd", body, offset)
    if not (math.isfinite(latitude) and math.isfinite(longitude)):
        return None
    if latitude == 0.0 and longitude == 0.0:
        # null-island fix from a GNSS dropout - one of these would blow the
        # bbox out to the equator
        return None
    if abs(latitude) > 90 or abs(longitude) > 180:
        # the spec uses out-of-range sentinels (e.g. 200.0) for "unavailable"
        return None
    return longitude, latitude


def _utc_date(timestamp: float | None) -> dt.date | None:
    if timestamp is None:
        return None
    return dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).date()
