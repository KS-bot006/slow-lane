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

## 2026-10-16, Phase 4: Scala history features

Commits:

- feat(scala): add history statistics and feature rows
- feat(scala): add feature job with Parquet output
- docs(results): add feature summary and history coverage tables

Exit check results:

- cd scala && sbt -batch test passed with 48 tests.
- FeatureJob ended with FEATURES OK on the slice (46532 rows) and on the full file (1862171 rows).
- The folder data/processed/features.parquet has the file _SUCCESS and 8 part files. The size is 54 MB.
- The file has 24 columns, no null value, and 1862171 different unique_key values.
- The latest train created_date is 2025-09-30T23:59:48. The earliest test created_date is 2025-10-01T00:00:14.
- feature_summary.csv shows rows in both windows. Source: results/tables/feature_summary.csv.

Feature summary (source: results/tables/feature_summary.csv):

- Train: 905441 rows, 228984 slow rows, slow share 0.2529.
- Test: 956730 rows, 218635 slow rows, slow share 0.2285.

History coverage, the share of rows whose key exists in the history window (source: results/tables/history_coverage.csv):

| Window | h1 (agency, type, descriptor) | h2 (type, borough) | h3 (ZIP) |
| --- | --- | --- | --- |
| train | 0.9995 | 0.9997 | 0.9999 |
| test | 0.9963 | 0.9969 | 1.0000 |

- The test window has lower h1 and h2 coverage than the train window. The test window is farther from the history window.
- A key that is not in the history gets the history-wide average. The model sees no missing value.

Bucket lists (source: results/tables/bucket_lists.csv):

- The file lists 100 descriptors and 30 location types from the history window, with their history counts.

Problems fixed:

- The first version of FeatureJob had 10 lines of more than 100 characters. The job was written again with shorter lines before the first run.
- A check of the Parquet schema with pandas failed because the project does not install pyarrow. The check used PySpark instead.

## 2026-10-16, Phase 5: Scala Spark concepts

Commits:

- feat(scala): add concepts job for partitions, lineage, cache, and recovery
- docs(results): add Spark concepts outputs and explanation

Exit check results:

- ConceptsJob ended with CONCEPTS OK on the slice and on the full file.
- partitions.csv has 34 rows. The three RDDs have 16, 16, and 2 partitions, and 16 + 16 + 2 = 34.
- lineage.txt contains the words ShuffledRDD and ShuffleDependency.
- cache_timing.csv has 6 rows. cache_storage.csv shows the cached RDD with 16 of 16 partitions.
- fault_tolerance.csv shows equal = true for the count and for the sum of the days.

Numbers from the full run (source: results/spark/):

- No cache: 2.180, 2.110, and 2.110 seconds. Cache: 7.521, 0.128, and 0.085 seconds. Source: cache_timing.csv.
- The first cached run is slower than the uncached runs, because it fills the cache.
- The recompute after unpersist takes 2.999 seconds. Source: fault_tolerance.csv.
- The cache holds 1958247816 bytes in memory and 41009876 bytes on disk. Source: cache_storage.csv.

Screenshots (human task, done): results/spark/ui/dag_job.png, stages.png, and storage.png. The file storage_rdd.png shows the partitions of the cached RDD.

Problems fixed:

- The first full run stopped when the computer shut down during the hold. The tables fault_tolerance.csv and spark_context.csv were not written. The job ran again, and the tables and screenshots come from the second run.
- The first dag_job.png showed the Jobs list and not the DAG of the job with the shuffle. The human saved the screenshot again from the page of job 9.
- The check is a simulation. A local run has no executor that can fail. This is stated in docs/spark_concepts.md.

## 2026-10-16, Phase 6: PySpark data and baselines

Commits:

- chore: ignore slice metric files
- feat(python): add config, session, and data loading with leakage guards
- feat(python): add metric functions and baselines
- test(python): add tests for metrics and leakage guards
- docs(results): add baseline metrics

Exit check results:

- .venv/bin/python -m pytest -q python/tests passed with 41 tests.
- Both baseline runs (slice and full file) ended with BASELINES OK.
- results/metrics_baselines.json has the entries majority and history_rule. Each has accuracy, precision, recall, f1, auc_roc, auc_pr, tp, fp, tn, fn, and test_rows.
- The majority accuracy is 0.7715, which equals 1 minus the test slow share of 0.2285. Its recall is 0. Source: results/metrics_baselines.json.
- All leakage guards passed on the full feature table.

