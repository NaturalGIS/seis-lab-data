#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${1:-}" ]]; then
    echo "Usage: $0 <simulated-archive-root>" >&2
    exit 1
fi

SIMULATED_ARCHIVE_ROOT=$1

# This script needs GPL rsync (rsync.samba.org) for resume (--partial) and
# include/exclude filters.
RSYNC=rsync
if ! command -v "${RSYNC}" >/dev/null 2>&1 || "${RSYNC}" --version 2>&1 | grep -qi openrsync; then
    RSYNC=""
    for candidate in /opt/homebrew/bin/rsync /usr/local/bin/rsync; do
        if [[ -x "${candidate}" ]] && ! "${candidate}" --version 2>&1 | grep -qi openrsync; then
            RSYNC=${candidate}
            break
        fi
    done
fi
if [[ -z "${RSYNC}" ]]; then
    echo "GPL rsync not found. Install it." >&2
    exit 1
fi

# Fetch a single file. rsync resumes interrupted transfers (--partial)
fetch() {
    local remote_path=$1
    local local_dir=$2
    mkdir -p "${local_dir}"
    # -s (--protect-args): paths sent literally, so spaces in remote paths work
    # across rsync versions. --append-verify: resume from the partial offset at
    # full speed (no slow delta scan), then verify the whole-file checksum.
    "${RSYNC}" -aP -s --append-verify "seis-lab-data-production:${remote_path}" "${local_dir}/"
}

# Fetch a primary file together with all same-stem siblings in its directory
# (shapefile sidecars, FLT+.hdr, ECW+.eww/.prj, S-57 base .000 + updates, a
# GeoTIFF + its .aux.xml, ...). Pass the path to the primary file; the {stem}.*
# siblings are selected with rsync include/exclude filters (no remote glob), so
# it also works when the remote directory path contains spaces. The stem strips
# only the last extension, so it matches sibling files but not unrelated ones.
fetch_with_sidecars() {
    local remote_primary=$1
    local local_dir=$2
    local base
    base=$(basename "${remote_primary}")
    local stem=${base%.*}
    local remote_dir
    remote_dir=$(dirname "${remote_primary}")
    mkdir -p "${local_dir}"
    "${RSYNC}" -aP -s --append-verify --include="${stem}.*" --exclude="*" \
        "seis-lab-data-production:${remote_dir}/" "${local_dir}/"
}

# raw bathymetry (82MB)
fetch /mnt/seislab_data/surveys/owf-seism-2024/s06-mbes/s02-raw-data/01-EM712/2024-09-29/0425_20240929_004829_MarioRuivo.kmall \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-seism-2024/s06-mbes/s02-raw-data/01-EM712/2024-09-29/
fetch /mnt/seislab_data/surveys/owf-seism-2024/s06-mbes/s02-raw-data/01-EM712/2024-09-29/0426_20240929_020125_MarioRuivo.kmall \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-seism-2024/s06-mbes/s02-raw-data/01-EM712/2024-09-29/
fetch /mnt/seislab_data/surveys/owf-seism-2024/s06-mbes/s02-raw-data/01-EM712/2024-09-28/0419_20240928_184829_MarioRuivo.kmall \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-seism-2024/s06-mbes/s02-raw-data/01-EM712/2024-09-28/

# processed bathymetry (~1GB)
fetch /mnt/seislab_data/surveys/owf-seism-2024/s06-mbes/s05-processed-data/FIG_All_Mainlines_and_Xlines_MBES_Grid_4m.xyz \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-seism-2024/s06-mbes/s05-processed-data/
fetch /mnt/seislab_data/surveys/owf-seism-2024/s06-mbes/s05-processed-data/LEI_All_Mainline_and_Xline_MBES_Grid_4m.xyz \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-seism-2024/s06-mbes/s05-processed-data/

# HUGE FILE!: seismic uhrs raw data (139GB)
fetch '/mnt/seislab_data/surveys/owf-seism-2024/s13-uhrs/s02-raw-data/BACKED UP - FIGUEIRA/FIG-24-M001/FIG-24-M001_rev1.segy' \
    "${SIMULATED_ARCHIVE_ROOT}/surveys/owf-seism-2024/s13-uhrs/s02-raw-data/BACKED UP - FIGUEIRA/FIG-24-M001"

# HUGE FILE!: seismic uhrs raw data (84GB)
fetch '/mnt/seislab_data/surveys/owf-seism-2024/s13-uhrs/s02-raw-data/BACKED UP - FIGUEIRA/FIG-24-M010/FIG-24-M010_rev1.segy' \
    "${SIMULATED_ARCHIVE_ROOT}/surveys/owf-seism-2024/s13-uhrs/s02-raw-data/BACKED UP - FIGUEIRA/FIG-24-M010"

# seismic uhrs qc data (~2GB)
fetch /mnt/seislab_data/surveys/owf-seism-2024/s13-uhrs/s03-qc/s03-bstk/FIG-24-M001_BSTK.sgy \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-seism-2024/s13-uhrs/s03-qc/s03-bstk/

