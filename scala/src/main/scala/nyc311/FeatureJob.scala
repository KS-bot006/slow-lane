package nyc311

import java.io.File
import java.nio.charset.StandardCharsets
import java.nio.file.{Files, Paths}
import org.apache.spark.broadcast.Broadcast
import org.apache.spark.rdd.RDD
import org.apache.spark.sql.functions.{col, max, min, sum, when}
import org.apache.spark.sql.types._
import org.apache.spark.sql.{DataFrame, Row, SparkSession}
import org.apache.spark.storage.StorageLevel
import org.apache.spark.SparkConf

object FeatureJob {
  import Pipeline.{collectSmall, fail, FailureExit}

  private val MaxHistoryEntries = 200000
  private val OutputPartitions = 8
  private val ParquetName = "features.parquet"
  private val HistoryColumns: Vector[String] = for {
    prefix <- Features.HistoryKeys
    suffix <- Vector("slow_rate", "mean_log_days", "log_n")
  } yield s"${prefix}_$suffix"

  private def textColumns(names: String*): Vector[StructField] =
    names.toVector.map(name => StructField(name, StringType, nullable = false))

  private val Schema: StructType = StructType(
    textColumns("unique_key", "window", "created_date") ++
      Vector(StructField("label", DoubleType, nullable = false),
        StructField("duration_days", DoubleType, nullable = false)) ++
      textColumns("agency", "complaint_type", "descriptor_g", "location_type_g", "borough",
        "channel", "zip") ++
      Vector("hour", "dow", "is_weekend").map(name =>
        StructField(name, IntegerType, nullable = false)) ++
      HistoryColumns.map(name => StructField(name, DoubleType, nullable = false))
  )

  def main(args: Array[String]): Unit = {
    val options = Pipeline.parseArgs(args)
    val input = Pipeline.required(options, "input")
    val outDir = options.getOrElse("out", Pipeline.DefaultOutput)
    val processed = options.getOrElse("processed", Pipeline.DefaultProcessed)
    val config = Pipeline.loadConfig()
    val conf = new SparkConf().setAppName("FeatureJob")
    val spark = SparkSession.builder().config(conf).getOrCreate()
    try {
      run(spark, input, outDir, processed, Pipeline.minPartitions(options), config)
    } finally {
      spark.stop()
    }
  }

  private def run(
      spark: SparkSession, input: String, outDir: String, processed: String,
      minPartitions: Int, config: Config
  ): Unit = {
    val sc = spark.sparkContext
    val threshold = readThreshold(processed)
    val clean = Pipeline.cleanRows(sc, input, minPartitions)
    // Keep the history rows. Every history statistic comes from these rows only.
    val history = clean.filter(record =>
      Windows.windowOf(record.created.toLocalDate, config).contains(Windows.History))
    val tables = buildTables(history, config, threshold)
    // Send the tables to every worker. This avoids a shuffle join.
    val shared = sc.broadcast(tables)

    val windowed = clean.flatMap(record =>
      Windows.windowOf(record.created.toLocalDate, config)
        .filter(window => window == Windows.Train || window == Windows.Test)
        .map(window => (window, record)))
    val features = windowed.map { case (window, record) =>
      Features.build(record, window, shared.value)
    }.persist(StorageLevel.MEMORY_AND_DISK)

    val expectedRows = windowed.count()
    val path = s"$processed/$ParquetName"
    writeParquet(spark, features, path)
    checkParquet(spark, path, expectedRows)
    writeSummary(outDir, features)
    writeBuckets(outDir, tables, history)
    writeCoverage(outDir, windowed, shared)
    features.unpersist(blocking = true)
    clean.unpersist(blocking = true)
    println("FEATURES OK")
  }

  private def readThreshold(processed: String): Double = {
    val path = Paths.get(processed, RunParams.FileName)
    if (!Files.exists(path)) {
      fail(s"$path is missing. Run ThresholdJob first.", Pipeline.HumanDecisionExit)
    }
    val text = new String(Files.readAllBytes(path), StandardCharsets.UTF_8)
    RunParams.thresholdDays(text).fold(message => fail(message, FailureExit), identity).toDouble
  }

  // Build the history maps, the history-wide statistics, and the two bucket sets.
  private def buildTables(
      history: RDD[CleanRecord], config: Config, threshold: Double
  ): HistoryTables = {
    val overall = history.aggregate(Stats.zero)(
      (agg, record) => Stats.add(agg, record.durationDays, threshold),
      (left, right) => Stats.merge(left, right))
    if (overall.n == 0L) fail("The history window has no clean rows.", FailureExit)
    val descriptors = history.map(_.descriptor)
    val locationTypes = history.map(_.locationType)
    HistoryTables(
      h1 = historyMap(history, threshold, Features.h1Key),
      h2 = historyMap(history, threshold, Features.h2Key),
      h3 = historyMap(history, threshold, Features.h3Key),
      overall = overall,
      topDescriptors = topValues(descriptors, config.topDescriptors).map(_._1).toSet,
      topLocationTypes = topValues(locationTypes, config.topLocationTypes).map(_._1).toSet,
      smoothingM = config.smoothingM.toDouble,
      thresholdDays = threshold
    )
  }

