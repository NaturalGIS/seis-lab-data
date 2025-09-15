"""
Standalone script to create MBTiles file from a directory of PNG tiles
organized in the standard `z/x/y` format.
"""

import argparse
import dataclasses
import json
import logging
import math
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class LatLonBoundingBox:
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


@dataclasses.dataclass
class ZoomInfo:
    zoom: int
    lon: float
    lat: float


@dataclasses.dataclass
class TilesInfo:
    bounds: LatLonBoundingBox
    center: ZoomInfo
    min_zoom: int
    max_zoom: int
    total_tiles: int


@dataclasses.dataclass
class TilesMinimalMetadata:
    name: str
    attribution: str
    type: str
    version: str
    description: str


def tile_to_lat_lon_bbox(x: int, y: int, z: int) -> LatLonBoundingBox:
    n = 2.0**z
    lon_deg_min = x / n * 360.0 - 180.0
    lon_deg_max = (x + 1) / n * 360.0 - 180.0
    lat_rad_min = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n)))
    lat_rad_max = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat_deg_min = math.degrees(lat_rad_min)
    lat_deg_max = math.degrees(lat_rad_max)
    return LatLonBoundingBox(
        min_lon=lon_deg_min,
        min_lat=lat_deg_min,
        max_lon=lon_deg_max,
        max_lat=lat_deg_max,
    )


def parse_metadata(metadata_path: Path) -> TilesMinimalMetadata:
    parsed = json.loads(metadata_path.read_text())
    return TilesMinimalMetadata(**parsed)


def discover_bounds_and_zoom(tiles_dir: Path) -> TilesInfo:
    min_lon, min_lat = float("inf"), float("inf")
    max_lon, max_lat = float("-inf"), float("-inf")
    zoom_levels = []
    total_tiles = 0

    logger.info("Analyzing tiles to discover bounds...")

    for z_dir in sorted(tiles_dir.iterdir()):
        if not z_dir.is_dir():
            continue

        z = int(z_dir.name)
        zoom_levels.append(z)

        for x_dir in sorted(z_dir.iterdir()):
            if not x_dir.is_dir():
                continue

            x = int(x_dir.name)

            for tile_file in sorted(x_dir.glob("*.png")):
                y = int(tile_file.stem)
                total_tiles += 1

                tile_bbox = tile_to_lat_lon_bbox(x, y, z)

                min_lon = min(min_lon, tile_bbox.min_lon)
                min_lat = min(min_lat, tile_bbox.min_lat)
                max_lon = max(max_lon, tile_bbox.max_lon)
                max_lat = max(max_lat, tile_bbox.max_lat)

    center_lon = (min_lon + max_lon) / 2
    center_lat = (min_lat + max_lat) / 2
    center_zoom = min(zoom_levels) + (max(zoom_levels) - min(zoom_levels)) // 2

    return TilesInfo(
        bounds=LatLonBoundingBox(
            min_lon=min_lon, min_lat=min_lat, max_lon=max_lon, max_lat=max_lat
        ),
        center=ZoomInfo(zoom=center_zoom, lon=center_lon, lat=center_lat),
        min_zoom=min(zoom_levels),
        max_zoom=max(zoom_levels),
        total_tiles=total_tiles,
    )


def create_mbtiles_from_png_tiles(tiles_dir: Path, output_path: Path):
    if (metadata_path := tiles_dir / "metadata.json").is_file():
        initial_metadata = parse_metadata(metadata_path)
        logger.info(f"{initial_metadata=}")
    else:
        raise RuntimeError("Missing metadata.json file")

    tiles_info = discover_bounds_and_zoom(tiles_dir)
    logger.info(f"{tiles_info=}")

    conn = sqlite3.connect(output_path)
    conn.execute(
        """
        CREATE TABLE metadata
        (
            name  text,
            value text
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE tiles
        (
            zoom_level  integer,
            tile_column integer,
            tile_row    integer,
            tile_data   blob
        );
        """
    )

    metadata = {
        "name": initial_metadata.name,
        "type": initial_metadata.type,
        "version": initial_metadata.version,
        "description": initial_metadata.description,
        "format": "png",
        "bounds": (
            f"{tiles_info.bounds.min_lon},{tiles_info.bounds.min_lat},"
            f"{tiles_info.bounds.max_lon},{tiles_info.bounds.max_lat}"
        ),
        "center": f"{tiles_info.center.lon},{tiles_info.center.lat},{tiles_info.center.zoom}",
        "minzoom": str(tiles_info.min_zoom),
        "maxzoom": str(tiles_info.max_zoom),
        "attribution": initial_metadata.attribution,
    }

    for name, value in metadata.items():
        conn.execute("INSERT INTO metadata VALUES (?, ?)", (name, value))

    tile_count = 0

    for z_dir in sorted(tiles_dir.iterdir()):
        if not z_dir.is_dir():
            continue

        z = int(z_dir.name)
        logger.info(f"Processing zoom level {z}")

        for x_dir in sorted(z_dir.iterdir()):
            if not x_dir.is_dir():
                continue

            x = int(x_dir.name)
            logger.debug(f"Processing x level {x}")

            for tile_file in sorted(x_dir.glob("*.png")):
                y = int(tile_file.stem)
                logger.debug(f"Processing y level {y}")

                with open(tile_file, "rb") as fh:
                    tile_data = fh.read()

                # MBTiles uses TMS scheme, so we need to flip Y coordinate
                # For web mercator: tms_y = (2^z - 1) - y
                tms_y = (2**z - 1) - y

                conn.execute(
                    """
                    INSERT INTO tiles (zoom_level, tile_column, tile_row, tile_data)
                    VALUES (?, ?, ?, ?)
                    """,
                    (z, x, tms_y, tile_data),
                )

                tile_count += 1
                if tile_count % 100 == 0:
                    print(f"Processed {tile_count} tiles")

    conn.execute(
        "CREATE UNIQUE INDEX tile_index ON tiles (zoom_level, tile_column, tile_row);"
    )

    conn.commit()
    conn.close()

    print(f"Successfully created {output_path!r} with {tile_count} tiles")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("tiles_dir", type=Path, help="Directory containing PNG tiles")
    parser.add_argument("output_path", type=Path, help="Output path for MBTiles file")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    create_mbtiles_from_png_tiles(args.tiles_dir, args.output_path)
