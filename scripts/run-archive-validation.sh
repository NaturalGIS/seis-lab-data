#!/usr/bin/env bash
# Run scripts/validate_extractors.py against the production archive, in chunks.
#
# The validator is streamed in over stdin and its CSV streamed back, so nothing
# is ever written on the production server. Each chunk produces its own report,
# which is what makes a multi-hour run survivable: a dropped connection costs
# one chunk, not the night.
#
# Usage: bash scripts/run-archive-validation.sh <chunk-set>
# Override the defaults with the SLD_VALIDATION_HOST / SLD_VALIDATION_ROOT /
# SLD_VALIDATION_OUT environment variables.

set -uo pipefail
# NOTE: -e is deliberately absent. A chunk that fails (broken pipe, unreadable
# subtree) must not cancel the chunks after it.

HOST=${SLD_VALIDATION_HOST:-seis-lab-data-production}
ROOT=${SLD_VALIDATION_ROOT:-/mnt/seislab_data/surveys}
OUT=${SLD_VALIDATION_OUT:-${HOME}/archive-validation-reports}
VALIDATOR=scripts/validate_extractors.py
# The two-hop ssh route to production has no keepalives of its own, so a
# silently dead stream would hang until morning instead of failing.
KEEPALIVE=(-o ServerAliveInterval=30 -o ServerAliveCountMax=6)

# Chunks are "name<TAB>subpath<TAB>extension<TAB>expected", one per line. The
# expected counts come from the 2026-07-20 archive scan and are a sanity check
# only: os.walk skips an unreadable subtree silently and still exits 0, so a
# short report is otherwise indistinguishable from a complete one.
#
# SEG-Y needs one pass per extension, and the chunk boundaries follow the
# archive's own structure. The "previews" set is everything the IPMA
# preview-folder list covers (plus all of owf-seism-2024 and sat-uhrs-2025);
# "rest" is the raw and QC material, which the catalog still ingests.
read -r -d '' CHUNKS_KMALL <<'EOF'
kmall-2025	owf-2025	.kmall	5222
kmall-2024	owf-seism-2024	.kmall	442
EOF

read -r -d '' CHUNKS_SEGY_PREVIEWS <<'EOF'
2024-sgy	owf-seism-2024	.sgy	2814
2024-segy	owf-seism-2024/s13-uhrs	.segy	337
satuhrs-segy	sat-uhrs-2025	.segy	88
satuhrs-sgy	sat-uhrs-2025	.sgy	5
2025-innomar-proc	owf-2025/s10-innomar/s05-processed-data	.sgy	3348
2025-uhrs-proc	owf-2025/s13-uhrs/s05-processed-data	.sgy	3732
2025-chirp-proc	owf-2025/s08-chirp/s05-processed-data	.sgy	12206
EOF

read -r -d '' CHUNKS_SEGY_REST <<'EOF'
2025-uhrs-qc	owf-2025/s13-uhrs/s03-qc	.sgy	2352
2025-uhrs-raw-segy	owf-2025/s13-uhrs/s02-raw-data	.segy	1797
2025-uhrs-raw-sgy	owf-2025/s13-uhrs/s02-raw-data	.sgy	594
2025-innomar-raw	owf-2025/s10-innomar/s02-raw-data	.sgy	7169
2025-innomar-qc	owf-2025/s10-innomar/s03-qc	.sgy	6791
2025-chirp-qc	owf-2025/s08-chirp/s03-qc	.sgy	9693
2025-chirp-raw	owf-2025/s08-chirp/s02-raw-data	.sgy	15126
2025-reporting	owf-2025/s30-reporting	.sgy	9
EOF

case "${1:-}" in
    kmall)          CHUNKS=${CHUNKS_KMALL} ;;
    segy-previews)  CHUNKS=${CHUNKS_SEGY_PREVIEWS} ;;
    segy-rest)      CHUNKS=${CHUNKS_SEGY_REST} ;;
    *)
        cat >&2 <<USAGE
Usage: bash $0 <chunk-set>

  kmall          every .kmall in the two priority surveys (~3.5 h)
  segy-previews  the SEG-Y the IPMA preview-folder list covers, plus all of
                 owf-seism-2024 and sat-uhrs-2025 (~8.7 h)
  segy-rest      the remaining SEG-Y: raw and QC material (~8.9 h)

Run from the repository root. On a laptop, wrap it in caffeinate and stay on
mains power:

    caffeinate -i bash $0 segy-previews
USAGE
        exit 1
        ;;
esac

if [[ ! -f "${VALIDATOR}" ]]; then
    echo "Run from the repository root: ${VALIDATOR} not found." >&2
    exit 1
fi
mkdir -p "${OUT}"

date "+start: %Y-%m-%d %H:%M:%S  (set: ${1}, host: ${HOST})"
while IFS=$'\t' read -r name subpath extension expected; do
    [[ -z "${name}" ]] && continue
    echo
    date "+%H:%M:%S  >>> ${name}  (${expected} files expected)"
    ssh "${KEEPALIVE[@]}" "${HOST}" \
        "nice -n 19 ionice -c3 python3 - --root ${ROOT}/${subpath} --extension ${extension} --output /dev/stdout" \
        < "${VALIDATOR}" > "${OUT}/${name}.csv"
    got=$(( $(wc -l < "${OUT}/${name}.csv") - 1 ))
    if (( got < expected )); then
        echo "    WARNING: ${got} rows, expected ${expected} - unreadable subtree or dropped connection"
    else
        echo "    ${got} rows"
    fi
done <<< "${CHUNKS}"

echo
date "+end: %Y-%m-%d %H:%M:%S"
echo "reports in ${OUT}"
