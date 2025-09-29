import argparse
import dataclasses
from dataclasses import field
from datetime import datetime
from datetime import UTC

import os
from typing import Tuple


from osgeo import gdal
from osgeo import ogr
from osgeo import osr

@dataclasses.dataclass
class GeoTIFFMetadata:
    name:       str
    size_bytes: int
    creation_date: datetime
    media_type: str
    driver:     str
    
    image_size: Tuple[int,int] 
    bands:      int
    geo_transform: [int]

    # Coordinate Model

    geographic: bool
    projected:  bool
    local:      bool
    geocentric: bool

    

    spatial:    str

    auxiliary: dict = field(default_factory=dict)
    messages: list[str] = field(default_factory=list)

    def __init__(self,gdal_ds):

        



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
        e.details["call"]       = f"gdal.Open({path},gdal.GA_ReadOnly)"
        e.details["error_no"]   = gdal.GetLastErrorNo()
        e.details["error_type"] = gdal.GetLastErrorType()
        e.details["message"]    = gdal.GetLastErrorMsg()
        gdal.PopErrorHandler()
        raise

    gdal.PopErrorHandler()

    return ds

def read_geotiff_metadata(path):
    ds = gdal_open_file(path)

    drv = ds.GetDriver()
    media_type = drv.LongName
    driver = drv.ShortName

    # get projection if any

    proj = ds.GetProjection()
    srs  = osr.SpatialReference(wkt=proj) if proj else None
    epsg = None
    if srs and srs.IsProjected():
        srs.AutoIdentifyEPSG()
        try:
            epsg = int(srs.GetAttrValue("AUTHORITY",1))
        except Exception:
            pass

    metadata = Metadata(ds)
        os.path.basename(path),
        os.path.getsize(path),
        datetime.fromtimestamp(os.path.getctime(path),UTC).isoformat() + "Z",
        media_type,driver,0,
    )






# Example usage
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Attempt to extract metadata from GDAL supported data formats."
    )
    parser.add_argument("file_name", help="GDAL supported file path")
    args = parser.parse_args()

    m = read_geotiff_metadata(args.file_name)
    # print(json.dumps(m,indent=2))
    print(str(m))
    print(f"#### {args.file_name} ####")
