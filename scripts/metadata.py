import dataclasses

from dataclasses import field
from datetime import datetime

from osgeo import gdal

@dataclasses.dataclass
class Metadata:
    name:       str
    size_bytes: int
    creation_date: datetime
    media_type: str
    driver:     str
    spatial:    str

    data_repr_class: bool  # 0: raster 1: vector
    auxiliary: dict = field(default_factory=dict)

    def is_vector(self):
        return self.data_repr_class == 1

    def is_raster(self):
        return self.data_repr_class == 0

warning_notes = []

def gdal_open_exceptions_handler(err_class, err_no, msg):
    global warning_notes
    if err_class == gdal.CE_Warning:
        warning_notes.append(msg)


def gdal_open_file(path):
    global warning_notes

    gdal.UseExceptions()
    warning_notes = []
    gdal.PushErrorHandler(gdal_open_exceptions_handler)
    try:
        ds = gdal.Open(path, gdal.GA_ReadOnly)
    except Exception as e:
        e.details["call"] = f"gdal.Open({path},gdal.GA_ReadOnly)"
        e.details["error_no"] = gdal.GetLastErrorNo()
        e.details["error_type"] = gdal.GetLastErrorType()
        e.details["message"] = gdal.GetLastErrorMsg()
        gdal.PopErrorHandler()
        raise
    finally:
        gdal.PopErrorHandler()

    return ds
