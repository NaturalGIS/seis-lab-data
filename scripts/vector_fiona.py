import fiona
from pyproj import CRS, Transformer

def vector_metadata_from_path(path: str, layer: str | None = None) -> VectorMetadata:
    # Open datasource; pick first layer if not provided
    with fiona.Env():
        with fiona.open(path, layer=layer) as src:
            md = VectorMetadata()
            md.driver = src.driver
            md.datasource = path
            md.layer_name = src.name

            # CRS
            crs = None
            try:
                crs = CRS.from_user_input(src.crs_wkt or src.crs)
            except Exception:
                crs = None
            if crs:
                if crs.to_authority():
                    auth, code = crs.to_authority()
                    md.crs_auth, md.crs_code = auth, code
                md.crs_wkt = crs.to_wkt()

            # Extent
            if src.bounds:
                md.bbox_native = tuple(src.bounds)

            # Transform bbox to WGS84 for easy map previews
            if md.bbox_native and crs:
                try:
                    to84 = Transformer.from_crs(crs, 4326, always_xy=True)
                    minx, miny, maxx, maxy = md.bbox_native
                    x0,y0 = to84.transform(minx, miny)
                    x1,y1 = to84.transform(maxx, maxy)
                    md.bbox_wgs84 = (min(x0,x1), min(y0,y1), max(x0,x1), max(y0,y1))
                except Exception:
                    pass

            # Schema / geometry
            sch = src.schema
            if sch:
                gtype = sch.get("geometry")
                if isinstance(gtype, str):
                    md.geometry_types = {gtype}
                props = sch.get("properties", {})
                md.fields_schema = [
                    FieldDef(name=k, type=v.split(":")[0], 
                             width=int(v.split(":")[1]) if ":" in v and v.split(":")[1].isdigit() else None)
                    for k,v in props.items()
                ]

            # Count and dimension flags
            try:
                md.feature_count = len(src)
            except Exception:
                md.feature_count = None

            # Detect Z/M by sampling first feature
            try:
                feat = next(iter(src))
                coords_text = str(feat.get("geometry"))
                md.has_z = "coordinates" in feat["geometry"] and \
                            any(isinstance(t, (list, tuple)) and \
                            len(t)>=3 for t in _coord_iter(feat["geometry"]["coordinates"]))
                md.has_m = False  # Fiona doesn’t expose M reliably; set via extra if you know
            except StopIteration:
                pass

            # Encoding (Shapefile DBF often sets this)
            try:
                md.text_encoding = src.encoding
            except Exception:
                pass

            # Spatial index (FlatGeobuf, GPKG, GDB may have one; Fiona doesn’t standardize this)
            md.has_spatial_index = None  # leave unknown; fill with driver-specific probes if needed

            return md

def _coord_iter(coords):
    # Flatten coordinate arrays a bit to check dimensionality (naive & safe)
    if isinstance(coords, (list, tuple)):
        for c in coords:
            if isinstance(c, (list, tuple)) and len(c) and isinstance(c[0], (list, tuple)):
                yield from _coord_iter(c)
            else:
                yield c

