import dataclasses
from dataclasses import dataclass
from dataclasses import field
from dataclasses import asdict
import argparse
from datetime import datetime
from datetime import UTC
from typing import List, Set, Tuple
from osgeo  import gdal
from osgeo  import ogr
from osgeo  import osr

from metadata import GeoMetadata

#@dataclasses.dataclass
#class GeoMetadata:
#    name:       str
#    size_bytes: int
#    creation_date: datetime
#    media_type: str
#    driver:     str
#
#    data_repr_class: bool = 0 # 0: raster 1: vector
#
#    def is_vector(self):
#        return self.data_repr_class == 1
#
#    def is_raster(self):
#        return self.data_repr_class == 0


@dataclasses.dataclass
class FieldDef:
    name:           str
    type:           str
    nullable:       bool
    width:          int
    precision:      int
    units:          str

@dataclasses.dataclass
class VectorMetadata(GeoMetadata):
    layer_name:     str = None
    geometry_types: Set[str] = field(default_factory=set)
    has_z:          bool = False
    has_m:          bool = False

    feature_count:  int = 0
    fields_schema:  List[FieldDef] = field(default_factory=list)
    primary_key:    str = None

    def __init__(self,file_path,layer_name=None):
        self.data_repr_class = 1

        ogr_ds = ogr_open_file(file_path)
        try:
            drv        = ogr_ds.GetDriver()
            driver     = drv.ShortName
            media_type = drv.LongName
        except Exception:
            driver     = None
            media_type = None

        super().__init__(file_path,driver,media_type)
        lyr = None
        if layer_name is not None:
            lyr = ogr_ds.GetLayerByName(layer_name)
            if lyr is None:
                raise RuntimeError(f"Layer '{layer_name}' not found in {file_path}")
        else:
            lyr = ogr_ds.GetLayer(0)
            if lyr is None:
                raise RuntimeError(f"No layers found in {file_path}")

        # Layer name
        try:
            self.layer_name = lyr.GetName()
        except Exception:
            pass


    # CRS (authority + WKT)
        srs = None
        try:
            srs = lyr.GetSpatialRef()
        except Exception:
            srs = None

        if srs:
            try:
                auth = srs.GetAuthorityName(None)
                code = srs.GetAuthorityCode(None)
                if auth and code:
                    self.crs_auth, self.crs_code = auth, code
            except Exception:
                pass

            try:
                self.crs_wkt = srs.ExportToWkt()
            except Exception:
                self.crs_wkt = None

    # Extent (OGR returns minX, maxX, minY, maxY)
        try:
            self.extent = lyr.GetExtent(True)  # True may compute if unknown
        except Exception:
            self.extent = None

        # Feature count (force fast when possible)
        try:
            fc = lyr.GetFeatureCount(True)
            if fc < 0:
                fc = lyr.GetFeatureCount(False)
            self.feature_count = int(fc) if fc is not None and fc >= 0 else None
        except Exception:
            self.feature_count = None

    # Geometry types, Z/M flags (read from layer definition)
        try:
            gdefn = lyr.GetLayerDefn()
            gtype = gdefn.GetGeomType()
            # Geometry type name (handles 25D, etc.)
            try:
                name = ogr.GeometryTypeToName(gtype)
                if name:
                    self.geometry_types.add(name)
            except Exception:
                self.geometry_types = None

            # Z/M flags (GDAL >= 2.0 has helpers)
            try:
                self.has_z = bool(ogr.GeometryTypeHasZ(gtype))
            except Exception:
                # Fallback: 25D suffix in name
                self.has_z = name.endswith("25D") if isinstance(name, str) else False

            try:
                self.has_m = bool(ogr.GeometryTypeHasM(gtype))
            except Exception:
                self.has_m = False
        except Exception:
            pass

    # Field schema
        try:
            ldefn = lyr.GetLayerDefn()
            fields = []
            for i in range(ldefn.GetFieldCount()):
                fdefn = ldefn.GetFieldDefn(i)
                ftype_name = fdefn.GetFieldTypeName(fdefn.GetType())
                width = fdefn.GetWidth() if fdefn.GetWidth() > 0 else None
                precision = fdefn.GetPrecision() if fdefn.GetPrecision() > 0 else None
                # Nullable/unique are not always available across drivers/GDAL versions
                try:
                    nullable = bool(fdefn.IsNullable())
                except Exception:
                    fields.append(FieldDef (name = fdefn.GetName(),
                                            type = ftype_name.lower(),
                                            nullable = True,
                                            width = width,
                                            precision = precision))

            self.fields_schema = fields
        except Exception:
            self.fields_schema = []


    def _extent_from_layer(lyr: ogr.Layer) -> Optional[Tuple[float,float,float,float]]:
        try:
            ext = lyr.GetExtent(True)  # (minX, maxX, minY, maxY) or None
            if ext:
                minx, maxx, miny, maxy = ext
                return (minx, miny, maxx, maxy)
        except Exception:
            pass

        # Fallback: sample features to compute extent
        try:
            lyr.SetSpatialFilter(None)
            lyr.ResetReading()
            first = True
            minx = miny = float("inf")
            maxx = maxy = float("-inf")
            for i, f in enumerate(lyr):
                g = f.GetGeometryRef()
                if g is None:
                    continue
                bx = g.GetEnvelope()  # (minx, maxx, miny, maxy)
                if bx:
                    if first:
                        minx, maxx, miny, maxy = bx
                        first = False
                    else:
                        minx = min(minx, bx[0]); maxx = max(maxx, bx[1])
                        miny = min(miny, bx[2]); maxy = max(maxy, bx[3])
                if i > 5000:  # don’t scan huge layers fully; this is a fallback
                    break
            if not first:
                return (minx, miny, maxx, maxy)
        except Exception:
            pass
        return None

    def _to_wgs84_bbox_osr(bbox: Tuple[float,float,float,float], srs: osr.SpatialReference,
                           samples_per_edge: int = 0) -> Optional[Tuple[float,float,float,float]]:
        try:
            srs84 = osr.SpatialReference()
            srs84.ImportFromEPSG(4326)
            ct = osr.CoordinateTransformation(srs, srs84)
        except Exception:
            return None
        minx, miny, maxx, maxy = bbox
        pts = [(minx,miny), (maxx,miny), (maxx,maxy), (minx,maxy)]
        if samples_per_edge > 0:
            def interp(a,b,n):
                for i in range(1,n+1):
                    t = i/(n+1)
                    yield (a[0]*(1-t)+b[0]*t, a[1]*(1-t)+b[1]*t)
            edges = [(0,1),(1,2),(2,3),(3,0)]
            base = pts.copy()
            for i0,i1 in edges:
                pts.extend(list(interp(base[i0], base[i1], samples_per_edge)))
        xs, ys = [], []
        for x,y in pts:
            try:
                X,Y,_ = ct.TransformPoint(x,y)  # returns lon,lat,z
                xs.append(X); ys.append(Y)
            except Exception:
                continue
        if not xs:
            return None
        return (min(xs), min(ys), max(xs), max(ys))


