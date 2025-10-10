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
class GeoRasterMetadata:
    name:           str
    size_bytes:     int
    creation_date: datetime
    media_type:     str
    driver:         str
    
    image_size: Tuple[int,int]
    bands:      int

    # Coordinate Model

    geographic:     bool
    projected:      bool
    local:          bool
    geocentric:     bool

    extent:          Tuple[float,float,float,float]

    projection:      str
    datum:           str
    crs_auth:        Optional[str] = None         # e.g., "EPSG"
    crs_code:        Optional[str] = None         # e.g., "4326"
    crs_wkt:         Optional[str] = None


    def __init__(self,gdal_ds):
        self.name = gdal_ds.GetDescription()
        self.size_bytes = os.path.getsize(self.name)
        self.creation_date = datetime.fromtimestamp(os.path.getctime(self.name),UTC).isoformat() + "Z"
        drv = gdal_ds.GetDriver()
        self.media_type = drv.LongName
        self.driver = drv.ShortName

        self.image_size = (gdal_ds.RasterXSize,gdal_ds.RasterYSize)
        self.bands = gdal_ds.RasterCount

        # model transform data

        gt = gdal_ds.GetGeoTransform()
        
        # CRS

        self.crs_wkt = gdal_ds.GetProjection()
        
        # Spatial Reference

        srs = osr.SpatialReference(wkt=self.crs_wkt)
        self.geographic = srs.IsGeographic()
        self.projected = srs.IsProjected()
        self.local = srs.IsLocal()
        self.geocentric = srs.IsGeocentric()

        #self.central_meridian = srs.GetProjParm("central_meridian")
        self.projection = srs.GetAttrValue("PROJECTION")
        self.datum = srs.GetAttrValue("DATUM")

        self.crs_auth = srs.GetAuthorityName(None)
        self.crs_code = srs.GetAuthorityCode(None)

        cols,rows = self.image_size
        self.extent = (gt[0], gt[3] + cols * gt[4] + rows * gt[5],
                       gt[0] + cols * gt[1] + rows * gt[2], gt[3])

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
        msg = (
            f"{e}\n"
            f"call       = gdal.Open({path}, gdal.GA_ReadOnly)\n"
            f"error_no   = {gdal.GetLastErrorNo()}\n"
            f"error_type = {gdal.GetLastErrorType()}\n"
            f"message    = {gdal.GetLastErrorMsg()}"
        )
        raise type(e)(msg).with_traceback(e.__traceback__)


    gdal.PopErrorHandler()

    return ds

def read_metadata_from_raster(path):
    ds = gdal_open_file(path)

    return GeoRasterMetadata(ds)

# Example usage
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Attempt to extract metadata from GDAL supported data formats."
    )
    parser.add_argument("file_name",help="GDAL supported file path")
    args = parser.parse_args()

    m = read_metadata_from_raster(args.file_name)
    # print(json.dumps(m,indent=2))
    print(str(m))
    print(f"#### {args.file_name} ####")
