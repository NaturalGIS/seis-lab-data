import datetime as dt
import math
import typing

import pydantic


class ExtractedMetadata(pydantic.BaseModel):
    # the structure of the data, which the driver alone does not tell: an XYZ file
    # holds either a grid or a point cloud
    data_type: typing.ClassVar[str | None] = None

    driver: str | None = None
    # set by the dispatcher rather than by each extractor
    file_size_bytes: int | None = None
    epsg: int | None = None
    crs_name: str | None = None
    crs_wkt: str | None = None
    # set by discovery when the survey mission's implicit CRS placed the file
    crs_from_mission: bool = False
    bbox_native: tuple[float, float, float, float] | None = None
    bbox_4326: tuple[float, float, float, float] | None = None
    temporal_extent_begin: dt.date | None = None
    temporal_extent_end: dt.date | None = None

    @property
    def bbox_native_needing_crs(self) -> tuple[float, float, float, float] | None:
        """Native bbox that can only be mapped if someone declares its CRS.

        Formats like SEG-Y and XYZ have nowhere to record a CRS, so the extractor
        reports coordinates but no bbox_4326. Whoever knows the CRS can project
        this bbox; the file itself never tells us.
        """
        declares_own_crs = self.epsg is not None or self.crs_wkt is not None
        if self.bbox_4326 is None and not declares_own_crs:
            return self.bbox_native
        return None

    def get_discovery_info(self) -> dict:
        """Return the metadata shown on a record's page, as JSON values.

        Fields holding their default value are left out, and so are the extents,
        which records store in columns of their own, the CRS WKT, the CRS codes
        quoted by a SEG-Y header, and the positions sampled from its traces. The
        structure of the data is added as `type`, if known.

        A field holding a non-finite float, or a list with one, is left out as well:
        PostgreSQL rejects such values in JSON, so the file would get no record.
        """
        info = self.model_dump(
            mode="json",
            exclude_defaults=True,
            exclude={
                "crs_wkt",
                "bbox_4326",
                "temporal_extent_begin",
                "temporal_extent_end",
                "header_epsg_codes",
                "sampled_positions",
            },
        )
        if self.data_type is not None:
            info["type"] = self.data_type
        return {
            key: value
            for key, value in info.items()
            if all(
                math.isfinite(element)
                for element in (value if isinstance(value, list) else [value])
                if isinstance(element, float)
            )
        }


class RasterMetadata(ExtractedMetadata):
    data_type = "raster"

    width: int
    height: int
    band_count: int
    pixel_size_x: float | None = None
    pixel_size_y: float | None = None
    nodata: float | None = None


class VectorMetadata(ExtractedMetadata):
    data_type = "vector"

    layer_count: int
    feature_count: int
    geometry_type: str


class PointCloudMetadata(ExtractedMetadata):
    data_type = "point cloud"

    point_count: int
    # estimated from the rows of a sampled read rather than counted
    point_count_estimated: bool = False


class KmallMetadata(ExtractedMetadata):
    echo_sounder_id: int | None = None
    # from the earliest to the latest datagram timestamp read
    duration_seconds: float | None = None


class SegyMetadata(ExtractedMetadata):
    trace_count: int | None = None
    samples_per_trace: int | None = None
    # the raw header value, deliberately unitless: time files store microseconds
    # here but depth-domain files store a length (50 == 0.05 m) and rev0/1 has
    # no flag to tell them apart
    sample_interval: int | None = None
    sample_format: str | None = None
    coordinate_units: str | None = None
    coverage: str = "full"
    # codes quoted in the free-text header; discovery decides whether one applies
    header_epsg_codes: tuple[int, ...] = ()
    # the points behind bbox_native, in trace order, for the track preview
    sampled_positions: tuple[tuple[float, float], ...] = ()


ExtractionResult = (
    RasterMetadata | PointCloudMetadata | VectorMetadata | KmallMetadata | SegyMetadata
)
