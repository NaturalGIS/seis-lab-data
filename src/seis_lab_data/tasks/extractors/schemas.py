import pydantic


class RasterMetadata(pydantic.BaseModel):
    driver: str
    width: int
    height: int
    band_count: int
    epsg: int | None = None
    crs_wkt: str | None = None
    pixel_size_x: float | None = None
    pixel_size_y: float | None = None
    nodata: float | None = None
    bbox_native: tuple[float, float, float, float] | None = None
    bbox_4326: tuple[float, float, float, float] | None = None
