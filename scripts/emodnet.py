"""Standalone script to download EMODNet bathymetry tiles."""

import argparse
import asyncio
import dataclasses
import enum
import json
import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class TilesMinimalMetadata:
    name: str
    attribution: str
    type: str
    version: str
    description: str


def _setup_logging(level: int = logging.INFO):
    logging.basicConfig(level=level)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


class DownloadStatus(enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


EMODNET_TILE_DOWNLOAD_TEMPLATE = (
    "https://tiles.emodnet-bathymetry.eu/2020/"
    "{layer_id}/{tile_matrix_set}/{z}/{x}/{y}.png"
)


def get_tile_ranges(max_zoom_level: int = 6) -> dict[int, tuple[int, int, int, int]]:
    result = {}
    for zoom_level in range(max_zoom_level + 1):
        num_tiles = 2**zoom_level
        result[zoom_level] = (0, num_tiles - 1, 0, num_tiles - 1)
    return result


async def download_tile(
    client: httpx.AsyncClient, url: str, file_path: Path
) -> tuple[DownloadStatus, Path]:
    if file_path.exists() and file_path.stat().st_size > 0:
        return DownloadStatus.SKIPPED, file_path
    try:
        response = await client.get(url)
        response.raise_for_status()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:
            async for chunk in response.aiter_bytes():
                f.write(chunk)
            return DownloadStatus.SUCCESS, file_path
    except httpx.RequestError as e:
        logger.warning(f"Error downloading {url!r}: {e}")
        return DownloadStatus.FAILED, file_path


def generate_metadata_file(
    tiles_root_dir: Path, metadata: TilesMinimalMetadata
) -> Path:
    output_path = tiles_root_dir / "metadata.json"
    if output_path.exists():
        logger.info(
            f"Metadata file {output_path!r} already exists, skipping generation..."
        )
        return output_path
    with output_path.open("w") as fh:
        json.dump(dataclasses.asdict(metadata), fh)
    return output_path


async def main(
    output_dir: Path,
    max_zoom_level: int = 6,
    max_concurrency: int = 20,
    emodnet_layer_id: str = "baselayer",
    tile_matrix_set: str = "web_mercator",
    pause_for_seconds: int = 3,
) -> list[tuple[DownloadStatus, Path]]:
    tile_ranges = get_tile_ranges(max_zoom_level)
    results = []

    def on_task_complete(task: asyncio.Task):
        try:
            result = task.result()
            results.append(result)
        except asyncio.CancelledError as e:
            logger.warning(f"Task was cancelled: {e}")
        except Exception:
            logger.exception("Task raised an unhandled exception")

    tasks = []
    task_count = 0

    async with httpx.AsyncClient(
        limits=httpx.Limits(max_connections=max_concurrency)
    ) as client:
        for z, (min_x, max_x, min_y, max_y) in tile_ranges.items():
            for x in range(min_x, max_x + 1):
                for y in range(min_y, max_y + 1):
                    url = EMODNET_TILE_DOWNLOAD_TEMPLATE.format(
                        layer_id=emodnet_layer_id,
                        tile_matrix_set=tile_matrix_set,
                        z=z,
                        x=x,
                        y=y,
                    )
                    file_path = output_dir / str(z) / str(x) / f"{y}.png"
                    if file_path.exists() and file_path.stat().st_size > 0:
                        results.append((DownloadStatus.SKIPPED, file_path))
                        continue
                    task = asyncio.create_task(download_tile(client, url, file_path))
                    task.add_done_callback(on_task_complete)
                    tasks.append(task)
                    task_count += 1

                    if task_count % max_concurrency == 0:
                        logger.debug(
                            f"Pausing for {pause_for_seconds}s in order to not "
                            f"overload remote servers..."
                        )
                        await asyncio.sleep(pause_for_seconds)

        await asyncio.wait(tasks)

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "output_dir", type=Path, help="Directory to save downloaded tiles"
    )
    parser.add_argument(
        "-l", "--layer-id", type=str, help="EMODNet layer id", default="baselayer"
    )
    parser.add_argument(
        "-z",
        "--max-zoom-level",
        type=int,
        help="Maximum tile zoom level to download",
        default=6,
    )
    parser.add_argument(
        "-c",
        "--max-concurrency",
        type=int,
        help="Maximum tile download concurrency",
        default=20,
    )
    parser.add_argument(
        "-t",
        "--tile-matrix-set",
        type=str,
        help="Id of the tile matrix set to download",
        default="web_mercator",
    )
    parser.add_argument(
        "-p",
        "--pause-seconds",
        type=int,
        help=(
            "How many seconds to pause between batches of concurrent downloads, "
            "to keep from overloading the remote tile server"
        ),
        default=3,
    )
    _setup_logging(logging.DEBUG)
    args = parser.parse_args()
    results = asyncio.run(
        main(
            args.output_dir,
            args.max_zoom_level,
            args.max_concurrency,
            emodnet_layer_id=args.layer_id,
            tile_matrix_set=args.tile_matrix_set,
            pause_for_seconds=args.pause_seconds,
        )
    )
    metadata = TilesMinimalMetadata(
        name="EMODNet Bathymetry World Base Layer",
        type="baselayer",
        version="1.0.0",
        description="EMODNet bathymetry base layer",
        attribution=(
            "EMODnet Bathymetry World Base Layer version 1. "
            "GGS Geo Consultancy (2021): EMODnet Bathymetry consortium "
            "https://doi.org/10.12770/386fe2aa-84c4-4cea-9e22-fcba4d5f2e75"
        ),
    )
    if args.output_dir.is_dir():
        metadata_path = generate_metadata_file(args.output_dir, metadata)
    print("Download summary:")
    print(f"Total tiles processed: {len(results)!r}")
    print(
        f"Downloaded {len([r for r in results if r[0] == DownloadStatus.SUCCESS])!r} tiles"
    )
    print(
        f"Skipped {len([r for r in results if r[0] == DownloadStatus.SKIPPED])!r} tiles"
    )
    print(
        f"Failed to download {len([r for r in results if r[0] == DownloadStatus.FAILED])!r} tiles"
    )
    print(f"All downloaded tiles are in {args.output_dir!r}")
