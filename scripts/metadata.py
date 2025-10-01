import dataclasses

from dataclasses import field
from datetime import datetime

@dataclasses.dataclass
class Metadata:
    name:       str
    size_bytes: int
    creation_date: datetime
    media_type: str
    driver:     str

    data_repr_class: bool  # 0: raster 1: vector
    auxiliary: dict = field(default_factory=dict)

    def is_vector(self):
        return self.data_repr_class == 1

    def is_raster(self):
        return self.data_repr_class == 0