# HUGE FILE!: seismic uhrs processed prestack data (~138GB)
fetch /mnt/seislab_data/surveys/owf-seism-2024/s13-uhrs/s05-processed-data/s01-prestk/s01-mul/FIG-24-M001_CMP_MUL.sgy \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-seism-2024/s13-uhrs/s05-processed-data/s01-prestk/s01-mul/

# seismic uhrs processed mul data (~2GB)
fetch /mnt/seislab_data/surveys/owf-seism-2024/s13-uhrs/s05-processed-data/s02-poststk/s01-twt/s01-mul/FIG-24-M001_MUL.sgy \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-seism-2024/s13-uhrs/s05-processed-data/s02-poststk/s01-twt/s01-mul/

# seismic uhrs processed mig data (~2GB)
fetch /mnt/seislab_data/surveys/owf-seism-2024/s13-uhrs/s05-processed-data/s02-poststk/s01-twt/s02-mig/FIG-24-M001_MIG.sgy \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-seism-2024/s13-uhrs/s05-processed-data/s02-poststk/s01-twt/s02-mig/

# seismic uhrs processed dpt data (~4GB)
fetch /mnt/seislab_data/surveys/owf-seism-2024/s13-uhrs/s05-processed-data/s02-poststk/s02-dpt/s02-mig/FIG-24-M001_DPT.sgy \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-seism-2024/s13-uhrs/s05-processed-data/s02-poststk/s02-dpt/s02-mig/

# seismic uhrs RMS velocities (~2.2GB)
fetch /mnt/seislab_data/surveys/owf-seism-2024/s13-uhrs/s05-processed-data/s03-velocities/s02-vel-rms/FIG-24-M001_VEL_RMS.sgy \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-seism-2024/s13-uhrs/s05-processed-data/s03-velocities/s02-vel-rms/

# seismic uhrs interval velocities (~2.2GB)
fetch /mnt/seislab_data/surveys/owf-seism-2024/s13-uhrs/s05-processed-data/s03-velocities/s03-vel-int/FIG-24-M001_VEL_INT.sgy \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-seism-2024/s13-uhrs/s05-processed-data/s03-velocities/s03-vel-int/

# seismic raster files
fetch /mnt/seislab_data/surveys/owf-seism-2024/s02-preparation/s02-lineplan/s01-final/01-Line_Plan/Reference_bathymetry/EMODnet/F3_2022.tif \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-seism-2024/s02-preparation/s02-lineplan/s01-final/01-Line_Plan/Reference_bathymetry/

fetch /mnt/seislab_data/surveys/owf-seism-2024//s04-gis-master-survey/s01-final/negative_depth_seism2024/negative_depth_FIG.tif \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-seism-2024//s04-gis-master-survey/s01-final/negative_depth_seism2024/

fetch /mnt/seislab_data/surveys/owf-seism-2024/s04-gis-master-survey/s01-final/negative_depth_seism2024/FIG_All_Mainlines_and_Xlines_MBES_Grid_4m.tif \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-seism-2024/s04-gis-master-survey/s01-final/negative_depth_seism2024/

# shapefiles + sidecars
fetch_with_sidecars /mnt/seislab_data/surveys/owf-seism-2024/s02-preparation/s02-lineplan/s01-final/01-Line_Plan/Reference_bathymetry/ingmar.shp \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-seism-2024/s02-preparation/s02-lineplan/s01-final/01-Line_Plan/Reference_bathymetry/

fetch_with_sidecars /mnt/seislab_data/surveys/owf-seism-2024/s09-sbp-other/s05-processed-data/s01-twt/oars/2024-09-29/NAV/ShapeFiles/FIG-LEI-24-T002_20240928184838_000.shp \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-seism-2024/s09-sbp-other/s05-processed-data/s01-twt/oars/2024-09-29/NAV/ShapeFiles/

# ===========================================================================
# GDAL-supported samples for the metadata-stripping / quick-preview assessment.
# One sizeable file per format (the largest sensible instance where one exists),
# broad raster + vector coverage. GeoTIFF DTM, XYZ and small shapefiles are
# already covered above, so they are not repeated here.
# ===========================================================================

# --- GDAL raster samples ---

# GeoTIFF, scanned/georeferenced IH chart (~1GB). Carries a .tif.aux.xml sidecar
# (GDAL PAM: stats + georef/metadata) plus embedded TIFF tags, so it is the best
# case for the metadata-stripping assessment. Pulled with its sidecar.
fetch_with_sidecars /mnt/seislab_data/surveys/sat-uhrs-2025/s04-gis-master-survey/s01-final/mapas_georef/IH_SED_SUP_folha05_2005_alterado.tif \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/sat-uhrs-2025/s04-gis-master-survey/s01-final/mapas_georef/

# ESRI ASCII Grid / AAIGrid (~6.4GB). Plain ASCII: large and slow to parse, and
# no embedded CRS (would need a .prj, none present here). Single file.
fetch /mnt/seislab_data/surveys/owf-2025/s06-mbes/s05-processed-data/03_DTM_POINTFILE/04_ASC/FIG25_MBES_AVG_ZH_2m_asc_TM06_v0_EXT.asc \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-2025/s06-mbes/s05-processed-data/03_DTM_POINTFILE/04_ASC/

