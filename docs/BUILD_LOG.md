# Build log

## 2026-10-15, Phase 0: Skeleton and environment

Commits:

- chore: add project skeleton, ignore rules, and pinned requirements
- build(scala): add sbt project and smoke job
- build: add environment check and Spark run script
- test: add Python smoke test and style check script
- docs: add build plan, agent rules, and build log

Exit check results:

- bash scripts/check_env.sh printed PASS for each tool and ended with ALL PASS.
- bash scripts/run_scala.sh Smoke printed SMOKE OK 500500.
- .venv/bin/python -m pytest -q python/tests passed with 9 tests.
- .venv/bin/python scripts/ste_check.py ended with STE CHECK OK.

Notes:

- The tools run in a Docker container. The image has Java 17, Spark 3.5.9, sbt 1.10.7, and Python 3.11.
- Smoke starts local[2] only when spark-submit gives no master. The script passes local[*] from the config.

## 2026-10-16, Phase 1: Data download

Commits:

- feat(data): add city API download script with retry and manifest
- feat(data): add download verification and slice script
- docs(data): record the download manifest

Exit check results:

- scripts/download_data.py ended with DOWNLOAD OK and 3655042 rows. Source: data/MANIFEST.json.
- scripts/verify_download.py ended with VERIFY OK. The header, field counts, unique keys, dates, month counts, and SHA-256 all match.
- scripts/make_slice.sh wrote data/raw/311_2025_slice.tsv with 91376 rows.
- The share of rows without closed_date is 1.4952 percent. The status Closed has 3602475 rows.
- No new borough value appeared. The value Unspecified has 2607 rows.

Notes:

- The city API returned HTTP 500 and 503 several times. The retry rules recovered each time. No month needed a manual restart.
