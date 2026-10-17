# Results summary

Python code writes this file from the result files. Every number comes from a file in results/ or from data/MANIFEST.json. The source column or the source line names the file.

## Dataset

The data is the NYC 311 service request dataset erm2-nwe9 from NYC Open Data. It holds 3655042 requests that were created in 2025. Clean rows, dropped rows, and rejected lines add up to the number of requests.

| Item | Value | Source |
| --- | --- | --- |
| Dataset ID | erm2-nwe9 | data/MANIFEST.json |
| Download time (UTC) | 2026-10-16T02:14:35Z | data/MANIFEST.json |
| Columns used | 11 | data/MANIFEST.json |
| Requests downloaded | 3655042 | data/MANIFEST.json |
| Lines rejected by the parser | 0 | results/tables/profile_row_counts.csv |
| Clean rows | 3596374 | results/tables/profile_row_counts.csv |
| Clean rows in the history window | 1734203 | results/tables/profile_row_counts.csv |
| Clean rows in the train window | 905441 | results/tables/profile_row_counts.csv |
| Clean rows in the test window | 956730 | results/tables/profile_row_counts.csv |
| Rows dropped: closed_before_created | 77 | results/tables/profile_row_counts.csv |
| Rows dropped: open_no_closed_date | 54649 | results/tables/profile_row_counts.csv |
| Rows dropped: status_not_closed | 3942 | results/tables/profile_row_counts.csv |
| Share of open requests (no closed date) | 1.50% | results/tables/profile_row_counts.csv |

## Target

A request is slow when it takes more than 3 days to close. ThresholdJob selected N = 3 from the history window. The candidates were 1, 3, 7 days.

Slow share of each candidate in the history window. Source: results/tables/threshold_selection.csv.

| N (days) | Slow share | Selected |
| --- | --- | --- |
| 1 | 38.13% | no |
| 3 | 23.93% | yes |
| 7 | 15.85% | no |

Slow share of each window.

| Window | Rows | Slow rows | Slow share | Source |
| --- | --- | --- | --- | --- |
| history | 1734203 | 415003 | 23.93% | results/tables/threshold_selection.csv |
| train | 905441 | 228984 | 25.29% | results/tables/feature_summary.csv |
| test | 956730 | 218635 | 22.85% | results/tables/feature_summary.csv |

## Spark processing

The master is local[*]. The default parallelism is 22 and the computer has 22 cores. Source: results/spark/spark_context.csv.

| RDD | Partitions | Rows | Source |
| --- | --- | --- | --- |
| base | 16 | 3655043 | results/spark/partitions.csv |
| repartition_16 | 16 | 3655043 | results/spark/partitions.csv |
| coalesce_2 | 2 | 3655043 | results/spark/partitions.csv |

The lineage lists 13 narrow dependencies and 1 shuffle dependency. Source: results/spark/lineage.txt.

Seconds for one count of the clean rows. Source: results/spark/cache_timing.csv.

| Variant | Run 1 (s) | Run 2 (s) | Run 3 (s) | Mean (s) |
| --- | --- | --- | --- | --- |
| cache | 7.521 | 0.128 | 0.085 | 2.578 |
| no_cache | 2.180 | 2.110 | 2.110 | 2.133 |

The first cached run takes 7.521 seconds, because it fills the cache. The mean of the next cached runs is 0.106 seconds. The mean without the cache is 2.133 seconds.

The cache holds 16 of 16 partitions, with 1958247816 bytes in memory and 41009876 bytes on disk. Source: results/spark/cache_storage.csv.

After unpersist, Spark recomputes the clean rows in 3.000 seconds. The count and the sum of the days are the same before and after. This is a simulation, because a local run has no executor that can fail. Source: results/spark/fault_tolerance.csv.

## Slowness findings

The 5 slowest groups. Source: results/tables/rank_complaint_type.csv.

| Problem types | Requests | Slow share | 95% interval | Dominant agency |
| --- | --- | --- | --- | --- |
| NOISE - HELICOPTER | 10881 | 100.0% | 100.0% to 100.0% | EDC |
| MOBILE FOOD VENDOR | 4894 | 99.9% | 99.7% to 99.9% | DOHMH |
| TAXI COMPLAINT | 7335 | 99.9% | 99.7% to 99.9% | TLC |
| FOR HIRE VEHICLE COMPLAINT | 15746 | 99.8% | 99.7% to 99.8% | TLC |
| NON-RESIDENTIAL HEAT | 1172 | 99.7% | 99.3% to 99.9% | DOHMH |

