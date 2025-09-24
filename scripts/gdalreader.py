# -*- coding: utf-8 -*-
""" """

import argparse
import dataclasses
from dataclasses import field
from dataclasses import fields
from datetime import datetime
from datetime import UTC
import json
import os
from osgeo import gdal
from osgeo import ogr
from osgeo import osr


@dataclasses.dataclass
class Metadata:
    name: str
    size_bytes: int
    creation_date: datetime
    format: str = None
    driver: str = None
    spatial: str = None
    raster: str = None
    vector: str = None
    error_no: str = 0
    error_type: str = ""
    messages: list[str] = field(default_factory=list)

    def __str__(self):
        md_d = dict()
        for f in fields(Metadata):
            md_d[f.name] = getattr(self, f.name)

        return json.dumps(md_d)


def gdal_open_exceptions_handler(cls, err_class, err_no, msg):
    if err_class == gdal.CE_Warning:
        GDALReader.warning_notes.append(msg)


class GDALReader:
    warning_notes = []

    def extract_metadata(self, path):
        gdal.UseExceptions()

        metadata = Metadata(
            os.path.basename(path),
            os.path.getsize(path),
            datetime.fromtimestamp(os.path.getctime(path), UTC).isoformat() + "Z",
        )

        # Try opening as raster

        gdal.PushErrorHandler(gdal_open_exceptions_handler)
        try:
            ds = gdal.Open(path, gdal.GA_ReadOnly)
        except Exception:
            metadata.error_type = gdal.GetLastErrorType()
            metadata.error_no = gdal.GetLastErrorNo()
            metadata.messages.append(gdal.GetLastErrorMsg())
            return metadata

        gdal.PopErrorHandler()

        if ds is not None:
            try:
                drv = ds.GetDriver()
                metadata.format = drv.LongName
                metadata.driver = drv.ShortName

                # Spatial reference

                # get data projection if any

                proj = ds.GetProjection()
                srs = osr.SpatialReference(wkt=proj) if proj else None
                epsg = None
                if srs and srs.IsProjected():
                    srs.AutoIdentifyEPSG()
                    try:
                        epsg = int(srs.GetAttrValue("AUTHORITY", 1))
                    except Exception:
                        pass

                # get the GeoTransform and infer the extent from it

                gt = ds.GetGeoTransform()
                if gt:
                    xmin = gt[0]
                    ymax = gt[3]
                    xmax = xmin + ds.RasterXSize * gt[1]
                    ymin = ymax + ds.RasterYSize * gt[5]
                else:
                    xmin = ymin = xmax = ymax = None

                metadata.spatial = {
                    "crs": {"epsg": epsg, "wkt": proj},
                    "extent": {"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax},
                    "resolution": {
                        "x": gt[1] if gt else None,
                        "y": gt[5] if gt else None,
                    },
                    "geometry_type": None,
                }

                # Raster bands
                bands_info = []
                for i in range(1, ds.RasterCount + 1):
                    band = ds.GetRasterBand(i)
                    stats = band.GetStatistics(True, True)
                    bands_info.append(
                        {
                            "band": i,
                            "datatype": gdal.GetDataTypeName(band.DataType),
                            "nodata_value": band.GetNoDataValue(),
                            "statistics": {
                                "min": stats[0],
                                "max": stats[1],
                                "mean": stats[2],
                                "stddev": stats[3],
                            },
                        }
                    )

                metadata.raster = {"bands": ds.RasterCount, "info": bands_info}

                ds = None
            except Exception:
                print(f"not handling {path} as raster")

            metadata.messages = GDALReader.warning_notes
            return metadata

        # Try opening as vector
        try:
            ds_vec = ogr.Open(path, 0)
            if ds_vec is not None:
                raise Exception("Unable to open the file as vector data file")

            print(f"reading {path} as vector file with driver")
            try:
                driver = ds_vec.GetDriver().GetName()
            except Exception:
                driver = None
                print(f"failed to establish a driver for {path}")

            metadata.driver = driver
            metadata.format = driver

            layers = []
            for i in range(ds_vec.GetLayerCount()):
                layer = ds_vec.GetLayer(i)
                srs = layer.GetSpatialRef()
                epsg = None
                if srs:
                    try:
                        srs.AutoIdentifyEPSG()
                        epsg = int(srs.GetAttrValue("AUTHORITY", 1))
                    except Exception:
                        pass

                extent = layer.GetExtent()
                schema = {}
                defn = layer.GetLayerDefn()
                for j in range(defn.GetFieldCount()):
                    fld = defn.GetFieldDefn(j)
                    schema[fld.GetName()] = fld.GetFieldTypeName(fld.GetType())

                layers.append(
                    {
                        "name": layer.GetName(),
                        "geometry_type": ogr.GeometryTypeToName(layer.GetGeomType()),
                        "feature_count": layer.GetFeatureCount(),
                        "attributes": schema,
                        "extent": {
                            "xmin": extent[0],
                            "ymin": extent[2],
                            "xmax": extent[1],
                            "ymax": extent[3],
                        },
                        "crs": {
                            "epsg": epsg,
                            "wkt": srs.ExportToWkt() if srs else None,
                        },
                    }
                )

            metadata.vector = {"layers": layers}
            ds_vec = None
        except Exception as e:
            print(f"Error reading vector data from {path}: {e}")

        return metadata


# Example usage
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Attempt to extract metadata from GDAL supported data formats."
    )
    parser.add_argument("file_name", help="GDAL supported file path")
    args = parser.parse_args()

    gdal_reader = GDALReader()
    m = gdal_reader.extract_metadata(args.file_name)
    # print(json.dumps(m, indent=2))
    print(str(m))
    print(f"#### {args.file_name} ####")
