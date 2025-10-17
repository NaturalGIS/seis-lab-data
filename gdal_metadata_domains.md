
## GEOTiff and other raster formats common metadata (GDAL Domains)

| Format                       | Example Domains                                        |
| ---------------------------- | ------------------------------------------------------ |
| **GeoTIFF (.tif/.tiff)**     | `None`, `GEOTIFF`, `IMAGE_STRUCTURE`, `RPC`, `xml:XMP` |
| **HDF5 / HDF4**              | `None`, `SUBDATASETS`, sometimes `GEOLOCATION`         |
| **NetCDF / CF-compliant**    | `None`, `SUBDATASETS`, `GEOLOCATION`                   |
| **JPEG2000 (.jp2)**          | `None`, `JPEG2000`, `xml:XMP`, `COLOR_PROFILE`         |
| **ECW**                      | `None`, `IMAGE_STRUCTURE`                              |
| **MrSID**                    | `None`, `IMAGE_STRUCTURE`                              |
| **PNG / JPEG / BMP**         | `None`, `COLOR_PROFILE` (if embedded)                  |
| **ASCII Grid / ESRI Raster** | `None` (mostly general metadata)                       |
| **GRIB**                     | `None`, `SUBDATASETS`, sometimes `GEOLOCATION`         |
| **SAR / SAR-C**              | Depends on format; often `RPC`                         |


## Concepts Hierarchy

```
Pixel space (row, col)
   │
Raster→Model transform = affine mapping: pixels -> coordinates (x,y) (see GetProjection())
   │
Coordinate Reference System (CRS) = semantics of (x,y)
   ├─ Ellipsoid
   ├─ Datum
   ├─ Geographic CRS (lat/lon)
   ├─ Projected CRS
   │    └─ Projection (spherical/ellipsoidal -> plane mapping)
   │
   v
AUTHORITY (e.g. EPSG:4326 = WGS84 geographic)
```

## Coordinate Reference Systems 

```
CRS
 ├── Ellipsoid
 ├── Datum
 ├── Coordinate system
 │     ├─ Geographic CRS
 │     └─ Projected CRS
 │          └─ Projection method + parameters
 └── Units
```

A projection specifies:

 * The mathematical transformation from latitude/longitude (on the ellipsoid) -> planar x/y.
 * The parameters of that transform:
    1. central meridian
    2. latitude of origin
    3. scale factor
    4. false easting / northing (?)

Projection definition are standardized by authorities (EPSG)

 * EPSG:4326 → WGS84 geographic CRS (no projection, lat/lon)
 * EPSG:32633 → WGS84 / UTM zone 33N = (datum: WGS84 + projection: Transverse Mercator + params)

