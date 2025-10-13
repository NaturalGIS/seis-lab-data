import dataclasses
from dataclasses import dataclass
from dataclasses import field
from dataclasses import asdict
from datetime    import datetime
from datetime    import UTC
from typing      import List, Optional, Dict, Any, Set, Tuple
import os

@dataclasses.dataclass
class GeoMetadata:
    name:           str = None
    size_bytes:     int = 0
    creation_date:  datetime = datetime.now()
    media_type:     str = None
    driver:         str = None

    data_repr_class: bool  = 0 # 0: raster 1: vector

    def is_vector(self):
        return self.data_repr_class == 1

    def is_raster(self):
        return self.data_repr_class == 0

    def __init__(self,file_path,driver,media_type):
        self.name           = file_path
        self.size_bytes     = os.path.getsize(file_path)
        self.creation_date  = datetime.fromtimestamp(os.path.getctime(file_path),UTC).isoformat() + "Z"
        self.driver         = driver
        self.media_type     = media_type
