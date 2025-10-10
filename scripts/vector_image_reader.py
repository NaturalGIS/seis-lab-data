from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Set, Tuple

@dataclasses.dataclass
class GeoMetadata:
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


@dataclass
class FieldDef:
    name:           str
    type:           str
    nullable:       bool    = True
    width:          int     = None
    precision:      int     = None
    units:          str     = None

@dataclass
class VectorMetadata(GeoMetadata):
    layer_name:     str
    geometry_types: Set[str] = field(default_factory=set)
    has_z:          bool = False
    has_m:          bool = False

    feature_count:  int = 0
    fields_schema:  List[FieldDef] = field(default_factory=list)
    primary_key:    str = None
    unique_fields:  List[str] = field(default_factory=list)

def __init__(self,ogr_ds):

    try:
        self.driver = ds.GetDriver()
    except Exception:
        self.driver = None

    lyr = None
    if args.layer_name is not None:
        lyr = ds.GetLayerByName(layer_name)
        if lyr is None:
            raise RuntimeError(f"Layer '{layer_name}' not found in {path_or_url}")
    else:
        lyr = ds.GetLayer(0)
        if lyr is None:
            raise RuntimeError(f"No layers found in {path_or_url}")

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
            pass

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

# Vector file layers helper

def list_layers_ogr(path_or_url: str) -> List[str]:
    ds = ogr.Open(path_or_url,update = 0)
    if ds is None:
        return []
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
    parser.add_argument("layer_name",help="Name of the layer to be read")
    args = parser.parse_args()
    ds = ogr.Open(args.file_name,update = 0)
    if ds is None:
        raise RuntimeError(f"Could not open: {args.file_name}")


    md = VectorMetadata(ds)
    md.name = args.file_name

    print(str(m))
    print(f"#### {args.file_name} ####")
