# Spark concepts

ConceptsJob ran on the full file data/raw/311_2025.tsv with the master local[*]. The files named below are in results/spark/. Every number comes from one of these files.

## Partitions

A partition is one slice of an RDD. One task works on one partition. The base RDD from textFile has 16 partitions and 3655043 rows, including the header line. The partition sizes are in partitions.csv. The first 15 partitions hold 237483 to 242860 rows. The last partition holds 48444 rows, because it holds the end of the file.

The call repartition(16) shuffles the rows. Each of its 16 partitions holds 228437 to 228443 rows, so the sizes are almost equal. The call coalesce(2) joins neighbouring partitions without a shuffle. Its two partitions hold 1926247 and 1728796 rows, so the sizes are not equal.

## Lineage

Lineage is the record of the steps that build an RDD from its parents. lineage.txt shows the lineage of the clean rows and of byType. The clean rows have 16 partitions and one narrow dependency in each step. A narrow dependency means that each child partition reads one parent partition.

The step reduceByKey on complaint type and days creates a ShuffledRDD. Its ShuffleDependency means that each child partition reads data from many parent partitions. The file lineage.txt labels each dependency as narrow or shuffle.

## DAG

A DAG is the graph of the stages of a job. Spark cuts a stage at each shuffle. The job that counts byType has two stages. Stage 12 runs textFile, filter, map, and flatMap. Stage 13 runs reduceByKey.

The picture of the DAG is results/spark/ui/dag_job.png. The tab with all stages is results/spark/ui/stages.png.

## Cache

A cache keeps computed partitions, so that the next action does not compute them again.

The file cache_timing.csv shows the times of the count of the clean rows. Without the cache, the three runs take 2.180, 2.110, and 2.110 seconds. With persist(MEMORY\_AND\_DISK), the first run takes 7.521 seconds, because it fills the cache. The next two runs take 0.128 and 0.085 seconds.

The file cache\_storage.csv shows that all 16 of 16 partitions are cached. The storage level is Disk Memory Deserialized 1x Replicated. The cache holds 1958247816 bytes in memory and 41009876 bytes on disk. Spark writes a partition to disk when the memory is full. The pictures are results/spark/ui/storage.png and results/spark/ui/storage\_rdd.png.

## Fault tolerance

Spark can rebuild a lost partition from its lineage. The job drops all cached partitions with unpersist and then computes the count and the sum of the days again. The file fault\_tolerance.csv shows the same count, 3596374 rows, before and after. The sum of the days is also the same, and the column equal is true. The recompute takes 2.999 seconds.

This check is a simulation. A local run has one process and no executor that can fail. The unpersist call removes the cached data, as the loss of an executor would. The recompute from the lineage is the same mechanism that Spark uses after a real failure.

## Spark context

The file spark\_context.csv shows the master local[*], a default parallelism of 22, and 22 cores. A default parallelism of 22 means that Spark makes 22 partitions for a new RDD that has no other setting.
