#!/usr/bin/env bash
# Check the tools and the versions that the build needs.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

FAILED=0

# Print PASS or FAIL for one check. Arguments: name, actual text, expected pattern.
report() {
  local name="$1" actual="$2" pattern="$3"
  if [[ "${actual}" =~ ${pattern} ]]; then
    echo "PASS ${name}: ${actual}"
  else
    echo "FAIL ${name}: found '${actual}', expected a match for '${pattern}'"
    FAILED=1
  fi
}

echo "+ java -version"
report "java" "$(java -version 2>&1 | head -n 1)" '"17\.'

echo "+ python3.11 --version"
report "python" "$(python3.11 --version 2>&1)" '^Python 3\.11\.'

echo "+ spark-submit --version"
SPARK_TEXT="$(spark-submit --version 2>&1)"
SPARK_VERSION="$(echo "${SPARK_TEXT}" | grep -m 1 -oE 'version [0-9]+\.[0-9]+\.[0-9]+' | cut -d' ' -f2)"
SCALA_VERSION="$(echo "${SPARK_TEXT}" | grep -m 1 -oE 'Scala version [0-9]+\.[0-9]+\.[0-9]+' | cut -d' ' -f3)"
report "spark" "${SPARK_VERSION}" '^3\.5\.9$'
report "scala" "${SCALA_VERSION}" '^2\.12\.'

echo "+ sbt --version"
report "sbt" "$(sbt --version 2>&1 | tail -n 1)" '1\.10\.7'

echo "+ git --version"
report "git" "$(git --version)" '^git version'

if [ -n "${SPARK_HOME:-}" ]; then
  PYTHON_BIN="python3.11"
  [ -x .venv/bin/python ] && PYTHON_BIN=".venv/bin/python"
  echo "+ ${PYTHON_BIN} -c 'import pyspark'"
  PYSPARK_VERSION="$("${PYTHON_BIN}" -c 'import pyspark; print(pyspark.__version__)')"
  report "pyspark equals spark" "${PYSPARK_VERSION}" "^${SPARK_VERSION}\$"
fi

if [ "${FAILED}" -eq 0 ]; then
  echo "ALL PASS"
else
  echo "SOME CHECKS FAILED"
  exit 1
fi
