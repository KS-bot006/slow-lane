# NYC 311 Resolution-Time Project: Build Plan

Oct 15, 2026 · @KS

## How to use this document

This document is the build specification for the NYC 311 Resolution-Time project. A coding agent builds the project from it. A human reviews the result at each exit check.

Terms used in this document:

- **Phase**: one unit of build work. Each phase ends with one commit.
- **Exit check**: a command that must pass before the next phase starts.
- **Agent**: the coding agent that writes the code.
- **Human**: the student who owns the project.

Rules for the agent:

- Read the whole document before you write code.
- Do the phases in the order given. Do not start a phase before the exit check of the previous phase passes.
- If an exit check fails, stop. Find the cause. Fix the cause. Run the check again.
- If this document and the course PDF disagree, follow the course PDF.
- Take every number in the report and the slides from a file in `results/`. Numbers can also come from data/MANIFEST.json. Name the file next to each number.

## Project summary

The project predicts whether a NYC 311 service request will take more than N days to close. The prediction uses only facts known when the request is filed. The project also ranks problem types, agencies, boroughs, and ZIP codes by how slow they are.

Two groups use the result. Residents get a realistic wait time when they file. City agencies and oversight bodies see where delays are structural and not random.

### Decisions fixed for this build

The agent does not change these decisions. If the agent cannot keep a decision, it stops and tells the human.

| Item | Decision |
| --- | --- |
| Dataset | 311 Service Requests from 2020 to Present (erm2-nwe9), NYC Open Data |
| Period | Requests created from 1 Jan 2025 to 31 Dec 2025 |
| Size | About 3.66 million requests created in 2025. About 1.5% have no closed date. (City API counts on 15 Oct 2026. Phase 1 records the exact counts.) |
| Target | slow = 1 if closed date minus created date is more than N days. Otherwise slow = 0. |
| Threshold N | 3 days by default. Phase 3 sets the final value with a fixed rule. |
| Removed rows | Rows with no closed date. Rows with a closed date before the created date. |
| History window | Created 1 Jan to 30 Jun 2025. Used only to compute history features. |
| Training window | Created 1 Jul to 30 Sep 2025. |
| Test window | Created 1 Oct to 31 Dec 2025. |
| Models | Logistic Regression (baseline) and Random Forest (main). |
| Metrics | Accuracy, precision, recall, F1, and AUC. Each is shown next to a majority-class baseline. |

## Dataset schema

