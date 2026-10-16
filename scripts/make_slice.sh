#!/usr/bin/env bash
# Keep the header and every 40th data line. Later phases use the slice for quick runs.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

SOURCE_FILE="data/raw/311_2025.tsv"
SLICE_FILE="data/raw/311_2025_slice.tsv"
SLICE_STEP=40

echo "+ awk 'NR == 1 || (NR - 1) % ${SLICE_STEP} == 0' ${SOURCE_FILE} > ${SLICE_FILE}"
awk -v step="${SLICE_STEP}" 'NR == 1 || (NR - 1) % step == 0' "${SOURCE_FILE}" \
  > "${SLICE_FILE}.tmp"
mv "${SLICE_FILE}.tmp" "${SLICE_FILE}"
echo "Slice rows: $(( $(wc -l < "${SLICE_FILE}") - 1 ))"
