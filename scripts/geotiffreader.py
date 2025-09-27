import argparse
import metadata
from datetime import datetime
from datetime import UTC

import os

from osgeo import gdal
from osgeo import ogr
from osgeo import osr


def read_geotiff_metadata(path):
    ds = gdal_open_file(path)

    drv = ds.GetDriver()
    media_type = drv.LongName
    driver = drv.ShortName

    # get projection if any

    proj = ds.GetProjection()
    srs = osr.SpatialReference(wkt=proj) if proj else None
    epsg = None
    if srs and srs.IsProjected():
        srs.AutoIdentifyEPSG()
        try:
            epsg = int(srs.GetAttrValue("AUTHORITY", 1))
        except Exception:
            pass

    metadata = Metadata(
        os.path.basename(path),
        os.path.getsize(path),
        datetime.fromtimestamp(os.path.getctime(path), UTC).isoformat() + "Z",
    )


# Example usage
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Attempt to extract metadata from GDAL supported data formats."
    )
    parser.add_argument("file_name", help="GDAL supported file path")
    args = parser.parse_args()

    m = read_geotiff_metadata(args.file_name)
    # print(json.dumps(m, indent=2))
    print(str(m))
    print(f"#### {args.file_name} ####")
