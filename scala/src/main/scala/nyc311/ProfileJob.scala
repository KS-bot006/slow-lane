package nyc311

import java.io.File
import org.apache.spark.rdd.RDD
import org.apache.spark.storage.StorageLevel
import org.apache.spark.{SparkConf, SparkContext}

object ProfileJob {
  import Pipeline.{collectSmall, fail, FailureExit, HumanDecisionExit => HeaderExit}

  private val ConfigPath = Pipeline.ConfigPath
  private val DefaultOutput = Pipeline.DefaultOutput
  private val DefaultMinPartitions = Pipeline.DefaultMinPartitions
  private val QuantileLevels = Vector(0.5, 0.75, 0.9, 0.95, 0.99)
  private val SampleSize = 5

  def main(args: Array[String]): Unit = {
    val options = Args.parse(args.toSeq).fold(message => fail(message, FailureExit), identity)
    val input = options.getOrElse("input", fail("Argument --input is missing.", FailureExit))
    val outDir = options.getOrElse("out", DefaultOutput)
    val minPartitions = options.get("min-partitions").map(_.toInt).getOrElse(DefaultMinPartitions)
    val config = Config.load(ConfigPath).fold(message => fail(message, FailureExit), identity)

    val sc = new SparkContext(new SparkConf().setAppName("ProfileJob"))
    try {
      run(sc, input, outDir, minPartitions, config)
    } finally {
      sc.stop()
    }
  }

  private def run(
      sc: SparkContext, input: String, outDir: String, minPartitions: Int, config: Config
  ): Unit = {
    // Use an absolute file URI so that the path does not depend on the Spark working folder.
    val uri = new File(input).getAbsoluteFile.toURI.toString
    val lines = sc.textFile(uri, minPartitions)
    val partitions = lines.getNumPartitions
    println(s"partitions: $partitions")
    if (lines.first() != Constants.Header) {
      fail(s"The first line of $input is not the expected header.", HeaderExit)
    }

    // Parse once and keep the result. Reject counts, drop counts, and clean rows reuse it.
    val parsed = lines.filter(line => line != Constants.Header)
      .map(Parser.parseLine)
      .persist(StorageLevel.MEMORY_AND_DISK)
    val year = config.year
    val classified = parsed.flatMap(_.toOption).map(request => Cleaning.classify(request, year))
    val clean = classified.flatMap(_.toOption).persist(StorageLevel.MEMORY_AND_DISK)

    val rejects = countByKey(parsed.flatMap(_.left.toOption))
    val drops = countByKey(classified.flatMap(_.left.toOption))
    val cleanCount = clean.count()
    val linesRead = lines.count()
    reconcile(linesRead, rejects, drops, cleanCount)

    val statuses = countByKey(parsed.flatMap(_.toOption).map(_.status))
    val months = countByKey(clean.map(record =>
      f"${record.created.getYear}%04d-${record.created.getMonthValue}%02d"))
    val windows = countByKey(clean.flatMap(record =>
      Windows.windowOf(record.created.toLocalDate, config)))
    val buckets = collectSmall(clean.map(record =>
      (Cleaning.durationBucket(record.durationDays), 1L)).reduceByKey(_ + _).sortByKey())
    val quantiles = durationQuantiles(clean, cleanCount)
    val maximum = clean.map(_.durationDays).reduce((left, right) => math.max(left, right))
    clean.take(SampleSize).foreach(record => println(s"sample: $record"))

    writeTables(outDir, partitions, linesRead, rejects, drops, cleanCount, statuses, months,
      windows, buckets, quantiles, maximum)
    clean.unpersist(blocking = true)
    parsed.unpersist(blocking = true)
    println("PROFILE OK")
  }

  // Count identical keys and sort by key, so the output does not depend on the partitions.
  private def countByKey(keys: RDD[String]): Array[(String, Long)] =
    collectSmall(keys.map(key => (key, 1L)).reduceByKey(_ + _).sortByKey())

  // Every line after the header must be a reject, a drop, or a clean row.
  private def reconcile(
      linesRead: Long, rejects: Array[(String, Long)], drops: Array[(String, Long)], clean: Long
  ): Unit = {
    val accounted = rejects.map(_._2).sum + drops.map(_._2).sum + clean
    println(s"lines read: $linesRead, accounted: $accounted (header excluded)")
    if (linesRead - 1 != accounted) {
      fail(s"Reconcile failed: ${linesRead - 1} data lines, $accounted accounted.", FailureExit)
    }
    println("reconcile: ok")
  }

  // Use the nearest rank. One pass over the sorted durations finds every quantile.
  private def durationQuantiles(clean: RDD[CleanRecord], count: Long): Seq[(Double, Double)] = {
    if (count == 0L) fail("No clean rows. Cannot compute quantiles.", FailureExit)
    val ranks = QuantileLevels.map(level => math.max(math.ceil(level * count).toLong - 1L, 0L))
    val wanted = ranks.toSet
    val sorted = clean.map(_.durationDays).sortBy(days => days).zipWithIndex()
    val found = collectSmall(sorted.filter { case (_, index) => wanted.contains(index) })
      .map { case (days, index) => index -> days }
      .toMap
    QuantileLevels.zip(ranks).map { case (level, rank) => (level, found(rank)) }
  }

  private def writeTables(
      outDir: String, partitions: Int, linesRead: Long, rejects: Array[(String, Long)],
      drops: Array[(String, Long)], cleanCount: Long, statuses: Array[(String, Long)],
      months: Array[(String, Long)], windows: Array[(String, Long)],
      buckets: Array[(Int, Long)], quantiles: Seq[(Double, Double)], maximum: Double
  ): Unit = {
    val rowCounts: Seq[Seq[Any]] =
      Seq(Seq("info", "partitions", partitions), Seq("lines", "lines_read", linesRead),
        Seq("lines", "header_lines", 1L)) ++
        rejects.map { case (reason, rows) => Seq("reject", reason, rows) } ++
        drops.map { case (reason, rows) => Seq("drop", reason, rows) } ++
        Seq(Seq("clean", "clean_rows", cleanCount)) ++
        windows.map { case (window, rows) => Seq[Any]("window", window, rows) }
    Csv.write(s"$outDir/profile_row_counts.csv", Seq("kind", "name", "rows"), rowCounts)
    Csv.write(s"$outDir/profile_status_counts.csv", Seq("status", "rows"),
      statuses.map { case (status, rows) => Seq(status, rows) })
    Csv.write(s"$outDir/profile_monthly_counts.csv", Seq("month", "rows"),
      months.map { case (month, rows) => Seq(month, rows) })
    Csv.write(s"$outDir/profile_duration_quantiles.csv", Seq("quantile", "days"),
      quantiles.map { case (level, days) => Seq(level, days) } :+ Seq("max", maximum))
    Csv.write(s"$outDir/profile_duration_hist.csv",
      Seq("bucket", "lower_hours", "upper_hours", "rows"),
      buckets.map { case (bucket, rows) => bucketRow(bucket, rows) })
  }

  private def bucketRow(bucket: Int, rows: Long): Seq[Any] =
    if (bucket == 0) Seq(0, 0, 1, rows) else Seq(bucket, 1L << (bucket - 1), 1L << bucket, rows)
}
