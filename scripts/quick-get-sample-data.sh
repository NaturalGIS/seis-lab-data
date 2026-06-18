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

# Fetch a shapefile together with all its sidecar files (.shx, .dbf, .prj, ...).
# Pass the path to the .shp; the {stem}.* siblings are selected with rsync
# include/exclude filters (no remote glob), so it also works when the remote
# directory path contains spaces.
fetch_shapefile() {
    local remote_shp=$1
    local local_dir=$2
    local stem
    stem=$(basename "${remote_shp}" .shp)
    local remote_dir
    remote_dir=$(dirname "${remote_shp}")
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
fetch_shapefile /mnt/seislab_data/surveys/owf-seism-2024/s02-preparation/s02-lineplan/s01-final/01-Line_Plan/Reference_bathymetry/ingmar.shp \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-seism-2024/s02-preparation/s02-lineplan/s01-final/01-Line_Plan/Reference_bathymetry/

fetch_shapefile /mnt/seislab_data/surveys/owf-seism-2024/s09-sbp-other/s05-processed-data/s01-twt/oars/2024-09-29/NAV/ShapeFiles/FIG-LEI-24-T002_20240928184838_000.shp \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-seism-2024/s09-sbp-other/s05-processed-data/s01-twt/oars/2024-09-29/NAV/ShapeFiles/
