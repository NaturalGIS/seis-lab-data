import dataclasses
from datetime import datetime
from datetime import UTC
from typing import Tuple
import os


@dataclasses.dataclass
class GeoMetadata:
    name: str
    size_bytes: int
    media_type: str
    driver: str

    creation_date: datetime = datetime.now()
    data_repr_class: bool = 0  # 0: raster 1: vector
    extent: Tuple[float, float, float, float] = (0, 0, 0, 0)
    crs_wkt: str = None
    crs_auth: str = None  # e.g., "EPSG"
    crs_code: str = None  # e.g., "4326"

    def is_vector(self):
        return self.data_repr_class == 1

    def is_raster(self):
        return self.data_repr_class == 0

    def __init__(self, file_path, driver, media_type):
        self.name = file_path
        self.size_bytes = os.path.getsize(file_path)
        self.creation_date = (
            datetime.fromtimestamp(os.path.getctime(file_path), UTC).isoformat() + "Z"
        )
        self.driver = driver
        self.media_type = media_type
