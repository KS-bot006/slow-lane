#!/usr/bin/env bash
# Run every stage of the build in order. The script stops at the first failure.
# Usage: bash scripts/run_all.sh [--skip-download]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

PYTHON=".venv/bin/python"
export PYTHONPATH=python

SKIP_DOWNLOAD=0
INPUT="data/raw/311_2025.tsv"
PROCESSED="data/processed"
RESULTS="results"
TABLES="results/tables"
SPARK_OUT="results/spark"
BASELINES_OUT="results/metrics_baselines.json"
TRAIN_ARGS=()

for argument in "$@"; do
  case "${argument}" in
    --skip-download) SKIP_DOWNLOAD=1 ;;
    *) echo "Unknown option: ${argument}" >&2; exit 2 ;;
  esac
done

# Print the name and the command of a stage, run it, and print the time.
stage() {
  local name="$1"
  shift
  echo "=== STAGE ${name}"
  echo "+ $*"
  local start="${SECONDS}"
  "$@"
  echo "=== DONE ${name} in $((SECONDS - start)) seconds"
}

# Skip the download if the manifest exists and the file passes the verification.
download() {
  if [ "${SKIP_DOWNLOAD}" -eq 1 ]; then
    echo "The download is skipped by --skip-download."
    return 0
  fi
  if [ -f data/MANIFEST.json ] && "${PYTHON}" scripts/verify_download.py > /dev/null 2>&1; then
    echo "The download is skipped. data/MANIFEST.json exists and the verification passes."
    return 0
  fi
  "${PYTHON}" scripts/download_data.py
  "${PYTHON}" scripts/verify_download.py
  bash scripts/make_slice.sh
}

summary() {
  "${PYTHON}" -m nyc311.summary
  "${PYTHON}" -m nyc311.summary --check
}

stage "check_env" bash scripts/check_env.sh
stage "download" download
stage "sbt test" bash -c 'cd scala && sbt -batch test'
stage "ProfileJob" bash scripts/run_scala.sh ProfileJob --input "${INPUT}" --out "${TABLES}"
stage "ThresholdJob" bash scripts/run_scala.sh ThresholdJob --input "${INPUT}" \
  --out "${TABLES}" --processed "${PROCESSED}"
stage "RankingJob" bash scripts/run_scala.sh RankingJob --input "${INPUT}" \
  --out "${TABLES}" --processed "${PROCESSED}"
stage "FeatureJob" bash scripts/run_scala.sh FeatureJob --input "${INPUT}" \
  --out "${TABLES}" --processed "${PROCESSED}"
stage "ConceptsJob" bash scripts/run_scala.sh ConceptsJob --input "${INPUT}" \
  --out "${SPARK_OUT}" --hold-seconds 0
stage "pytest" "${PYTHON}" -m pytest -q python/tests
stage "baselines" "${PYTHON}" -m nyc311.baselines --processed "${PROCESSED}" \
  --out "${BASELINES_OUT}"
stage "train" "${PYTHON}" -m nyc311.train --processed "${PROCESSED}" \
  --results "${RESULTS}" ${TRAIN_ARGS[@]+"${TRAIN_ARGS[@]}"}
stage "plots" "${PYTHON}" -m nyc311.plots --results "${RESULTS}" --processed "${PROCESSED}"
stage "summary" summary
stage "ste_check" "${PYTHON}" scripts/ste_check.py

echo "ALL STAGES OK"
