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

## 2026-10-16, Phase 2: Scala parsing, cleaning, and profile

Commits:

- feat(scala): add constants, args, config, and CSV writer
- refactor(scala): shorten a long line in the smoke job
- feat(scala): add line parser and cleaning rules
- test(scala): add unit tests for parser, cleaning, windows, and CSV
- feat(scala): add profile job with RDD operations
- docs(results): add profile tables

Exit check results:

- cd scala && sbt -batch test passed with 25 tests.
- ProfileJob on the slice ended with reconcile: ok and PROFILE OK.
- ProfileJob on the full file read 3655043 lines and ended with reconcile: ok and PROFILE OK.
- The monthly counts show 12 months, 2025-01 to 2025-12. Source: results/tables/profile_monthly_counts.csv.
- The quantiles rise from 0.2757 days (median) to 207.86 days (0.99). The maximum is 640.48 days. Source: results/tables/profile_duration_quantiles.csv.
- The histogram counts add up to 3596374 clean rows. Source: results/tables/profile_duration_hist.csv.
- The open_no_closed_date drops are 54649 rows, which is 1.495 percent of the data rows. verify_download.py printed 1.4952 percent.

Row counts (source: results/tables/profile_row_counts.csv):

- Clean rows: 3596374.
- Drops: open_no_closed_date 54649, status_not_closed 3942, closed_before_created 77.
- Rejects: none.
- Windows: history 1734203, train 905441, test 956730.

Problems fixed:

- The first full run printed RejectedExecutionException traces after PROFILE OK. The cause was an unpersist call that did not wait before the context stopped. The job now calls unpersist with blocking = true. The tables did not change.
- The sbt package step prints a warning that it found multiple main classes. This is an sbt message, not a compiler warning. The jar and the job are not affected.

## 2026-10-16, Phase 3: Scala threshold and rankings

Commits:

- feat(scala): add statistics helpers, group keys, and shared pipeline
- refactor(scala): share job helpers from Pipeline in the profile job
- feat(scala): add threshold rule and run parameters
- test(scala): add tests for statistics helpers and group keys
- feat(scala): add threshold job with fixed selection rule
- feat(scala): add ranking job with multi-level aggregation and join
- docs(results): add threshold and ranking tables

Exit check results:

- cd scala && sbt -batch test passed with 40 tests. The Wilson values match the plan within 0.001.
- ThresholdJob on the full file ended with THRESHOLD OK. data/processed/run_params.properties has slow_threshold_days=3.
- RankingJob on the full file ended with RANKING OK and one reconcile: ok line for each of the 9 grains. Each grain sums to 3596374 clean rows.
- In every row of every ranking and pattern table, wilson_low is at most slow_share, and slow_share is at most wilson_high.
- The smallest n in rank_complaint_type.csv is 623. All ranking tables keep groups with n of at least 500.

Threshold selection (source: results/tables/threshold_selection.csv):

- History window rows: 1734203.
- Slow share above 1 day: 0.3813. Above 3 days: 0.2393. Above 7 days: 0.1585.
- The default of 3 days is inside share_min and share_max, so N is 3.

Notes:

- type_owner.csv keeps every complaint type, as the plan states no minimum group size for it. Its smallest n is 1.

Problems fixed:

- The first ranking run wrote n as 537219.0. The cause was that Scala widened the Long value to Double in a mixed Seq. The code now types the Seq as Seq[Any]. The tables were written again.
- The compiler gave a warning that a type was inferred as AnyVal. The cause was the same mixed Seq in ThresholdJob. The code now types the Seq as Seq[Any].