  private def historyMap(
      history: RDD[CleanRecord], threshold: Double, keyOf: CleanRecord => String
  ): Map[String, Agg] = {
    val aggregated = history
      .map(record => (keyOf(record), Stats.single(record.durationDays, threshold)))
      .aggregateByKey(Stats.zero)(
        (left, right) => Stats.merge(left, right), (left, right) => Stats.merge(left, right))
    if (aggregated.count() > MaxHistoryEntries) {
      fail(s"A history map has more than $MaxHistoryEntries entries.", FailureExit)
    }
    aggregated.collectAsMap().toMap
  }

  // The most frequent values. Ties break by the value, so each run gives the same result.
  private def topValues(values: RDD[String], count: Int): Array[(String, Long)] =
    values.map(value => (value, 1L)).reduceByKey(_ + _)
      .top(count)(Ordering.by[(String, Long), (Long, String)](pair => (pair._2, pair._1)))

  private def writeParquet(spark: SparkSession, features: RDD[FeatureRow], path: String): Unit = {
    val rows = features.map(feature => Row.fromSeq(
      Seq(feature.uniqueKey, feature.window, feature.createdDate, feature.label,
        feature.durationDays, feature.agency, feature.complaintType, feature.descriptorG,
        feature.locationTypeG, feature.borough, feature.channel, feature.zip, feature.hour,
        feature.dow, feature.isWeekend) ++ feature.history))
    spark.createDataFrame(rows, Schema).coalesce(OutputPartitions)
      .write.mode("overwrite").parquet(fileUri(path))
  }

  private def fileUri(path: String): String = new File(path).getAbsoluteFile.toURI.toString

  // Read the written file again. Stop with an error if one check fails.
  private def checkParquet(spark: SparkSession, path: String, expectedRows: Long): Unit = {
    val frame: DataFrame = spark.read.parquet(fileUri(path))
    val nullSums = frame.select(frame.columns.map(name =>
      sum(when(col(name).isNull, 1).otherwise(0)).alias(name)): _*).first().toSeq
    if (nullSums.exists(value => Option(value).exists(_.asInstanceOf[Number].longValue() > 0L))) {
      fail("A feature column has a null value.", FailureExit)
    }
    val bounds = frame.groupBy("window").agg(min("created_date"), max("created_date")).collect()
      .map(row => row.getString(0) -> ((row.getString(1), row.getString(2)))).toMap
    if (bounds.keySet != Set(Windows.Train, Windows.Test)) {
      fail(s"The window column holds ${bounds.keySet}. Expected train and test.", FailureExit)
    }
    if (bounds(Windows.Train)._2 >= bounds(Windows.Test)._1) {
      fail("The latest train created_date is not before the earliest test created_date.",
        FailureExit)
    }
    val rows = frame.count()
    if (rows != expectedRows) {
      fail(s"The file has $rows rows. The clean train and test rows are $expectedRows.",
        FailureExit)
    }
    println(s"checks ok: $rows rows, no nulls, windows ordered")
  }

  private def writeSummary(outDir: String, features: RDD[FeatureRow]): Unit = {
    val counts = features.map(feature => (feature.window, (1L, feature.label.toLong)))
      .reduceByKey((left, right) => (left._1 + right._1, left._2 + right._2)).sortByKey()
    val rows = collectSmall(counts).toSeq.map { case (window, (rows, slow)) =>
      Seq[Any](window, rows, slow, slow.toDouble / rows)
    }
    Csv.write(s"$outDir/feature_summary.csv",
      Seq("window", "rows", "slow_rows", "slow_share"), rows)
  }

  private def writeBuckets(
      outDir: String, tables: HistoryTables, history: RDD[CleanRecord]
  ): Unit = {
    val rows = bucketRows("descriptor", tables.topDescriptors, history.map(_.descriptor)) ++
      bucketRows("location_type", tables.topLocationTypes, history.map(_.locationType))
    Csv.write(s"$outDir/bucket_lists.csv", Seq("kind", "value", "history_count"), rows)
  }

  private def bucketRows(kind: String, kept: Set[String], values: RDD[String]): Seq[Seq[Any]] = {
    val counts = values.filter(value => kept.contains(value)).map(value => (value, 1L))
      .reduceByKey(_ + _).sortBy({ case (value, count) => (-count, value) })
    collectSmall(counts).toSeq.map { case (value, count) => Seq[Any](kind, value, count) }
  }

  private def writeCoverage(
      outDir: String, windowed: RDD[(String, CleanRecord)], shared: Broadcast[HistoryTables]
  ): Unit = {
    val counts = windowed.flatMap { case (window, record) =>
      Features.keysOf(record).map { case (name, key) =>
        val covered = if (Features.hasHistory(name, key, shared.value)) 1L else 0L
        ((window, name), (1L, covered))
      }
    }.reduceByKey((left, right) => (left._1 + right._1, left._2 + right._2)).sortByKey()
    val rows = collectSmall(counts).toSeq.map { case ((window, name), (rows, covered)) =>
      Seq[Any](window, name, rows, covered, covered.toDouble / rows)
    }
    Csv.write(s"$outDir/history_coverage.csv",
      Seq("window", "key", "rows", "rows_with_history", "share"), rows)
  }
}