The 5 slowest groups. Source: results/tables/rank_agency.csv.

| Agencies | Requests | Slow share | 95% interval |
| --- | --- | --- | --- |
| EDC | 10881 | 100.0% | 100.0% to 100.0% |
| OOS | 1111 | 99.7% | 99.2% to 99.9% |
| TLC | 30065 | 82.7% | 82.3% to 83.1% |
| DOE | 1737 | 79.2% | 77.2% to 81.0% |
| DPR | 95422 | 65.2% | 64.9% to 65.5% |

The 5 slowest groups. Source: results/tables/rank_borough.csv.

| Boroughs | Requests | Slow share | 95% interval |
| --- | --- | --- | --- |
| UNSPECIFIED | 2368 | 50.8% | 48.8% to 52.8% |
| STATEN ISLAND | 131862 | 27.7% | 27.4% to 27.9% |
| MANHATTAN | 708911 | 27.5% | 27.4% to 27.6% |
| BROOKLYN | 1062455 | 24.9% | 24.8% to 25.0% |
| BRONX | 831605 | 23.5% | 23.4% to 23.6% |

The 5 slowest groups. Source: results/tables/rank_zip.csv.

| ZIP codes | Requests | Slow share | 95% interval |
| --- | --- | --- | --- |
| 11430 | 3370 | 71.5% | 69.9% to 73.0% |
| 10000 | 720 | 54.4% | 50.8% to 58.0% |
| 10280 | 955 | 49.9% | 46.8% to 53.1% |
| 10044 | 766 | 47.8% | 44.3% to 51.3% |
| 10037 | 10523 | 42.0% | 41.0% to 42.9% |

Agencies DOHMH and TLC are each the dominant agency of 2 of the 5 slowest problem types. Source: results/tables/type_owner.csv.

## Model results

Metrics of the slow class on the test window at the threshold 0.5. Source: results/tables/metrics_by_model.csv.

| Model | Accuracy | Precision | Recall | F1 | AUC ROC | AUC PR |
| --- | --- | --- | --- | --- | --- | --- |
| Majority class | 0.771 | 0.000 | 0.000 | 0.000 | 0.500 | 0.229 |
| History rule | 0.903 | 0.814 | 0.747 | 0.779 | 0.950 | 0.843 |
| Logistic Regression | 0.891 | 0.707 | 0.892 | 0.789 | 0.956 | 0.858 |
| Random Forest | 0.888 | 0.703 | 0.887 | 0.784 | 0.949 | 0.809 |
| Random Forest without history | 0.713 | 0.443 | 0.992 | 0.612 | 0.928 | 0.769 |

The model with the highest F1 is Logistic Regression (0.789).

The Random Forest against each baseline:

- On F1, the Random Forest is better than the majority class (0.784 against 0.000).
- On AUC ROC, the Random Forest is better than the majority class (0.949 against 0.500).
- On AUC PR, the Random Forest is better than the majority class (0.809 against 0.229).
- On F1, the Random Forest is better than the history rule (0.784 against 0.779).
- On AUC ROC, the Random Forest is worse than the history rule (0.949 against 0.950).
- On AUC PR, the Random Forest is worse than the history rule (0.809 against 0.843).
- On F1, the Random Forest is worse than Logistic Regression (0.784 against 0.789).
- On AUC ROC, the Random Forest is worse than Logistic Regression (0.949 against 0.956).
- On AUC PR, the Random Forest is worse than Logistic Regression (0.809 against 0.858).

Without the history features, the F1 of the Random Forest is 0.612. With them it is 0.784.

## Limits

- Open requests are left out. They are 1.50% of the requests. This favors fast closures.
- The data covers 2025. The test window is the last quarter.
- A closed request is not always a fixed problem.
- N is the same for all problem types. Agencies have different service targets.
- The class weights make precision lower at the threshold 0.5. The precision of the Random Forest is 0.703. The precision of the history rule is 0.814.

Source of the precision values: results/tables/metrics_by_model.csv.
