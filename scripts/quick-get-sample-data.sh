#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${1:-}" ]]; then
    echo "Usage: $0 <simulated-archive-root>" >&2
    exit 1
fi

SIMULATED_ARCHIVE_ROOT=$1

fetch() {
    local remote_path=$1
    local local_dir=$2
    local filename
    filename=$(basename "${remote_path}")
    if [[ -f "${local_dir}/${filename}" ]]; then
        echo "Skipping ${filename} (already present)"
        return
    fi
    mkdir -p "${local_dir}"
    scp "seis-lab-data-production:${remote_path}" "${local_dir}/"
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
fetch '/mnt/seislab_data/surveys/owf-seism-2024/s13-uhrs/s02-raw-data/BACKED\ UP\ -\ FIGUEIRA/FIG-24-M001/FIG-24-M001_rev1.segy' \
    "${SIMULATED_ARCHIVE_ROOT}/surveys/owf-seism-2024/s13-uhrs/s02-raw-data/BACKED UP - FIGUEIRA/FIG-24-M001"

# HUGE FILE!: seismic uhrs raw data (84GB)
fetch '/mnt/seislab_data/surveys/owf-seism-2024/s13-uhrs/s02-raw-data/BACKED\ UP\ -\ FIGUEIRA/FIG-24-M010/FIG-24-M010_rev1.segy' \
    "${SIMULATED_ARCHIVE_ROOT}/surveys/owf-seism-2024/s13-uhrs/s02-raw-data/BACKED UP - FIGUEIRA/FIG-24-M010"

# seismic uhrs qc data (~2GB)
fetch /mnt/seislab_data/surveys/owf-seism-2024/s13-uhrs/s03-qc/s03-bstk/FIG-24-M001_BSTK.sgy \
    "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-seism-2024/s13-uhrs/s03-qc/s03-bstk/

# HUGE FILE!: seismic uhrs processed prestack data (~138GB)
# fetch /mnt/seislab_data/surveys/owf-seism-2024/s13-uhrs/s05-processed-data/s01-prestk/s01-mul/FIG-24-M001_CMP_MUL.sgy \
#     "${SIMULATED_ARCHIVE_ROOT}"/surveys/owf-seism-2024/s13-uhrs/s05-processed-data/s01-prestk/s01-mul/

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