warning_notes = []

def ogr_open_exceptions_handler(err_class, err_no, msg):
    global warning_notes
    if err_class == gdal.CE_Warning:
        warning_notes.append(msg)

def ogr_open_file(path):
    global warning_notes

    ogr.UseExceptions()
    warning_notes = []
    gdal.PushErrorHandler(ogr_open_exceptions_handler)
    try:
        ds = ogr.Open(path, gdal.GA_ReadOnly)
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

# Vector file layers helper

def list_layers_ogr(path_or_url: str) -> List[str]:
    ds = ogr_open_file(path_or_url)
    names = []
    try:
        for i in range(ds.GetLayerCount()):
            lyr = ds.GetLayer(i)
            if lyr is not None:
                names.append(lyr.GetName())
    except Exception:
        pass
    return names

# Example usage
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Attempt to extract metadata from GDAL/OGR supported data formats."
    )
    parser.add_argument("file_name",help="GDAL/OGR supported file path")
    parser.add_argument("-l","--layer-name",default=None,help="Layer name to be read")
    parser.add_argument("-L","--list-layers",default=False,help="List layers and then exit")
    args = parser.parse_args()

    #ds = ogr.Open(args.file_name,update = 0)
    #if ds is None:
    #    raise RuntimeError(f"Could not open: {args.file_name}")

    md = VectorMetadata(args.file_name)

    print(str(md))
    print(f"#### {args.file_name} ####")
