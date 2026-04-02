# Dataset reference

Quick reference for the data model dimensions used to classify datasets in the archive.

## Domain types

| Code | Domain type | Description |
|------|-------------|-------------|
| D1 | Geophysical | Remote sensing and acoustic survey data (bathymetry, backscatter, seismic, magnetometer/gradiometer) |
| D2 | Geotechnical | Physical sampling and in-situ testing data (superficial sediment samples, cores, CPT tests) |

## Dataset categories

| Code | Category | Domain |
|------|----------|--------|
| C1 | Bathymetry | Geophysical |
| C2 | Backscatter | Geophysical |
| C3 | Seismic | Geophysical |
| C4 | Magnetometer/gradiometer | Geophysical |
| C5 | Superficial sediment samples | Geotechnical |
| C6 | Cores | Geotechnical |
| C7 | CPT tests | Geotechnical |

## Workflow stages

| Code | Stage | Description |
|------|-------|-------------|
| S1 | Raw data | Unprocessed data as acquired by the instrument |
| S2 | QC | Quality-controlled data with artefacts flagged or removed |
| S3 | Processed data | Data processed into derived products (grids, mosaics) |
| S4 | Interpreted data | Final products with geological or geophysical interpretation |

## Format-to-category matrix

Which file formats appear in which category and stage combinations. See
[Supported formats](supported-formats.md) for detailed format descriptions.

### Bathymetry (C1)

| Format | Raw (S1) | QC (S2) | Processed (S3) | Interpreted (S4) |
|--------|----------|---------|-----------------|-------------------|
| KMALL | Primary | | | |
| XYZ | Primary | Primary | | Secondary |
| CSV | Primary | Primary | | Secondary |
| NetCDF | | | Primary | Primary |
| GeoTIFF | | | Primary | Primary |
| CSAR | | | Primary | |
| Float Grid (.flt) | | | Secondary | Primary/Secondary |
| ASCII Grid (.asc) | | | | Primary |
| HIPS Project | | | Primary | |
| Shapefile | Secondary | Secondary | Secondary | Secondary |
| GeoJSON | | | Secondary | Secondary |
| GeoPackage | | | Secondary | Secondary |
| KML/KMZ | | | | Secondary |
| File Geodatabase | Secondary | Secondary | Secondary | Primary/Secondary |
| XLS | Secondary | Secondary | Secondary | |

### Backscatter (C2)

| Format | Raw (S1) | QC (S2) | Processed (S3) | Interpreted (S4) |
|--------|----------|---------|-----------------|-------------------|
| KMALL | Primary | | | |
| XYZ | Primary | | | Primary |
| CSV | Primary | | | Primary |
| NetCDF | | | Primary | Primary |
| GeoTIFF | | Primary | Primary | Primary |
| CSAR | | | Primary | |
| Float Grid (.flt) | | | | Primary |
| ASCII Grid (.asc) | | | | Primary |
| GeoJSON | | | Secondary | Secondary |
| GeoPackage | | | Secondary | Secondary |
| KML/KMZ | | | | Secondary |
| File Geodatabase | Secondary | Secondary | Secondary | Primary/Secondary |

### Seismic (C3)

| Format | Raw (S1) | QC (S2) | Processed (S3) | Interpreted (S4) |
|--------|----------|---------|-----------------|-------------------|
| SEG-Y | Primary | | | |
| JSF | Primary | | | |