Baseline metrics on the test window, 956730 rows, N = 3 days (source: results/metrics_baselines.json):

| Baseline | Accuracy | Precision | Recall | F1 | AUC ROC | AUC PR |
| --- | --- | --- | --- | --- | --- | --- |
| majority (predicts not slow) | 0.7715 | 0.0000 | 0.0000 | 0.0000 | 0.5000 | 0.2285 |
| history rule (h1_slow_rate at least 0.5) | 0.9032 | 0.8143 | 0.7469 | 0.7791 | 0.9504 | 0.8427 |

Notes:

- The history rule is a strong baseline. A Phase 7 model must beat F1 0.7791 and AUC ROC 0.9504 to show a gain.
- The majority baseline predicts the label that is most frequent in the train window. That label is 0.0.

Problems fixed:

- Three lines were longer than 88 characters. They were shortened before the commit.

## 2026-10-16, Phase 7: PySpark models and evaluation

Commits:

- feat(python): add feature pipeline and class weights
- feat(python): add evaluation tables and feature importance by group
- feat(python): add model builders and training script
- test(python): add tests for pipeline stages and importance grouping
- docs(results): add model metrics and result tables

Exit check results:

- .venv/bin/python -m pytest -q python/tests passed with 52 tests.
- The rehearsal with --fast on the slice and the full run both ended with TRAIN OK.
- For every model, tp + fp + tn + fn equals test_rows (956730). Source: results/metrics.json.
- The Random Forest importances sum to 1.0. Source: results/tables/feature_importance_groups_rf.csv.

Test metrics at the threshold 0.5, N = 3 days (source: results/tables/metrics_by_model.csv):

| Model | Accuracy | Precision | Recall | F1 | AUC ROC | AUC PR | Train seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| majority | 0.7715 | 0.0000 | 0.0000 | 0.0000 | 0.5000 | 0.2285 | |
| history_rule | 0.9032 | 0.8143 | 0.7469 | 0.7791 | 0.9504 | 0.8427 | |
| logistic_regression | 0.8910 | 0.7073 | 0.8922 | 0.7891 | 0.9560 | 0.8578 | 23.9 |
| random_forest | 0.8885 | 0.7027 | 0.8874 | 0.7843 | 0.9492 | 0.8094 | 122.0 |
| random_forest_no_history | 0.7129 | 0.4428 | 0.9920 | 0.6123 | 0.9277 | 0.7689 | 103.0 |

Findings:

- The Random Forest F1 is 0.7843. The history rule F1 is 0.7791. The Random Forest beats the rule on F1 by 0.0052.
- The Random Forest does not beat the history rule on AUC ROC (0.9492 against 0.9504) or on AUC PR (0.8094 against 0.8427).
- The Logistic Regression beats the Random Forest and the history rule on F1, AUC ROC, and AUC PR.
- The history features matter. Without them the Random Forest F1 falls from 0.7843 to 0.6123.
- The groups h1 and h2 hold 0.4327 and 0.2352 of the Random Forest importance. Source: results/tables/feature_importance_groups_rf.csv.
- The top two deciles hold 0.7245 of all slow requests. The lift of decile 1 is 3.75. Source: results/tables/decile_capture_rf.csv.
- The class weights make the models favor recall. The precision of the three models is lower than the precision of the history rule.
- The agency NYPD has a slow share of 0.0001, so the Random Forest finds no slow request there. Source: results/tables/metrics_by_agency_rf.csv.

Decisions:

- The Random Forest does not clearly beat the baselines. No setting was tuned on the test window, as the plan states.
- The results summary must report that the Logistic Regression is the best model on the test window.

Problems fixed:

- Two new tests had wrong expected values. The importance test used a vector of 13 values, but the lengths need 11. The decile test expected exactly 10 slow rows in decile 1, but the cut points are approximate quantiles and decile 1 holds 11 rows. The tests now check the property that matters. The code did not change.
- The plan lists the evaluation tables after the training script. The code order in the commits is changed, because the training script imports the table functions.
