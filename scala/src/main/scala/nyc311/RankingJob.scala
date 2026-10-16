package nyc311

import java.nio.charset.StandardCharsets
import java.nio.file.{Files, Paths}
import org.apache.spark.rdd.RDD
import org.apache.spark.storage.StorageLevel
import org.apache.spark.{SparkConf, SparkContext}

object RankingJob {
  import Pipeline.{collectSmall, fail}

  // Grain, output file, and whether the table is a ranking (true) or a pattern (false).
  private val Tables: Vector[(String, String, Boolean)] = Vector(
    (Keys.Agency, "rank_agency.csv", true),
    (Keys.ComplaintType, "rank_complaint_type.csv", true),
    (Keys.Borough, "rank_borough.csv", true),
    (Keys.Zip, "rank_zip.csv", true),
    (Keys.AgencyType, "rank_agency_type.csv", true),
    (Keys.TypeBorough, "rank_type_borough.csv", true),
    (Keys.Hour, "pattern_hour.csv", false),
    (Keys.DayOfWeek, "pattern_dow.csv", false),
    (Keys.Month, "pattern_month.csv", false)
  )
  private val StatColumns = Seq("n", "mean_days", "slow_share", "wilson_low", "wilson_high")

  def main(args: Array[String]): Unit = {
    val options = Pipeline.parseArgs(args)
    val input = Pipeline.required(options, "input")
    val outDir = options.getOrElse("out", Pipeline.DefaultOutput)
    val processed = options.getOrElse("processed", Pipeline.DefaultProcessed)
    val config = Pipeline.loadConfig()
    val sc = new SparkContext(new SparkConf().setAppName("RankingJob"))
    try {
      run(sc, input, outDir, readThreshold(processed), Pipeline.minPartitions(options), config)
    } finally {
      sc.stop()
    }
  }

  private def readThreshold(processed: String): Int = {
    val path = Paths.get(processed, RunParams.FileName)
    if (!Files.exists(path)) {
      fail(s"$path is missing. Run ThresholdJob first.", Pipeline.HumanDecisionExit)
    }
    val text = new String(Files.readAllBytes(path), StandardCharsets.UTF_8)
    RunParams.thresholdDays(text).fold(message => fail(message, Pipeline.FailureExit), identity)
  }

  private def run(
      sc: SparkContext, input: String, outDir: String, thresholdDays: Int, minPartitions: Int,
      config: Config
  ): Unit = {
    val clean = Pipeline.cleanRows(sc, input, minPartitions)
    val cleanCount = clean.count()
    val threshold = thresholdDays.toDouble
    // Emit one pair for each grain of each row. Then combine the pairs without groupByKey.
    val aggregated = clean
      .flatMap(record => Keys.grainKeys(record).map(key =>
        (key, Stats.single(record.durationDays, threshold))))
      .aggregateByKey(Stats.zero)(
        (left, right) => Stats.merge(left, right), (left, right) => Stats.merge(left, right))
      .persist(StorageLevel.MEMORY_AND_DISK)

    println(s"slow threshold: $thresholdDays days, clean rows: $cleanCount")
    Tables.foreach { case (grain, fileName, isRanking) =>
      writeTable(aggregated, grain, s"$outDir/$fileName", isRanking, cleanCount, config)
    }
    writeTypeOwner(aggregated, s"$outDir/type_owner.csv")
    aggregated.unpersist(blocking = true)
    clean.unpersist(blocking = true)
    println("RANKING OK")
  }

  private def writeTable(
      aggregated: RDD[(String, Agg)], grain: String, path: String, isRanking: Boolean,
      cleanCount: Long, config: Config
  ): Unit = {
    val groups = collectSmall(aggregated.filter { case (key, _) => Keys.grainOf(key) == grain })
    val total = groups.map { case (_, agg) => agg.n }.sum
    if (total != cleanCount) {
      fail(s"Reconcile failed for $grain: $total rows in groups, $cleanCount clean rows.",
        Pipeline.FailureExit)
    }
    println(s"reconcile: ok $grain")
    val kept = if (isRanking) groups.filter(_._2.n >= config.minGroupSize) else groups
    val ordered =
      if (isRanking) kept.sortBy { case (key, agg) => (-slowShare(agg), -agg.n, key) }
      else kept.sortBy { case (key, _) => key }
    val rows = ordered.toSeq.map { case (key, agg) => Keys.parse(key)._2 ++ statistics(agg) }
    Csv.write(path, Keys.GroupColumns(grain) ++ StatColumns, rows)
  }

  private def slowShare(agg: Agg): Double = agg.slowCount.toDouble / agg.n

  private def statistics(agg: Agg): Seq[Any] = {
    val (low, high) = Stats.wilson(agg.slowCount, agg.n)
    Seq[Any](agg.n, agg.sumDays / agg.n, slowShare(agg), low, high)
  }

  // Find the agency with the most requests for each type. Join it with the Agg of the type.
  private def writeTypeOwner(aggregated: RDD[(String, Agg)], path: String): Unit = {
    val dominant = aggregated
      .filter { case (key, _) => Keys.grainOf(key) == Keys.AgencyType }
      .map { case (key, agg) =>
        val parts = Keys.parse(key)._2
        (parts(1), (parts(0), agg.n))
      }
      .reduceByKey((left, right) =>
        if (right._2 > left._2 || (right._2 == left._2 && right._1 < left._1)) right else left)
    val totals = aggregated
      .filter { case (key, _) => Keys.grainOf(key) == Keys.ComplaintType }
      .map { case (key, agg) => (Keys.parse(key)._2(0), agg) }
    val joined = collectSmall(dominant.join(totals))
    val rows = joined.sortBy { case (complaintType, (_, agg)) => (-agg.n, complaintType) }
      .toSeq.map { case (complaintType, ((agency, dominantRows), agg)) =>
        complaintType +: agency +: (dominantRows.toDouble / agg.n) +: statisticsFrom(agg)
      }
    Csv.write(path, Seq("complaint_type", "dominant_agency", "dominant_share", "n",
      "slow_share", "wilson_low", "wilson_high"), rows)
  }

  private def statisticsFrom(agg: Agg): Seq[Any] = {
    val (low, high) = Stats.wilson(agg.slowCount, agg.n)
    Seq[Any](agg.n, slowShare(agg), low, high)
  }
}