# ESRI float grid / EHdr (~7.5GB). The .hdr is REQUIRED by GDAL to read the .flt;
# .flt.gi / .flt.xml are auxiliary. Pulled with all same-stem siblings.
fetch_with_sidecars /mnt/seislab_data/surveys/owf-2025/s17-magnetometer/s03-qc/s01-24h-deliverables/s02-flt/20250819/OI_634_A7805_TVG_LEI_25_nT_Residual_LMB04_M081.flt \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-2025/s17-magnetometer/s03-qc/s01-24h-deliverables/s02-flt/20250819/

# ECW (~3MB). Needs the (proprietary) ECW driver/plugin in GDAL to read. Ships a
# .eww world file and a .prj; pulled as sidecars.
fetch_with_sidecars /mnt/seislab_data/surveys/mineplat-sampling-2019/s06-mbes/s10-tracklines/2019-04-04/BACK_20190404.ecw \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/mineplat-sampling-2019/s06-mbes/s10-tracklines/2019-04-04/

# --- GDAL vector samples ---

# Line shapefile, the vector "monster" (~1GB .shp). Needs .shx/.dbf/.prj sidecars.
fetch_with_sidecars /mnt/seislab_data/surveys/owf-2025/s28-tracks/s02-final/FIG25_SBP_CHIRP_Trackplot_ln_TM06_v1_EXT.shp \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-2025/s28-tracks/s02-final/

# DXF / CAD (~25MB). Single file; no embedded CRS in the DXF itself.
fetch /mnt/seislab_data/surveys/owf-2025/s04-gis-master-survey/Permit_areas.dxf \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-2025/s04-gis-master-survey/

# AutoCAD DWG / CAD, georeferenced survey line plan (~0.05MB). Binary CAD read by the
# OGR DWG driver (a different path from the ASCII DXF above). Carries a CRS (TM06), so
# it exercises bbox/CRS extraction. Single file.
fetch /mnt/seislab_data/surveys/owf-2026/s02-preparation/s02-lineplan/s01-final/2026-04-21_Main_LEI_Survey_Lines/DWG/105634-Line_Plan_TM06_20260421.dwg \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-2026/s02-preparation/s02-lineplan/s01-final/2026-04-21_Main_LEI_Survey_Lines/DWG/

# AutoCAD DWG, largest instance (~15MB; spaces in the remote path). Vessel general-
# arrangement drawing: mechanical CAD, likely no usable georeferencing; included as the
# size / metadata-stripping stress case. Single file.
fetch '/mnt/seislab_data/surveys/owf-seism-2024/s02-preparation/s01-documents/1.Vessel_MarioRuivo_Equipment_info/PLANO DE ARRANJO GERAL FINAL _ GRAFICA.dwg' \
    "${SIMULATED_ARCHIVE_ROOT}/surveys/owf-seism-2024/s02-preparation/s01-documents/1.Vessel_MarioRuivo_Equipment_info/"

# GeoPackage (~0.3MB). Self-contained SQLite container; single file.
fetch /mnt/seislab_data/surveys/owf-2025/s02-preparation/s02-lineplan/s02-old/20250428_LinePlan/IPMA_2025_Prelim_Survey_Line_Plan_20250428.gpkg \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-2025/s02-preparation/s02-lineplan/s02-old/20250428_LinePlan/

# GeoJSON (~0.2MB). Single file; WGS84 by spec unless a crs member says otherwise.
fetch /mnt/seislab_data/surveys/owf-seism-2024/s02-preparation/s02-lineplan/s02-old/LinePlan_Planeamento_preliminar/Planning_Preliminary_lineplan.geojson \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-seism-2024/s02-preparation/s02-lineplan/s02-old/LinePlan_Planeamento_preliminar/

# KML (~0.7MB; spaces in the remote path). Single file; KML coords are WGS84.
fetch '/mnt/seislab_data/surveys/mineplat-geophysical-2019/s06-mbes/s04-processing-flows/PDS Projects/Testes_Pinger/LinhaCosta_UTM29N.kml' \
    "${SIMULATED_ARCHIVE_ROOT}/surveys/mineplat-geophysical-2019/s06-mbes/s04-processing-flows/PDS Projects/Testes_Pinger/"

# S-57 ENC chart (~0.9MB; spaces in the remote path). Multi-file dataset: base
# cell .000 plus sequential updates .001..008 (+ .TXT/.met). GDAL OGR S57 driver
# applies the updates onto the base. Pulled as same-stem siblings.
fetch_with_sidecars '/mnt/seislab_data/surveys/mineplat-2017/s06-mbes/s02-raw-data/2017_04_01_MBES/Projects Common Files/S-57/PT324205/PT324205.000' \
    "${SIMULATED_ARCHIVE_ROOT}/surveys/mineplat-2017/s06-mbes/s02-raw-data/2017_04_01_MBES/Projects Common Files/S-57/PT324205/"