The dataset is 311 Service Requests from 2020 to Present (ID erm2-nwe9) from NYC Open Data. It has 48 columns. Each row is one service request. The city updates it every day. This schema comes from the official column definitions, read on 15 Oct 2026: [columns.json](https://data.cityofnewyork.us/api/views/erm2-nwe9/columns.json).

Facts the agent must know:

- In December 2025 the city split the dataset. Requests from 2020 onward stay in erm2-nwe9. Requests from 2010 to 2019 moved to a new dataset (76ig-c548). See the [city notice](https://opendata.cityofnewyork.us/311-service-requests-from-2010-to-present-updates/).
- The city changed two display names. complaint\_type now shows as 'Problem'. descriptor now shows as 'Problem Detail'. The API field names did not change. Use the API names in code.
- The city added three columns: descriptor\_2 ('Additional Details'), council\_district, and police\_precinct.
- The city says its lists of expected values are not complete. Code must not fail when it sees a new value.
- The live 2025 data uses these borough values: BRONX, BROOKLYN, MANHATTAN, QUEENS, STATEN ISLAND, and Unspecified. A third-party page that lists boroughs as the numbers 1 to 5 does not match the live data.
- Treat every value as text on input. Cast each value with a safe cast. Count the casts that fail.

### Columns the project uses (11 of 48)

| API field | Type | Role | Notes |
| --- | --- | --- | --- |
| unique\_key | text | Row ID | One row per request. Must be unique in the download. |
| created\_date | date and time | Window, features | Sets the time window. Gives hour of day and day of week. |
| closed\_date | date and time | Target only | Never a feature. It exists only after resolution. |
| status | text | Filter only | Keep rows with status Closed. |
| agency | text | Feature | Code of the responding agency. |
| complaint\_type | text | Feature | Shown as 'Problem'. The main driver of slowness. |
| descriptor | text | Feature | Shown as 'Problem Detail'. Many values. Group rare values as OTHER. |
| location\_type | text | Feature | Type of place. Many values. Group rare values as OTHER. |
| borough | text | Feature | Five boroughs and Unspecified. |
| open\_data\_channel\_type | text | Feature | How the caller filed the request. |
| incident\_zip | text | History key, ranking | Not a direct feature. Values that are not 5 digits become UNKNOWN. |

### Columns the project does not use (37 of 48)

| Group | Columns | Reason |
| --- | --- | --- |
| Repeats another column | agency\_name, city | The project uses agency and borough instead. |
| Address detail | incident\_address, street\_name, cross\_street\_1, cross\_street\_2, intersection\_street\_1, intersection\_street\_2, address\_type, landmark, bbl | Too specific for this model. Some columns identify private addresses. The project does not download them. |
| Known only after resolution | resolution\_description, resolution\_action\_updated\_date | These columns would leak the answer. |
| May change after filing | due\_date | The project cannot prove that the value is fixed at filing. Future work. |
| Filled for few request types | descriptor\_2, facility\_type, park\_facility\_name, park\_borough, vehicle\_type, taxi\_company\_borough, taxi\_pick\_up\_location, bridge\_highway\_name, bridge\_highway\_direction, road\_ramp, bridge\_highway\_segment | Filled only for some request types. |
| Place detail | x\_coordinate\_state\_plane, y\_coordinate\_state\_plane, latitude, longitude, location, community\_board, council\_district, police\_precinct, and four :@computed\_region columns | ZIP code and borough carry the place information. The platform creates the computed region columns. |

## Setup

The human installs five tools before the build starts. The agent downloads the data in Phase 1. Run the whole build on the human's computer, a Linux x64 machine. Phases 1 and 2 need internet access to the city data API and to Maven Central.

### Tools to install

| Tool | Version | Used for | Check |
| --- | --- | --- | --- |
| Java (JDK) | 17 | Runs Spark and Scala | java -version prints 17 |
| Python | 3.11 | Runs PySpark and the plots | python3.11 --version prints 3.11 |
| Apache Spark | 3.5.9, default build (Hadoop 3, Scala 2.12) | Runs the Scala job and the Spark UI | spark-submit --version prints 3.5.9 and Scala 2.12 |
| sbt | 1.10.7 | Builds the Scala program | sbt --version prints 1.10.7 |
| Git | Any current version | Makes the commits | git --version |

The computer needs 8 GB of RAM at minimum and 10 GB of free disk space. 16 GB of RAM is better.

### Why these versions

- Spark 3.5.9 is the newest release of the 3.5 line (16 Jul 2026). Spark 4.2.0 is the newest release overall (14 Jul 2026), but Spark 4 turns on strict SQL mode by default. In strict mode, one bad value stops the whole job. Spark 3.5 returns null for a bad value, and the code counts those nulls.
- The Spark 3.5.9 documentation lists Java 8, 11, and 17. Do not use Java 21 or 25.
- The Scala program must use the same Scala version as Spark. The default Spark 3.5.9 build uses Scala 2.12, so the project uses Scala 2.12.18.
- PySpark must have the same version as Spark: 3.5.9.
- PySpark, numpy, pandas, matplotlib, and pytest were installed together at the pinned versions on Python 3.11, and a PySpark smoke test passed on 15 Oct 2026. Do not change these versions.

### Install commands

The commands below are for Debian or Ubuntu. On other systems, use the package manager of the system. Add the export lines to the file \~/.bashrc so that they stay set.

```bash
mkdir -p $HOME/Apps
sudo apt install openjdk-17-jdk git
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

curl -L https://archive.apache.org/dist/spark/spark-3.5.9/spark-3.5.9-bin-hadoop3.tgz | tar -xz -C $HOME/Apps
export SPARK_HOME=$HOME/Apps/spark-3.5.9-bin-hadoop3
export PATH=$SPARK_HOME/bin:$PATH

curl -L https://github.com/sbt/sbt/releases/download/v1.10.7/sbt-1.10.7.tgz | tar -xz -C $HOME/Apps
export PATH=$HOME/Apps/sbt/bin:$PATH

curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.11
```

If the Spark archive link fails, use the [Spark downloads page](https://spark.apache.org/downloads.html). Choose release 3.5.9 and the package 'Pre-built for Apache Hadoop 3.3 and later'. Do not choose the Scala 2.13 package.

A free Socrata app token reduces throttling by the city API. Set it as the variable SOCRATA\_APP\_TOKEN. The download also works without it.

## Tech stack

The project uses the tools below at these exact versions. The agent does not add other tools.

| Layer | Tool | Version | Role |
| --- | --- | --- | --- |
| Runtime | Java (JDK) | 17 | Runs Spark and sbt |
| Engine | Apache Spark | 3.5.9 | RDD API, Spark SQL for the Parquet output, Spark UI |
| Language | Scala | 2.12.18 | Data processing with RDDs |
| Build | sbt | 1.10.7 | Builds the Scala jar |
| Scala tests | ScalaTest | 3.2.18 | Unit tests for pure functions |
| Language | Python | 3.11 | Machine learning, plots, scripts |
| ML | PySpark | 3.5.9 | Feature pipeline, Logistic Regression, Random Forest |
| Python math | numpy | 1.26.4 | Array math in metrics and plots |
| Python tables | pandas | 2.2.3 | Small result tables only |
| Plots | matplotlib | 3.9.4 | All figures |
| Python tests | pytest | 8.3.5 | Unit tests |
| Data access | Python standard library | 3.11 | Download script (urllib, csv, json) |
| Version control | Git | Any current version | Commits |

Data formats: the raw data is a TSV file. The processed data is Parquet. Results are CSV and JSON files. Figures are PNG files.

The build downloads Spark and ScalaTest libraries from Maven Central. It downloads Python packages from PyPI.

The project does not use scikit-learn, seaborn, notebooks, Docker, Spark 4, or cloud services. Fewer tools mean fewer errors in a one-day build.

## Repository layout

The repository has one folder for each kind of work. The agent creates all folders in Phase 0. Folders marked as ignored stay out of Git.

```text
nyc311-resolution-time/
  README.md                 What the project does and how to run it
  AGENTS.md                 Rules for the agent (copy of the agent rules in this document)
  requirements.txt          Pinned Python packages
  .gitignore
  config/
    project.properties      Dates, thresholds, model settings (one source of truth)
  scripts/
    check_env.sh            Checks all tools and versions
    download_data.py        Downloads the 2025 requests from the city API
    verify_download.py      Checks the downloaded file
    make_slice.sh           Makes a small slice for quick test runs
    run_scala.sh            Runs one Scala job with spark-submit
    ste_check.py            Finds style problems in comments and documents
    run_all.sh              Runs every phase in order
  scala/
    build.sbt
    project/build.properties
    src/main/scala/nyc311/  Smoke, Constants, Args, Config, Record, Parser, Cleaning,
                            Windows, Stats, Csv, ProfileJob, ThresholdJob, RankingJob,
                            FeatureJob, ConceptsJob
    src/test/scala/nyc311/  Unit tests
  python/
    nyc311/                 config, session, data, features, baselines, models,
                            evaluate, train, plots, summary
    tests/                  Unit tests
  data/
    raw/                    Downloaded TSV files (ignored)
    processed/              Parquet features, predictions, run parameters (ignored)
    MANIFEST.json           Download record (committed)
  results/
    tables/                 CSV tables from Scala and PySpark
    figures/                PNG figures
    spark/                  Partitions, lineage, cache timing, UI screenshots
    metrics.json            Model metrics
  docs/
    BUILD_PLAN.md           This document, exported as Markdown
    BUILD_LOG.md            One entry for each phase
    results_summary.md      Numbers and findings for the report and the slides
    rubric_evidence.md      Where each grading item is shown
    spark_concepts.md       Partitions, lineage, DAG, fault tolerance, cache
```

Do not add other top-level folders. Put every setting in config/project.properties or on the command line. Do not put settings in code.

## Build phases

The build has 11 phases, numbered 0 to 10. Each phase has tasks, an exit check, and commits. Do the phases in order. Make the commits only after the exit check passes.

| Phase | Goal | Main output |
| --- | --- | --- |
| 0. Skeleton and environment | Create the repository. Pin the tools. Prove that Scala and PySpark run. | Passing environment check and smoke tests |
| 1. Data download | Get all 2025 requests from the city API. | data/raw/311\_2025.tsv and data/MANIFEST.json |
| 2. Scala: parse, clean, profile | Turn lines into clean records. Count what the file holds. | results/tables/profile\_\*.csv |
| 3. Scala: threshold and rankings | Set N. Rank problem types, agencies, boroughs, and ZIP codes by slowness. | results/tables/rank\_\*.csv |
| 4. Scala: history features | Build the feature table from the history window. | data/processed/features.parquet |
| 5. Scala: Spark concepts | Show partitions, lineage, cache, and recovery. | results/spark/ |
| 6. PySpark: data and baselines | Load the features. Guard against leakage. Score the baselines. | results/metrics\_baselines.json |
| 7. PySpark: models | Train Logistic Regression and Random Forest. Evaluate on the test window. | results/metrics.json and result tables |
| 8. Visualization | Draw the figures. | results/figures/\*.png |
| 9. Results summary | Collect all numbers and the rubric evidence. | docs/results\_summary.md |
| 10. Final check | Run everything from a clean clone. Tag the release. | Git tag v1.0.0 |

Time saver: start the Phase 1 download in the background as soon as Phase 0 passes. Write the Phase 2 code while the download runs.

### Phase 0: Skeleton and environment

**Goal.** Create the repository, pin the tools, and prove that Scala and PySpark run.

**Tasks.**

1. Create the folder nyc311-resolution-time. Run git init -b main. Create all folders from the repository layout.
2. Write .gitignore. Ignore `data/raw/`, `data/processed/`, `data/processed_slice/`, `results/tables_slice/`, `results/spark_slice/`, `results_slice/`, `logs/`, `.venv/`, `scala/target/`, `scala/project/target/`, `scala/project/project/`, `__pycache__/`, `.pytest_cache/`, `spark-warehouse/`, `metastore_db/`, `derby.log`, and `*.crc`.
3. Write requirements.txt with the five pinned Python packages from the tech stack. Write pytest.ini with the lines `[pytest]`, `pythonpath = python`, and `testpaths = python/tests`.
4. Create the Python environment with the commands below.
5. Write config/project.properties with the values below.
6. Write scala/project/build.properties with the line sbt.version=1.10.7.
7. Write scala/build.sbt as shown below.
8. Write the Scala job Smoke. It starts a SparkContext on local\[2\], sums the numbers 1 to 1000 with an RDD, and prints SMOKE OK 500500.
9. Write scripts/run\_scala.sh. It takes a job name and more arguments. It reads spark\_master and spark\_driver\_memory from the properties file. It runs sbt -batch package in the scala folder. Then it runs spark-submit with the class nyc311.JobName and the first jar in scala/target/scala-2.12/.
10. Write scripts/check\_env.sh. It checks Java 17, Python 3.11, Spark 3.5.9 with Scala 2.12, sbt 1.10.7, and Git. If SPARK\_HOME is set, it checks that the Spark version equals the PySpark version. It prints PASS or FAIL for each check. It exits with a non-zero code if one check fails.
11. Write python/tests/test\_smoke.py. It starts a local SparkSession and checks that spark.range(100).count() returns 100.
12. Write scripts/ste\_check.py and its test, as described in the section Writing standards.
13. Write README.md with the project name and one paragraph that states the purpose. Phase 10 completes it.
14. Write AGENTS.md as a copy of the section Rules for the coding agent. Save this document as docs/BUILD\_PLAN.md. Create docs/BUILD\_LOG.md with a title line.

Python environment commands:

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

The file config/project.properties:

```properties
year=2025
history_start=2025-01-01
history_end=2025-06-30
train_start=2025-07-01
train_end=2025-09-30
test_start=2025-10-01
test_end=2025-12-31
default_threshold_days=3
candidate_threshold_days=1,3,7
share_min=0.10
share_max=0.50
min_group_size=500
top_descriptors=100
top_location_types=30
smoothing_m=20
spark_master=local[*]
spark_driver_memory=4g
rf_num_trees=60
rf_max_depth=10
rf_subsampling_rate=0.5
rf_min_instances_per_node=20
lr_max_iter=50
seed=42
```

The file scala/build.sbt:

```scala
ThisBuild / scalaVersion := "2.12.18"
ThisBuild / version      := "1.0.0"
ThisBuild / organization := "nyc311"

lazy val root = (project in file("."))
  .settings(
    name := "nyc311-resolution-time",
    libraryDependencies ++= Seq(
      "org.apache.spark" %% "spark-core" % "3.5.9"  % Provided,
      "org.apache.spark" %% "spark-sql"  % "3.5.9"  % Provided,
      "org.scalatest"    %% "scalatest"  % "3.2.18" % Test
    ),
    scalacOptions ++= Seq("-deprecation", "-feature", "-unchecked", "-Xlint")
  )
```

The first sbt run downloads libraries from Maven Central. It can take several minutes.

**Exit check.**

- bash scripts/check\_env.sh prints PASS for each tool and ends with ALL PASS.
- bash scripts/run\_scala.sh Smoke prints SMOKE OK 500500.
- .venv/bin/python -m pytest -q python/tests passes.
- .venv/bin/python scripts/ste\_check.py ends with STE CHECK OK.

**Commits.**

- chore: add project skeleton, ignore rules, and pinned requirements
- build(scala): add sbt project and smoke job
- build: add environment check and Spark run script
- test: add Python smoke test and style check script
- docs: add build plan, agent rules, and build log

### Phase 1: Data download

**Goal.** Get all 2025 requests as one TSV file with 11 columns. Record the download in a manifest.

**Tasks.**

1. Write scripts/download\_data.py. Use only the Python standard library. It must follow the rules below.
2. Write scripts/verify\_download.py. It must run the checks listed in the exit check.
3. Write scripts/make\_slice.sh. It keeps the header and every 40th line of data/raw/311\_2025.tsv. It writes the result to data/raw/311\_2025\_slice.tsv. The slice has about 90,000 rows. Later phases use it for quick test runs.
4. Run the three scripts in the order shown below.

Rules for download\_data.py:

- Read the year from config/project.properties.
- Use the endpoint https://data.cityofnewyork.us/resource/erm2-nwe9.csv.
- Request these 11 columns with $select, in this order: unique\_key, created\_date, closed\_date, status, agency, complaint\_type, descriptor, location\_type, borough, open\_data\_channel\_type, incident\_zip.
- Download one month at a time. Filter with $where on created\_date: greater than or equal to the first day of the month, and less than the first day of the next month. Use the form 2025-03-01T00:00:00.
- Order by created\_date, then unique\_key. Use $limit=50000 and move $offset by 50000 for each page.
- Before each month, ask the .json endpoint for the count of that month with $select=count(\*) and the same filter.
- Write each month to data/raw/parts/YYYY-MM.tsv. Skip a month if its part file exists and its row count equals the API count.
- Retry on HTTP 429, 500, 502, 503, and 504, and on network errors. Make 6 tries. Wait 2, 4, 8, 16, and 32 seconds. Wait 0.5 seconds between requests.
- Send the header User-Agent: nyc311-student-project. If the variable SOCRATA\_APP\_TOKEN is set, send it as the header X-App-Token.
- Replace each tab, carriage return, and newline in a value with one space. Strip spaces from both ends of a value.
- Stop with an error if the rows of a month differ from the API count by more than 0.1%.
- Join the parts into data/raw/311\_2025.tsv. Write to a temporary file first. Then rename it.
- Write data/MANIFEST.json with these keys: dataset\_id, endpoint, year, downloaded\_at\_utc, columns, rows\_per\_month, total\_rows, sha256.

The download makes about 85 requests. Run the scripts in this order:

```bash
.venv/bin/python scripts/download_data.py
.venv/bin/python scripts/verify_download.py
bash scripts/make_slice.sh
```

**Exit check.** verify\_download.py ends with VERIFY OK. It checks that:

- The header equals the 11 column names, in order.
- Every row has 11 fields.
- No unique\_key appears twice.
- Every created\_date matches the pattern YYYY-MM-DDTHH:MM:SS.mmm and lies in 2025.
- The row count of each month equals the value in data/MANIFEST.json.
- The SHA-256 of the file equals the value in data/MANIFEST.json.

The script also prints these values: the total rows, the rows per month, and the share of rows without a closed\_date. It prints the count of each status value and of each borough value. A new borough value gives a WARN line. It does not stop the build.

**Commits.**

- feat(data): add city API download script with retry and manifest
- feat(data): add download verification and slice script
- docs(data): record the download manifest

### Phase 2: Scala parsing, cleaning, and profile

**Goal.** Turn each line into a clean record. Count what the file holds. Show the RDD basics: creation, transformations, actions, and partitions.

**Tasks.**

1. Write the pure Scala objects listed below. They must not import Spark. This keeps the unit tests fast and free of Java module errors.
2. Write ScalaTest unit tests for each object.
3. Write the job ProfileJob. It follows the steps listed below.
4. Run ProfileJob on the slice. Then run it on the full file.

Pure objects:

- **Constants.** The 11 column names in download order. The header line. The field count of 11. The allowed borough values. The reject reasons.
- **Args.** Turns the arguments --key value into a Map. It stops with an error message if a key has no value.
- **Config.** Reads config/project.properties. It gives typed values: the window dates, the candidate thresholds, and the sizes. Jobs run from the repository root.
- **Record.** A case class Request with these fields: uniqueKey, created (LocalDateTime), closed (Option of LocalDateTime), status, agency, complaintType, descriptor, locationType, borough, channel, zip.
- **Parser.** The function parseLine(line) returns Either a reject reason or a Request.
- **Cleaning.** The function classify(request) returns Either a drop reason or a clean record with the duration in days.
- **Windows.** The function windowOf(date) returns history, train, or test. It returns None for other dates. Both end dates belong to the window.
- **Csv.** The function escape quotes a value that has a comma, a quote, or a newline. The function write(path, header, rows) writes UTF-8 with a header and the line break \\n.

Parser rules:

- Split the line with split("\\t", -1). If the line does not have 11 fields, reject it with bad\_field\_count.
- If unique\_key is empty, reject with missing\_key.
- Parse created\_date with LocalDateTime.parse. If it fails, reject with bad\_created\_date.
- If closed\_date is empty, store None. If it fails to parse, reject with bad\_closed\_date.
- If any other text field is empty, store UNKNOWN.

Cleaning rules. Apply them in this order. The first rule that fails gives the drop reason:

1. closed is None: drop with open\_no\_closed\_date.
2. status is not Closed (ignore case): drop with status\_not\_closed.
3. created is not in the year of the config: drop with outside\_year.
4. closed is before created: drop with closed\_before\_created.

The duration in days is the seconds between created and closed, divided by 86400.0. A duration of zero is valid. Then normalize the record:

- Convert agency, complaint\_type, descriptor, location\_type, and channel to upper case.
- Borough: trim and convert to upper case. Keep it if it is BRONX, BROOKLYN, MANHATTAN, QUEENS, or STATEN ISLAND. Otherwise use UNSPECIFIED.
- ZIP: if the value matches ^\\d{5}(-\\d{4})?$, keep the first 5 digits. Otherwise use UNKNOWN.
- Add the hour of day (0 to 23) and the day of week (1 for Monday to 7 for Sunday) of the created time.

Unit tests must cover at least these cases:

- A valid line.
- A line with 10 fields.
- A bad created date.
- An empty closed date.
- A negative duration.
- A status other than Closed.
- The ZIP forms 11201, 11201-1234, and N/A.
- The borough forms Brooklyn and 0.
- The window boundaries, on both end dates.
- A CSV value with a comma, a quote, and a newline.

Steps of ProfileJob. Arguments: --input, --out (default results/tables), --min-partitions (default 8):

1. Create the RDD with sc.textFile from an absolute file URI. Record the number of partitions.
2. Read the first line with first(). If it is not the expected header, print an error and exit with code 2.
3. Remove the header with filter. Convert each line with map(Parser.parseLine). Persist the result with MEMORY\_AND\_DISK.
4. Count the reject reasons with flatMap, map to (reason, 1), and reduceByKey.
5. Apply Cleaning.classify with map. Count the drop reasons the same way. Keep the clean records with flatMap and persist them.
6. Check that lines read minus 1 equals the rejects plus the drops plus the clean rows. Print reconcile: ok, or stop with an error.
7. Count the clean rows by month with map, reduceByKey, and sortByKey. Count all rows by status before cleaning.
8. Compute the quantiles 0.5, 0.75, 0.9, 0.95, and 0.99 of the duration. Use sortBy and zipWithIndex. Also get the maximum with reduce, and print 5 sample records with take.
9. Build a histogram of the duration. The bucket is 0 when the duration is under 1 hour. Otherwise the bucket is floor(log2(hours)) + 1.
10. Count the clean rows by window.
11. Before every collect, check that the result has at most 10,000 rows. Write the results with Csv.write. Print PROFILE OK.

Output files in the folder --out: profile\_row\_counts.csv, profile\_status\_counts.csv, profile\_monthly\_counts.csv, profile\_duration\_quantiles.csv, and profile\_duration\_hist.csv.

Commands:

```bash
bash scripts/run_scala.sh ProfileJob --input data/raw/311_2025_slice.tsv --out results/tables_slice
bash scripts/run_scala.sh ProfileJob --input data/raw/311_2025.tsv --out results/tables
```

**Exit check.**

- cd scala && sbt -batch test passes.
- Both ProfileJob runs end with reconcile: ok and PROFILE OK.
- The monthly counts show 12 months, 2025-01 to 2025-12.
- The quantiles rise from the first to the last row. The histogram counts add up to the clean rows.
- The share of open\_no\_closed\_date drops is close to the share that verify\_download.py printed.

**Commits.**

- feat(scala): add constants, args, config, and CSV writer
- feat(scala): add line parser and cleaning rules
- test(scala): add unit tests for parser, cleaning, windows, and CSV
- feat(scala): add profile job with RDD operations
- docs(results): add profile tables

### Phase 3: Scala threshold and rankings

**Goal.** Set the threshold N from the history window. Rank groups by how slow they are.

**Tasks.**

1. Write the pure object Stats. It holds the case class Agg(n, sumDays, sumLogDays, slowCount). It also holds the functions zero, add, merge, wilson(k, n), and smooth(sum, n, m, prior). Write the pure object Keys. It builds and parses the group keys. Write the object Pipeline. Its function cleanRows(sc, path, minPartitions) does steps 1 to 5 of ProfileJob and returns the clean records. The three later jobs use it. Pipeline and the jobs are the only objects that import Spark.
2. Write unit tests. Use these values: wilson(5, 10) is (0.2366, 0.7634). wilson(0, 10) is (0.0, 0.2775). Allow an error of 0.001. Merging the Agg of two halves must equal the Agg of the whole. A key must survive the round trip through build and parse.
3. Write ThresholdJob and RankingJob. Run both on the slice. Then run both on the full file.

The Wilson interval with z = 1.96:

```latex
\frac{\hat p + \frac{z^2}{2n} \pm z\sqrt{\frac{\hat p(1-\hat p)}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}
```

The job ThresholdJob uses only the clean rows of the history window. It never reads a test label. Arguments: --input, --out (default results/tables), --processed (default data/processed).

- For each candidate N in the config (1, 3, and 7 days), count the rows with a duration above N days. Compute the slow share.
- Start with default\_threshold\_days (3). If its share is below share\_min (0.10), select 1. If its share is above share\_max (0.50), select 7.
- If the share of the selected N is outside share\_min and share\_max, print an error and exit with code 2. Stop and ask the human.
- Write threshold\_selection.csv with the columns candidate\_days, history\_rows, slow\_rows, slow\_share, and selected.
- Write run\_params.properties in the folder --processed with slow\_threshold\_days, history\_rows, and history\_slow\_share.

The job RankingJob uses all clean rows of the year. This analysis describes the data. It does not train a model. Arguments: --input, --out, --processed. It reads N from run\_params.properties.

1. Read the clean rows. Use flatMap to emit one key-value pair for each grain of each row. The grains are agency, complaint\_type, borough, zip, agency and complaint\_type, complaint\_type and borough, hour, day of week, and month. The value is an Agg for that one row.
2. Combine the pairs with aggregateByKey. Do not use groupByKey. Persist the result.
3. For each grain, compute n, mean days, slow share, and the Wilson interval. For the ranking tables, keep groups with n of at least min\_group\_size (500). Sort by slow share, highest first. Keep all groups in the hour, day, and month tables.
4. Build the table type\_owner.csv with a join. Count the requests for each pair of complaint type and agency. Reduce to the agency with the most requests for each type. Join the result with the Agg of the type. The columns are complaint\_type, dominant\_agency, dominant\_share, n, slow\_share, wilson\_low, and wilson\_high.
5. For each grain, check that the sum of n over all groups equals the number of clean rows. Print reconcile: ok for each grain, or stop with an error.
6. Print RANKING OK.

Output files: rank\_agency.csv, rank\_complaint\_type.csv, rank\_borough.csv, rank\_zip.csv, rank\_agency\_type.csv, rank\_type\_borough.csv, pattern\_hour.csv, pattern\_dow.csv, pattern\_month.csv, and type\_owner.csv.

Commands for the full run. For the slice run, use the slice input, --out results/tables\_slice, and --processed data/processed\_slice:

```bash
bash scripts/run_scala.sh ThresholdJob --input data/raw/311_2025.tsv
bash scripts/run_scala.sh RankingJob --input data/raw/311_2025.tsv
```

**Exit check.**

- sbt -batch test passes.
- ThresholdJob ends with THRESHOLD OK. The file run\_params.properties has a value for slow\_threshold\_days.
- RankingJob ends with RANKING OK and one reconcile: ok line for each grain.
- In every row of the ranking tables, wilson\_low is at most slow\_share, and slow\_share is at most wilson\_high.
- Read rank\_complaint\_type.csv by eye. The top rows must have n of at least 500.

**Commits.**

- feat(scala): add statistics helpers, group keys, and shared pipeline
- test(scala): add tests for statistics helpers and group keys
- feat(scala): add threshold job with fixed selection rule
- feat(scala): add ranking job with multi-level aggregation and join
- docs(results): add threshold and ranking tables

### Phase 4: Scala history features

**Goal.** Build the feature table for the model. Every history statistic comes from the history window only. The model never sees a label that was used to build one of its features.

**Tasks.**

1. Write the pure object Features. It builds the feature row of one clean record. It also builds the three history keys and looks them up.
2. Write unit tests. The label is 1.0 only when the duration is strictly above N days. A duration of exactly N days gives 0.0. A key that is not in the history gives the prior value. The weekend flag is 1 for day 6 and day 7. A rare descriptor becomes OTHER.
3. Write FeatureJob. Run it on the slice. Then run it on the full file.

The three history keys:

- **h1:** agency, complaint type, and descriptor.
- **h2:** complaint type and borough.
- **h3:** ZIP code.

For each key, the job computes three history features. Two of them use a smoothed value. A smoothed value pulls a small group toward the history-wide average. This formula defines it:

```latex
s = \frac{k + m \, p_0}{n + m}
```

Terms of the formula:

- k is the slow count of the key in the history window. For the mean of ln(1 + days), k is the sum of ln(1 + days).
- n is the number of history rows of the key.
- m is smoothing\_m (20).
- p0 is the history-wide average of the same quantity.

The three features of each key:

- **slow\_rate:** the smoothed share of requests with a duration above N days.
- **mean\_log\_days:** the smoothed mean of ln(1 + days).
- **log\_n:** ln(1 + n), where n is the number of history rows of the key.

Steps of FeatureJob. Arguments: --input, --out (default results/tables), --processed (default data/processed). The job reads N from run\_params.properties:

1. Read the clean rows with Pipeline.cleanRows.
2. Select the history rows with filter. Compute the history-wide statistics with aggregate.
3. For each of the three keys, build the history map with map, aggregateByKey, and collectAsMap. Stop with an error if a map has more than 200,000 entries.
4. Find the most frequent descriptors (top\_descriptors, 100) and location types (top\_location\_types, 30) in the history rows. Use map, reduceByKey, and top. Rare values become OTHER.
5. Send the maps and the two sets to the workers with sc.broadcast. This avoids a shuffle join.
6. Select the train and test rows. Build the feature row of each with map.
7. For each key, count the train and test rows that have a key in the history. Use map and reduceByKey.
8. Build a DataFrame with an explicit schema. Write it to features.parquet in the folder --processed with mode overwrite. Use coalesce(8) before the write.
9. Run these checks. Stop with an error if one fails. No column has a null value. The column window holds only train and test. The latest train created\_date is before the earliest test created\_date. The number of rows equals the number of clean rows in the train and test windows.
10. Write feature\_summary.csv with the columns window, rows, slow\_rows, and slow\_share. Write bucket\_lists.csv with the columns kind, value, and history\_count. Write history\_coverage.csv with the columns window, key, rows, rows\_with\_history, and share. Print FEATURES OK.

Store dates as ISO strings in the feature table. This avoids time zone errors. The columns of features.parquet:

| Column | Type | Use |
| --- | --- | --- |
| unique\_key | string | Row ID |
| window | string | train or test |
| created\_date | string | ISO time of filing |
| label | double | 1.0 if the request is slow, else 0.0 |
| duration\_days | double | Analysis only. Never a feature. |
| agency, complaint\_type, descriptor\_g, location\_type\_g, borough, channel | string | Categorical features |
| zip | string | Analysis only. Not a feature. |
| hour, dow, is\_weekend | int | Time features |
| h1\_slow\_rate, h1\_mean\_log\_days, h1\_log\_n, h2\_slow\_rate, h2\_mean\_log\_days, h2\_log\_n, h3\_slow\_rate, h3\_mean\_log\_days, h3\_log\_n | double | History features |

Commands for the full run. For the slice run, use the slice input and --processed data/processed\_slice:

```bash
bash scripts/run_scala.sh FeatureJob --input data/raw/311_2025.tsv
```

**Exit check.**

- sbt -batch test passes.
- FeatureJob ends with FEATURES OK on the slice and on the full file.
- The folder data/processed/features.parquet has the file \_SUCCESS and part files.
- feature\_summary.csv shows rows in both windows. Every slow\_share lies between 0 and 1.
- Read history\_coverage.csv. Write the coverage values in docs/BUILD\_LOG.md.

**Commits.**

- feat(scala): add history statistics and feature rows
- feat(scala): add feature job with Parquet output
- docs(results): add feature summary and history coverage tables

### Phase 5: Scala Spark concepts

**Goal.** Produce evidence for partitions, lineage, DAG, fault tolerance, and cache. These topics belong to the 10 marks for Scala and Spark in the course rubric.

**Tasks.**

1. Write ConceptsJob. Arguments: --input, --out (default results/spark), --hold-seconds (default 0).
2. Run it on the slice to test it. Run it on the full file.
3. Write docs/spark\_concepts.md. Explain each concept in 3 to 5 plain sentences. Name the file in results/spark/ that shows it. Copy numbers only from those files.

Steps of ConceptsJob:

1. **Partitions.** Create the base RDD with textFile and minPartitions 4. Record its number of partitions. The number depends on the file size. Make a second RDD with repartition(16) and a third with coalesce(2). Record their partitions too. For each RDD, count the rows in each partition with mapPartitionsWithIndex. Write partitions.csv with the columns rdd\_name, partition\_index, and rows.
2. **Lineage.** Build the pipeline with Pipeline.cleanRows. Then build byType with map and reduceByKey on (complaint\_type, days). Write the toDebugString of the clean RDD and of byType to lineage.txt. Add the type of each dependency (narrow or shuffle). Run byType.count() once. This action creates a Spark job with a shuffle stage for the DAG.
3. **Cache.** First, run one full count of the lines to warm the file cache of the operating system. Then run clean.count() 3 times without cache and time each run. Call persist(MEMORY\_AND\_DISK) on clean. Run clean.count() 3 times and time each run. Write cache\_timing.csv with the columns variant, run, and seconds. Write the storage information of sc.getRDDStorageInfo to cache\_storage.csv.
4. **Hold.** If --hold-seconds is above 0, print the address of the Spark UI. Then wait for that number of seconds. The human takes the screenshots in this time.
5. **Fault tolerance.** Save the count and the sum of the days of clean. Call unpersist(blocking = true). This drops all cached partitions, as a lost executor would. Compute the count and the sum again. Spark rebuilds the data from the lineage. Write fault\_tolerance.csv with the columns check, before, after, equal, and recompute\_seconds. Print a line that states the result. The check is a simulation, because a local run has no executor that can fail. Say so in docs/spark\_concepts.md.
6. Write spark\_context.csv with the master, the default parallelism, and the number of cores. Print CONCEPTS OK.

Commands. The full run with a hold lets the human take the screenshots:

```bash
bash scripts/run_scala.sh ConceptsJob --input data/raw/311_2025_slice.tsv --out results/spark_slice
bash scripts/run_scala.sh ConceptsJob --input data/raw/311_2025.tsv --hold-seconds 900
```

**Human task.** The job waits when --hold-seconds is above 0. Use this time to take three screenshots:

- Open the address that the job prints, usually http://localhost:4040.
- Save dag\_job.png in results/spark/ui/. Open the Jobs tab, then the job with the shuffle. Capture its DAG visualization.
- Save stages.png in the same folder. Capture the Stages tab.
- Save storage.png in the same folder. Capture the Storage tab with the cached RDD.

If the human is not present, the agent runs the job with --hold-seconds 0. It lists the three screenshots as open tasks in docs/BUILD\_LOG.md.

**Exit check.**

- ConceptsJob ends with CONCEPTS OK on the slice and on the full file.
- partitions.csv has one row for each partition of the three RDDs. The number of rows equals the sum of the three partition counts that the job prints.
- lineage.txt contains the words ShuffledRDD and ShuffleDependency.
- cache\_timing.csv has 6 rows. cache\_storage.csv shows the cached RDD.
- fault\_tolerance.csv shows equal = true.

**Commits.**

- feat(scala): add concepts job for partitions and lineage
- feat(scala): add cache timing and fault tolerance demo
- docs(results): add Spark concepts outputs and explanation

### Phase 6: PySpark data and baselines

**Goal.** Load the feature table. Split it by time. Guard against leakage. Score two baselines. Write the metric code that Phase 7 also uses.

**Tasks.** Write these modules in python/nyc311/:

1. **config.** Reads config/project.properties and run\_params.properties into a dict. It stops with a clear error if a key is missing.
2. **session.** The function get\_spark(app\_name) builds a local SparkSession. It sets the master and the driver memory from the config, spark.sql.shuffle.partitions to 16, and spark.sql.ansi.enabled to false.
3. **data.** Holds the column lists below. It loads features.parquet, splits it into train and test by the column window, and runs the leakage guards.
4. **evaluate.** The function confusion\_counts(df, label\_col, pred\_col) returns tp, fp, tn, and fn. The function metrics\_from\_counts(counts) returns accuracy, precision, recall, and F1 of the slow class. A zero denominator gives 0.0. The function auc\_scores(df, label\_col, score\_col) returns the area under the ROC curve and under the precision-recall curve. It uses BinaryClassificationEvaluator with the score as rawPredictionCol.
5. **baselines.** The majority-class baseline predicts the label that is most frequent in the train window. Its score is a constant. The history-rule baseline predicts slow when h1\_slow\_rate is at least 0.5. Its score is h1\_slow\_rate.
6. Write pytest tests. Use small synthetic DataFrames. Test metrics\_from\_counts with known numbers and with a zero denominator. Test that each leakage guard raises an error when it should. Test the history rule on a few rows.
7. Write the command python -m nyc311.baselines with the arguments --processed (default data/processed) and --out (default results/metrics\_baselines.json).

Column lists in data.py:

- **CATEGORICAL:** agency, complaint\_type, descriptor\_g, location\_type\_g, borough, channel, hour, dow.
- **NUMERIC\_TIME:** is\_weekend.
- **NUMERIC\_HISTORY:** the nine columns h1\_slow\_rate, h1\_mean\_log\_days, h1\_log\_n, h2\_slow\_rate, h2\_mean\_log\_days, h2\_log\_n, h3\_slow\_rate, h3\_mean\_log\_days, and h3\_log\_n.
- **NOT\_FEATURES:** unique\_key, window, created\_date, label, duration\_days, and zip.

The leakage guards. Each one stops the run with an error message if it fails:

- The column window holds only the values train and test.
- The latest created\_date in train is before the earliest created\_date in test.
- Each unique\_key appears once.
- No feature column is in NOT\_FEATURES. No feature column name contains closed, resolution, status, or due.
- No feature column has a null or NaN value. Check this in one pass over the data.

Commands:

```bash
PYTHONPATH=python .venv/bin/python -m nyc311.baselines --processed data/processed_slice --out results/metrics_baselines_slice.json
PYTHONPATH=python .venv/bin/python -m nyc311.baselines
```

Run every Python module from the repository root. Put PYTHONPATH=python in front of the command. The file pytest.ini sets the path for pytest.

**Exit check.**

- .venv/bin/python -m pytest -q python/tests passes.
- Both baseline runs end with BASELINES OK.
- The JSON file has the entries majority and history\_rule. Each entry has accuracy, precision, recall, f1, auc\_roc, auc\_pr, tp, fp, tn, fn, and test\_rows.
- The accuracy of the majority baseline equals 1 minus the test slow share. Its recall is 0.

**Commits.**

- feat(python): add config, session, and data loading with leakage guards
- feat(python): add metric functions and baselines
- test(python): add tests for metrics and leakage guards
- docs(results): add baseline metrics

### Phase 7: PySpark models and evaluation

**Goal.** Train Logistic Regression and Random Forest on the train window. Evaluate them on the test window. Write all result tables.

**Tasks.**

1. Write python/nyc311/features.py. The function build\_pipeline(classifier, use\_history) returns a Spark ML Pipeline. The function add\_weights(train) adds a column weight. The weight of class c is n divided by (2 times n\_c). Here n is the number of train rows and n\_c is the number of train rows of class c. The pipeline has these stages:
   - StringIndexer for the CATEGORICAL columns, with handleInvalid keep.
   - OneHotEncoder for the indexed columns, with handleInvalid keep.
   - VectorAssembler, with handleInvalid error. Its inputs are the one-hot columns and NUMERIC\_TIME. If use\_history is true, the inputs also include NUMERIC\_HISTORY.
   - The classifier.
2. Write python/nyc311/models.py. The function make\_logistic\_regression uses weightCol weight, maxIter from lr\_max\_iter, and standardization true. The function make\_random\_forest uses weightCol weight and featureSubsetStrategy sqrt. It reads numTrees, maxDepth, subsamplingRate, minInstancesPerNode, and the seed from the config.
3. Add these lines to config/project.properties: fast\_train\_fraction=0.2, fast\_rf\_num\_trees=20, and fast\_rf\_max\_depth=6.
4. Write python/nyc311/train.py. It follows the steps below.
5. Write pytest tests. Test add\_weights on a small DataFrame. Test that the pipeline with use\_history false has no history column in its assembler. Test the function that groups feature importance.
6. Rehearse with --fast on the slice. Then run the full training.

Steps of train.py. Arguments: --processed (default data/processed), --results (default results), and --fast:

1. Load the features. Run the leakage guards. Split into train and test. In fast mode, sample the fraction fast\_train\_fraction of train with the seed.
2. Add the weights. Cache the train data.
3. Fit three pipelines: Logistic Regression, Random Forest, and Random Forest without the history features. Record the training time of each.
4. Predict on the test data. For each model, take the slow probability with vector\_to\_array(probability)\[1\].
5. Compute accuracy, precision, recall, F1, the area under the ROC curve, and the area under the precision-recall curve. The decision threshold is 0.5. Add the two baselines from Phase 6.
6. Build these tables for the Random Forest: the confusion matrix, the decile table, the metrics of the 10 agencies with the most test rows, and the feature importance by group.
7. Build the precision-recall table for the Random Forest and for Logistic Regression. Use the thresholds 0.00, 0.01, and so on up to 1.00.
8. Write the files listed below. Print TRAIN OK.

The decile table sorts the test requests by the Random Forest slow probability. Use approxQuantile for the nine cut points and Bucketizer for the deciles. The columns are decile (1 is the riskiest 10%), rows, slow\_rows, share\_of\_all\_slow, cumulative\_share, and lift. The lift is the slow share of the decile divided by the slow share of all test rows.

The feature importance by group. Read the length of each one-hot vector from the metadata of its column. Slice the Random Forest importance vector by these lengths. Sum the slices for each categorical column. Keep is\_weekend as one group. Sum the nine history columns into three groups, h1, h2, and h3. The importances must sum to 1 within 0.000001.

Output files:

- results/metrics.json with the entries majority, history\_rule, logistic\_regression, random\_forest, and random\_forest\_no\_history. Each entry has the keys of the baselines plus train\_seconds for the three models. The file also has the keys train\_rows, test\_rows, slow\_threshold\_days, test\_slow\_share, and fast\_mode.
- results/tables/metrics\_by\_model.csv, confusion\_matrix\_rf.csv, pr\_curve.csv, decile\_capture\_rf.csv, metrics\_by\_agency\_rf.csv, feature\_importance\_groups\_rf.csv, and train\_config.csv.
- data/processed/predictions\_test.parquet with unique\_key, label, p\_lr, p\_rf, p\_rf\_nohist, agency, complaint\_type, and borough. Git ignores this file.

Commands. The first one rehearses on the slice:

```bash
PYTHONPATH=python .venv/bin/python -m nyc311.train --processed data/processed_slice --results results_slice --fast
PYTHONPATH=python .venv/bin/python -m nyc311.train
```

**Exit check.**

- pytest passes.
- Both runs end with TRAIN OK.
- For every model, tp + fp + tn + fn equals test\_rows.
- The Random Forest importances sum to 1.
- Read metrics\_by\_model.csv. If the Random Forest does not beat a baseline on F1, do not tune it on the test data. Write the result in docs/BUILD\_LOG.md and report it in the results summary.

**Commits.**

- feat(python): add feature pipeline and class weights
- feat(python): add model builders and training script
- feat(python): add evaluation tables and feature importance by group
- test(python): add tests for pipeline stages and importance grouping
- docs(results): add model metrics and result tables

### Phase 8: Visualization

**Goal.** Draw the figures for the slides and the report. The course asks for at least 3 charts. The build makes 10. The slides need only the best 3 to 6.

**Tasks.**

1. Write python/nyc311/plots.py with one function for each figure. Use matplotlib with the Agg backend. Read the CSV files with pandas. Do not start Spark in this module.
2. Write the command python -m nyc311.plots. It reads results/tables and results/metrics.json. It writes PNG files to results/figures/.
3. Build every title from the numbers in the table. Do not type a number into a title.
4. Write pytest tests. Call each plot function with a small synthetic table. Check that the PNG file exists and is larger than 5 KB. Test the title builders.
5. Open every PNG file and check it by eye. Fix overlapping text, cut-off labels, and unreadable sizes.

| File | Chart | Source | What it shows |
| --- | --- | --- | --- |
| fig01\_duration\_histogram.png | Bars with a line at N days | profile\_duration\_hist.csv, run\_params.properties | How long requests take to close |
| fig02\_slowest\_types.png | Horizontal bars with Wilson intervals | rank\_complaint\_type.csv | The 15 problem types with the highest slow share |
| fig03\_agency\_slowness.png | Sorted bars with request counts | rank\_agency.csv | The slow share of each agency |
| fig04\_type\_borough\_heatmap.png | Heatmap | rank\_type\_borough.csv | Slow share of the 12 most frequent types in each borough |
| fig05\_time\_patterns.png | Three panels | pattern\_hour.csv, pattern\_dow.csv, pattern\_month.csv | How the slow share changes with the hour, the weekday, and the month of filing |
| fig06\_model\_comparison.png | Grouped bars | metrics\_by\_model.csv | Recall, precision, and F1 of the slow class for the five models |
| fig07\_pr\_curves.png | Lines and points | pr\_curve.csv, metrics.json | Precision against recall for both models, with the baselines marked |
| fig08\_decile\_capture.png | Bars and a cumulative line | decile\_capture\_rf.csv | The share of slow requests in each risk decile |
| fig09\_feature\_importance.png | Horizontal bars | feature\_importance\_groups\_rf.csv | Which feature groups the Random Forest uses most |
| fig10\_confusion\_matrix.png | Annotated 2 by 2 grid | confusion\_matrix\_rf.csv | Counts and shares of right and wrong predictions |

The slow share of all requests is the sum of slow requests divided by the sum of requests in pattern\_month.csv.

Command:

```bash
PYTHONPATH=python .venv/bin/python -m nyc311.plots
```

**Exit check.**

- The command ends with PLOTS OK and writes 10 PNG files.
- Every figure follows the figure rules in the section Coding standards.
- The agent has opened every figure. The entry in docs/BUILD\_LOG.md lists what it fixed.
- pytest passes.

**Commits.**

- feat(python): add plot helpers and descriptive figures
- feat(python): add model evaluation figures
- test(python): add plot tests
- docs(results): add figures

### Phase 9: Results summary and rubric evidence

**Goal.** Collect every number and every proof in two files. The human writes the slides and the report from them.

**Tasks.**

1. Write python/nyc311/summary.py. It reads data/MANIFEST.json, results/tables/, results/metrics.json, and results/spark/. It writes docs/results\_summary.md.
2. Write docs/rubric\_evidence.md. Copy the table from the section Rubric map. Add a column with the path of the evidence file. Add the command python -m nyc311.summary --check. It stops with an error if a listed path does not exist.
3. Run the summary. Read the whole file. Compare three numbers with their source files. Write the result in docs/BUILD\_LOG.md.

Sections of results\_summary.md. Code fills every number from a file:

- **Dataset.** Source, dataset ID, download time, total rows, columns used, rows in each window, rows dropped for each reason, and the share of open requests.
- **Target.** N, the table that selected it, and the slow share in each window.
- **Spark processing.** The partition counts, the dependency types of the lineage, the mean time of the cached and uncached runs, and the fault tolerance result.
- **Slowness findings.** The five slowest problem types, agencies, boroughs, and ZIP codes, each with its slow share and interval. The agency that owns the slowest types.
- **Model results.** The metrics of the five models on the test window. Sentences made by code that compare the Random Forest with each baseline. They say better, equal, or worse as the numbers show.
- **Limits.** Open requests are left out. This favors fast closures. The data covers one year, and the test window is the last quarter. A closed request is not always a fixed problem. N is the same for all problem types, but agencies have different service targets. The weights make precision lower at the threshold 0.5.

Commands:

```bash
PYTHONPATH=python .venv/bin/python -m nyc311.summary
PYTHONPATH=python .venv/bin/python -m nyc311.summary --check
```

**Exit check.**

- Both commands end with SUMMARY OK.
- docs/results\_summary.md has no TODO, TBD, nan, or None.
- The style check ends with STE CHECK OK for the files in docs/.

**Commits.**

- feat(python): add results summary generator
- docs: add results summary and rubric evidence

### Phase 10: Final check

**Goal.** Prove that the project runs from a clean clone. Complete the README. Tag the release.

**Tasks.**

1. Write scripts/run\_all.sh with set -euo pipefail. It runs these stages in order: check\_env.sh, the download (skipped if data/MANIFEST.json exists and verify\_download.py passes), sbt test, ProfileJob, ThresholdJob, RankingJob, FeatureJob, ConceptsJob with --hold-seconds 0, pytest, baselines, train, plots, summary, and ste\_check.py. It prints the name and the time of each stage. It stops at the first failure.
2. Add the option --rehearse. It runs the same stages on the slice, with the folders that end in \_slice and with train --fast. It must finish in a short time.
3. Run bash scripts/run\_all.sh --rehearse. It must end with ALL STAGES OK.
4. Complete README.md: the purpose in two sentences, the data source with a link and a note that the NYC Open Data terms of use apply, the run commands, the repository layout, where the results are, and the limits.
5. Add one sentence to README.md that states how AI tools were used. The human decides the wording.
6. Clone the repository into a new folder. Copy data/raw/311\_2025.tsv and the slice into the clone. Run bash scripts/run\_all.sh --rehearse there. If time allows, run the full chain with the option --skip-download.
7. Update docs/BUILD\_LOG.md. Commit. Tag the commit.

The slides and the report are not part of the build. The human prepares them from docs/results\_summary.md, docs/rubric\_evidence.md, and the figures.

**Exit check.**

- bash scripts/run\_all.sh --rehearse ends with ALL STAGES OK in the clean clone.
- git status shows no changes. git tag shows v1.0.0.
- Human checks: open every figure, read docs/results\_summary.md, and confirm that the three Spark UI screenshots exist.

**Commits and tag.**

- build: add run\_all script with rehearsal mode
- docs: complete README and build log
- Tag: git tag -a v1.0.0 -m 'Project Review 3 release'

## Commit rules

Each phase ends with commits that a reviewer can read in one pass. The history must show the build order. The commit lists in each phase are the plan. The agent may split a commit. It must not merge commits from different phases.

- Use the Conventional Commits format: type(scope): summary. The types are feat, fix, test, docs, build, chore, and refactor. The scopes are scala, python, data, and results.
- Write the summary in the imperative mood. Keep it under 72 characters. Do not end it with a period.
- Add a body only when the reason is not clear from the summary. Leave one blank line after the summary. Wrap the body at 72 characters. In a fix commit, state the cause.
- Make one logical change in each commit. Each commit must compile and pass the tests that exist at that point.
- Commit the last commit of a phase only after the exit check passes.
- Commit a test in the same commit as its code, or in the next commit.
- Add files by name with git add. Do not use git add -A or git add . .
- Before each commit, run git status --short and git diff --cached --stat. Check that no file is larger than 5 MB and that no ignored data is staged.
- Do not commit data/raw/, data/processed/, the slice outputs, logs, .venv, or scala/target/. Do commit data/MANIFEST.json, results/, and docs/.
- Add the BUILD\_LOG.md entry of a phase in the last commit of that phase. The entry has the date, the phase, the commit summaries, the result of the exit check, and the problems that the agent fixed.
- Do not push. The human pushes. Do not use git push --force, git reset --hard, or git rebase on commits that the human has seen, unless the human asks.
- Do not remove an attribution line that the commit tool adds.

Examples of good summaries:

- feat(scala): add line parser and cleaning rules
- fix(scala): count a duration of exactly N days as not slow
- docs(results): add model metrics and result tables

Examples of bad summaries: update stuff, final version, and fix bugs.

## Coding standards

### All languages

- Keep the code simple. A short clear function is better than a clever one.
- Use full words in names. The only short names are id, df, rdd, sc, and n.
- Give each function one job. Keep each function under 40 lines.
- Do not leave dead code, commented-out code, or debug prints in a commit.
- Do not use magic numbers. Put each setting in config/project.properties or in a named constant.
- Fail early with a clear message. Do not catch an exception and then continue. Exit with code 2 when the human must decide.
- Use the terms of this document: request, row, job, window, slice, and exit check.
- Make each script safe to run again. A second run overwrites its own outputs and gives the same result.
- Use the seed from the config wherever a step is random.
- Use paths relative to the repository root. Do not read or write outside the repository.

### Scala

- Use Scala 2.12.18, two spaces of indentation, and lines under 100 characters.
- Keep Args, Config, Parser, Cleaning, Windows, Stats, Keys, Features, and Csv pure. They do not import Spark.
- Use case classes, Option, and Either. Do not use null. Do not call get on an Option. Avoid var.
- Put the functions that run on workers in top-level objects. Do not capture the enclosing class or the SparkContext in a closure.
- Use reduceByKey or aggregateByKey. Do not use groupByKey.
- Call collect only on small results. Check the size first.
- Persist an RDD that two or more actions use. Unpersist it when the job no longer needs it.
- Do not call setMaster in code. The command spark-submit sets the master.
- Convert each input path to an absolute file URI before you call sc.textFile.
- Sort results before you write them. The output must not depend on the order of the partitions.
- Put a comment above each block of RDD operations. State why the block is there. Do not repeat the code.
- Fix every compiler warning in project code.

### Python

- Use Python 3.11. Add type hints and a one-line docstring to every public function.
- Keep lines under 88 characters. Use pathlib for paths. Use logging in library code. A script prints only its stage lines and the final OK line.
- Give each module a main() function and the guard if **name** == '**main**'.
- Do not call toPandas() on a large DataFrame. Call it only after an aggregation, with limit().
- Write metrics, grouping, and title code as pure functions. Test them.
- Do not use wildcard imports.

### Shell

- Start every script with set -euo pipefail. Quote every variable. Print the command before it runs.

### Tests

- Test every pure function and every guard.
- Use small synthetic data in tests only. Name it fixture. No job reads a fixture.
- Never delete, skip, or weaken a failing test to pass an exit check. Fix the code. If the test is wrong, state the reason in the commit body.

### Figures

- Use 10 by 5.6 inches, 200 dpi, and PNG. Use a font size of at least 11 points.
- Use the Okabe-Ito colors: #0072B2 blue, #E69F00 orange, #009E73 green, #D55E00 vermillion, #CC79A7 purple, #56B4E9 sky blue, and #000000 black. Use one accent color and gray for the rest. Do not mark a difference with red and green alone.
- Label each axis with its unit. Start bars at zero. Sort bars by value. Label the values directly when there are fewer than 15 bars.
- Write a title that states the finding. Build it from the data. Add a footer with the source, for example: Source: NYC 311 requests created in 2025. Slow means more than N days to close.
- Show the Wilson interval as error bars in figures that rank groups.
- Make one point in each figure. Do not use 3D, pie charts, or two y-axes.

## Writing standards

Humans read the code, the comments, and the documents of this project. If a human finds the text unclear, the build has failed. All text follows the rules of Simplified Technical English (ASD-STE100).

The official standard has a dictionary of about 900 approved words. The agent does not have the dictionary. The agent follows the writing rules below, uses plain words, and uses the project terms as technical names. Technical names such as Spark, RDD, partition, and cache are allowed.

### Where the rules apply

- Code comments and docstrings.
- Log lines, error messages, and exit messages.
- Commit messages.
- README.md, the files in docs/, and BUILD\_LOG.md.
- Figure titles, axis labels, and footers.

Names of variables, functions, and files follow the coding standards. Use plain words in them.

### Writing rules

1. Write instructions in 20 words or fewer. Write descriptions in 25 words or fewer.
2. Give one instruction in each sentence. Start it with a verb: Run the check. Read the file.
3. Use the active voice. Write 'The job writes the file', not 'The file is written by the job'.
4. Use the simple present tense for facts and instructions. Use the simple past tense for what happened. Do not use will.
5. Keep the articles a, an, and the. Write 'Read the file', not 'Read file'.
6. Use one word for one meaning. Use the terms of this document. Do not swap them for synonyms.
7. Do not put more than three nouns in a row.
8. Do not use idioms, slang, or contractions.
9. Put the condition first: 'If the check fails, stop.'
10. Keep a paragraph to 6 sentences or fewer. Give each paragraph one topic.
11. Use a list for steps and for parallel items.
12. Define an abbreviation the first time a document uses it.

### Writing that sounds machine-made is not allowed

Every sentence must carry a fact, a number, a condition, or an instruction.

- Do not use these words: delve, robust, seamless, leverage, comprehensive, cutting-edge, state-of-the-art, game-changer, powerful, streamline, crucial, pivotal, holistic, unlock, harness, tapestry, landscape, elevate, empower, journey, synergy, and paradigm.
- Do not use these openings and fillers: it is worth noting, it is important to note, in today's world, let's, dive into, moreover, furthermore, additionally, overall, in conclusion, in summary, basically, essentially, simply, just, very, really, and quite.
- Do not use emoji, exclamation marks, rhetorical questions, or the em dash. End the sentence with a full stop and begin a new one.
- Do not praise the work or the result. State what the result is.
- Do not write a comment that repeats the code. Write a comment only to state why.
- Do not state a result that no file supports. Name the file next to the number.
- State uncertainty as a fact: 'The test window covers one quarter.' Do not use vague hedges such as may potentially or could possibly.

### Words to replace

| Do not write | Write |
| --- | --- |
| utilize, leverage | use |
| perform | do |
| ensure | make sure |
| in order to | to |
| prior to | before |
| subsequent, subsequently | next, after |
| approximately | about |
| additional | more |
| terminate | stop |
| obtain | get |
| commence | start |
| require (as a verb) | need |
| e.g., i.e. | for example, that is |

### Examples

| Not allowed | Allowed |
| --- | --- |
| // Leverage a robust broadcast to seamlessly enrich each row | // Send the history table to every worker. This avoids a shuffle join. |
| Oops! Something went wrong while processing the data. | Download failed for month 2025-03 after 6 tries. Last status: HTTP 429. Set SOCRATA\_APP\_TOKEN and run the script again. |
| Powerfully computes the metrics. | Return accuracy, precision, recall, and F1 of the slow class. |
| Let's kick off the training! | Training started: 3 pipelines, {train\_rows} train rows. |
| The model delivers impressive results. | In the test window, the Random Forest F1 is {rf\_f1}. The history rule F1 is {rule\_f1}. |
| Improved things and fixed bugs | fix(scala): reject rows with a closed date before the created date |

### Style check

The agent writes scripts/ste\_check.py in Phase 0. The script reads the comments and docstrings of .scala, .py, and .sh files. It also reads the prose of .md files. It skips code blocks and tables in Markdown. It skips docs/BUILD\_PLAN.md, AGENTS.md, scripts/ste\_check.py, and the test of the script, because they list the words that are not allowed.

The script reports each of these problems with the file name and the line number:

- A sentence of more than 25 words.
- A paragraph of more than 6 sentences.
- A word from the list of words that are not allowed.
- A contraction, an exclamation mark, an em dash, an emoji, or the abbreviations e.g. and i.e.

The script ends with STE CHECK OK, or it lists the problems and exits with code 1. It finds common problems. It does not prove that a text follows ASD-STE100. The agent also reads its own text before each commit.

## Rules for the coding agent

The agent copies this section to AGENTS.md in Phase 0.

### Scope and honesty

- Build only what this document describes. Do not add features, tools, notebooks, or folders.
- Use only the real NYC 311 data from the city API. Use synthetic data in unit tests only.
- Take every number in a document from a file in results/, from data/MANIFEST.json, or from run\_params.properties. Name the file next to the number.
- Report the results as computed. If the model does not beat a baseline, say so.
- Never change an expected value, a threshold, or a test to make a check pass.
- Do not say that a step passed unless you ran its command and read the output.

### Data and leakage

- Never use closed\_date, a resolution field, status, or due\_date as a feature.
- Split by time: history window, then train window, then test window.
- Compute the history features and set N from the history window only.
- Do not tune any setting on the test window.
- Download only the 11 columns of this document. Do not store addresses, names, phone numbers, or free text.

### Safety

- Run every command from the repository root.
- Do not use sudo. The human installs the system tools.
- Do not change or delete files outside the repository. Inside it, delete only files that the build made.
- Do not change shell profiles, global settings, or the system Java.
- Use the network only for data.cityofnewyork.us, repo1.maven.org, pypi.org, files.pythonhosted.org, github.com, and astral.sh. Do not upload data or results anywhere.
- Do not write the Socrata app token to a file, a log, or Git.

### Process

- Read this document at the start of every session. Read docs/BUILD\_LOG.md to find the current phase.
- Make one task for each task of the current phase. Mark each task done only after its check passes.
- Run each exit check yourself and read its output. Do not guess the result.
- Run each Scala job on the slice first. Run it on the full file only after the slice run passes.
- After each phase, add an entry to docs/BUILD\_LOG.md.
- Run scripts/ste\_check.py before every commit that changes text.
- End each phase with a short report: what passed and what is open.

### When to stop and ask the human

Stop and ask when one of these happens:

- An exit check still fails after two fixes.
- A decision in this document cannot be kept.
- ThresholdJob exits with code 2.
- The city API returns other column names or another format than this document states.
- A command fails because the computer has too little memory or disk space.
- A step needs a tool, a version, or a permission that this document does not list.

When you stop, state what failed, the command, the last 20 lines of its output, what you tried, and what you need.

## Plan for a build with no errors

No plan can promise a build without errors. This plan lowers the chance of errors in three ways. It pins every version. It tests each step on a small slice before the full run. It stops at the first failed check.

### Safeguards

- **Pinned versions.** Java 17, Spark 3.5.9, Scala 2.12.18, Python 3.11, and five Python packages. The Python packages were installed together on Python 3.11, and a PySpark smoke test passed on 15 Oct 2026.
- **Environment check.** Phase 0 finds version problems before any project code runs.
- **Slice first.** Every Scala job and the training run on the slice before the full run. The command run\_all.sh --rehearse repeats the whole chain on the slice.
- **Row reconciliation.** Lines read must equal the rejected rows plus the dropped rows plus the clean rows. Each ranking grain must add up to the clean rows. No row disappears without a count.
- **Hard checks in code.** The jobs and the Python modules stop with an error when a check fails. They do not continue with bad data.
- **Leakage guards.** Time windows do not overlap. No feature comes from a field that exists only after closing.
- **Unit tests.** Every pure function and every guard has a test.
- **Repeatable runs.** Fixed seeds. Sorted output. Scripts that overwrite their own outputs.
- **Build log.** Each phase records its result and its problems.

### What was checked while writing this plan

- The schema comes from the official column definitions, read on 15 Oct 2026.
- A live API response showed the date format 2026-10-14T01:54:42.000 and an empty closed\_date for an open request.
- The Socrata documentation states a maximum page size of 50,000 rows for 2.0 endpoints.
- The five Python packages installed together on Python 3.11. A PySpark session counted rows and fitted a Random Forest on a small synthetic DataFrame.

### What was not checked

- The Scala build and the Spark jobs. Maven Central and the Spark download site were not reachable from the workspace where this plan was written. The Scala code, sbt 1.10.7, ScalaTest 3.2.18, and the Spark archive link are not tested. Phase 0 tests them first.
- The value lists of status, agency, and channel in the 2025 data. The live checks for these fields returned unusable output. Phase 1 prints the real values.
- The speed of the download and the throttling by the city API.
- The run time and the memory use of the Random Forest on the human's computer. The RAM of that computer is not known.

### Risks and fallbacks

| Risk | Sign | Fallback |
| --- | --- | --- |
| Wrong Java version | check\_env.sh prints FAIL for Java | Install JDK 17. Set JAVA\_HOME. Run the check again. |
| Spark and PySpark versions differ | check\_env.sh prints FAIL for the Spark version | Install Spark 3.5.9 and PySpark 3.5.9. Unset an old SPARK\_HOME. |
| sbt cannot download libraries | sbt stops with a resolve error | Check the internet and the proxy settings. Run sbt update. Ask the human. |
| The city API throttles | HTTP 429 in the log | The script retries. Set SOCRATA\_APP\_TOKEN. Run the script again. It skips finished months. |
| The city API changes the columns | verify\_download.py fails on the header | Stop and ask the human. |
| A Scala job runs out of memory | java.lang.OutOfMemoryError | Raise spark\_driver\_memory in the config, for example to 6g. Close other programs. Run again. |
| Training runs out of memory | OutOfMemoryError or a lost executor | Lower rf\_num\_trees and rf\_subsampling\_rate. Raise the driver memory. Record the change in the build log. |
| Training takes too long | No TRAIN OK in the time the human accepts | Rehearse with --fast. For the final run, set rf\_num\_trees to 40 and rf\_max\_depth to 8. Record the change. |
| Port 4040 is busy | The job prints another Spark UI address | Use the printed address. |
| The slow share differs between train and test | feature\_summary.csv shows two different shares | This is a finding, not an error. Report it. |
| No candidate N gives a slow share between 10% and 50% | ThresholdJob exits with code 2 | Stop and ask the human to choose N. |
| The disk is full | A write fails | Free 10 GB. Run the job again. Jobs overwrite their own output. |

### Definition of done

- Every exit check of Phases 0 to 10 has passed.
- The rehearsal passes in a clean clone.
- The three Spark UI screenshots exist.
- docs/results\_summary.md is complete, and the style check ends with STE CHECK OK.
- The human has opened every figure and read the results summary.

## Rubric map

Each grading item of the course rubric maps to a phase and a file. Phase 9 copies this table to docs/rubric\_evidence.md.

| Rubric item | Group (marks) | Phase | Evidence |
| --- | --- | --- | --- |
| Dataset, problem, and attributes | Course step 1 | 1 | data/MANIFEST.json, section Dataset schema, docs/results\_summary.md |
| RDD created from the dataset | Scala and Spark (10) | 2 | ProfileJob.scala, results/tables/profile\_row\_counts.csv |
| At least 3 transformations | Scala and Spark (10) | 2, 3 | map, filter, flatMap, reduceByKey, and sortBy in ProfileJob.scala and RankingJob.scala |
| At least 2 actions | Scala and Spark (10) | 2, 3 | count, first, take, collect, and reduce in ProfileJob.scala |
| Key-value RDD operations | Scala and Spark (10) | 3 | reduceByKey, aggregateByKey, and join in RankingJob.scala, results/tables/rank\_\*.csv, results/tables/type\_owner.csv |
| Number of partitions | Scala and Spark (10) | 5 | results/spark/partitions.csv |
| RDD lineage | Scala and Spark (10) | 5 | results/spark/lineage.txt |
| DAG | Scala and Spark (10) | 5 | results/spark/ui/dag\_job.png |
| Fault tolerance | Scala and Spark (10) | 5 | results/spark/fault\_tolerance.csv, docs/spark\_concepts.md |
| cache() and persist() | Scala and Spark (10) | 5 | results/spark/cache\_timing.csv, results/spark/cache\_storage.csv, results/spark/ui/storage.png |
| Data and feature preparation | PySpark ML (3) | 4, 7 | data/processed/features.parquet, python/nyc311/features.py, results/tables/feature\_summary.csv |
| Train and test split | PySpark ML (3) | 6 | python/nyc311/data.py, the leakage tests |
| At least one ML model | PySpark ML (3) | 7 | python/nyc311/models.py, results/metrics.json |
| Accuracy, precision, recall, and F1 | PySpark ML (3) | 6, 7 | results/metrics.json, results/tables/metrics\_by\_model.csv, results/tables/confusion\_matrix\_rf.csv |
| At least 3 charts | Visualization and results (2) | 8 | results/figures/ with 10 PNG files |
| Results and discussion | Visualization and results (2) | 9 | docs/results\_summary.md |
