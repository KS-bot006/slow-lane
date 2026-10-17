# NYC 311 Resolution-Time

This project predicts whether a New York City (NYC) 311 request takes more than N days to close, using only facts known at filing. It also ranks problem types, agencies, boroughs, and ZIP codes by how slow they are.

## Data source

The data is the dataset 311 Service Requests from 2020 to Present, with the ID erm2-nwe9. The city publishes it on [NYC Open Data](https://data.cityofnewyork.us/resource/erm2-nwe9). The terms of use of NYC Open Data apply to the data.

The project uses the requests that were created in 2025 and 11 of the 48 columns. The file data/MANIFEST.json records the download.

## Tools

The build needs these tools. The script scripts/check_env.sh checks them.

| Tool | Version |
| --- | --- |
| Java (JDK) | 17 |
| Apache Spark | 3.5.9 (Hadoop 3, Scala 2.12) |
| Scala and sbt | 2.12.18 and 1.10.7 |
| Python | 3.11 |
| Git | any current version |

A free Socrata app token reduces the throttling of the city API. Set it in the variable SOCRATA_APP_TOKEN. The download also works without it.

## How to run

Run every command from the repository root. First create the Python environment and check the tools.

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements.txt
bash scripts/check_env.sh
```

Run all stages in order. The script stops at the first failure and ends with ALL STAGES OK.

```bash
bash scripts/run_all.sh
```

The option --skip-download skips the download. The option --rehearse runs all stages on the slice file data/raw/311_2025_slice.tsv. A rehearsal is short and never changes the committed results.

```bash
bash scripts/run_all.sh --rehearse
```

Each stage also runs alone. The Scala jobs run with run_scala.sh. The Python modules run from the repository root with PYTHONPATH=python.

```bash
bash scripts/run_scala.sh ProfileJob --input data/raw/311_2025.tsv
PYTHONPATH=python .venv/bin/python -m nyc311.train
PYTHONPATH=python .venv/bin/python -m nyc311.plots
```

## Repository layout

| Folder or file | Content |
| --- | --- |
| config/project.properties | Dates, thresholds, and model settings |
| scripts/ | Download, checks, and the run scripts |
| scala/ | The sbt project with the Spark jobs and their tests |
| python/nyc311/ | The PySpark modules: data, features, models, evaluation, plots, and summary |
| python/tests/ | The Python tests |
| data/MANIFEST.json | The record of the download |
| results/ | Tables, figures, Spark evidence, and metrics |
| docs/ | The build plan, the build log, the results summary, and the rubric evidence |

The raw data in data/raw/ and the features in data/processed/ stay out of Git.

## Results

The results are in the folder results/. The folder results/tables/ holds the CSV tables. The folder results/figures/ holds 10 figures. The folder results/spark/ holds the partitions, the lineage, the cache timing, and the screenshots of the Spark UI. The file results/metrics.json holds the model metrics.

The file docs/results_summary.md collects every number and names its source file. The file docs/rubric_evidence.md lists the evidence for each grading item. The file docs/spark_concepts.md explains the Spark concepts. The file docs/BUILD_LOG.md records each phase of the build.

## Limits

- Open requests are left out. This favors fast closures.
- The data covers one year. The test window is the last quarter.
- A closed request is not always a fixed problem.
- N is the same for all problem types, but agencies have different service targets.
- The class weights make precision lower at the threshold 0.5.
- The Logistic Regression scores a higher F1 than the Random Forest on the test window. The file docs/results_summary.md shows the numbers.
