# Rubric evidence

Each grading item of the course rubric maps to a phase and to evidence files. The column Evidence path lists the files as paths from the repository root.

Run PYTHONPATH=python .venv/bin/python -m nyc311.summary --check to test the paths. The command stops with an error if a listed path does not exist.

| Rubric item | Group (marks) | Phase | Evidence | Evidence path |
| --- | --- | --- | --- | --- |
| Dataset, problem, and attributes | Course step 1 | 1 | data/MANIFEST.json, section Dataset schema of the build plan, docs/results_summary.md | `data/MANIFEST.json`, `docs/BUILD_PLAN.md`, `docs/results_summary.md` |
| RDD created from the dataset | Scala and Spark (10) | 2 | ProfileJob.scala, profile_row_counts.csv | `scala/src/main/scala/nyc311/ProfileJob.scala`, `results/tables/profile_row_counts.csv` |
| At least 3 transformations | Scala and Spark (10) | 2, 3 | map, filter, flatMap, reduceByKey, and sortBy in ProfileJob.scala and RankingJob.scala | `scala/src/main/scala/nyc311/ProfileJob.scala`, `scala/src/main/scala/nyc311/RankingJob.scala` |
| At least 2 actions | Scala and Spark (10) | 2, 3 | count, first, take, collect, and reduce in ProfileJob.scala | `scala/src/main/scala/nyc311/ProfileJob.scala` |
| Key-value RDD operations | Scala and Spark (10) | 3 | reduceByKey, aggregateByKey, and join in RankingJob.scala, the rank tables, type_owner.csv | `scala/src/main/scala/nyc311/RankingJob.scala`, `results/tables/rank_*.csv`, `results/tables/type_owner.csv` |
| Number of partitions | Scala and Spark (10) | 5 | partitions.csv | `results/spark/partitions.csv` |
| RDD lineage | Scala and Spark (10) | 5 | lineage.txt | `results/spark/lineage.txt` |
| DAG | Scala and Spark (10) | 5 | dag_job.png | `results/spark/ui/dag_job.png` |
| Fault tolerance | Scala and Spark (10) | 5 | fault_tolerance.csv, spark_concepts.md | `results/spark/fault_tolerance.csv`, `docs/spark_concepts.md` |
| cache() and persist() | Scala and Spark (10) | 5 | cache_timing.csv, cache_storage.csv, storage.png | `results/spark/cache_timing.csv`, `results/spark/cache_storage.csv`, `results/spark/ui/storage.png` |
| Data and feature preparation | PySpark ML (3) | 4, 7 | features.parquet (not in Git), features.py, feature_summary.csv | `python/nyc311/features.py`, `scala/src/main/scala/nyc311/FeatureJob.scala`, `results/tables/feature_summary.csv` |
| Train and test split | PySpark ML (3) | 6 | data.py and the leakage tests | `python/nyc311/data.py`, `python/tests/test_data.py` |
| At least one ML model | PySpark ML (3) | 7 | models.py, metrics.json | `python/nyc311/models.py`, `results/metrics.json` |
| Accuracy, precision, recall, and F1 | PySpark ML (3) | 6, 7 | metrics.json, metrics_by_model.csv, confusion_matrix_rf.csv | `results/metrics.json`, `results/tables/metrics_by_model.csv`, `results/tables/confusion_matrix_rf.csv` |
| At least 3 charts | Visualization and results (2) | 8 | results/figures/ with 10 PNG files | `results/figures/fig*.png` |
| Results and discussion | Visualization and results (2) | 9 | results_summary.md | `docs/results_summary.md` |
