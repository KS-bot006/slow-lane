#!/usr/bin/env bash
# Build the Scala jar and run one job with spark-submit.
# Usage: bash scripts/run_scala.sh JobName [job arguments]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if [ "$#" -lt 1 ]; then
  echo "Usage: bash scripts/run_scala.sh JobName [job arguments]" >&2
  exit 2
fi
JOB_NAME="$1"
shift

property() {
  grep -E "^$1=" config/project.properties | head -n 1 | cut -d= -f2-
}
SPARK_MASTER="$(property spark_master)"
DRIVER_MEMORY="$(property spark_driver_memory)"

echo "+ (cd scala && sbt -batch package)"
(cd scala && sbt -batch package)

JAR_FILE="$(ls scala/target/scala-2.12/*.jar | head -n 1)"
echo "+ spark-submit --class nyc311.${JOB_NAME} --master ${SPARK_MASTER}" \
  "--driver-memory ${DRIVER_MEMORY} ${JAR_FILE} $*"
spark-submit --class "nyc311.${JOB_NAME}" --master "${SPARK_MASTER}" \
  --driver-memory "${DRIVER_MEMORY}" "${JAR_FILE}" "$@"
