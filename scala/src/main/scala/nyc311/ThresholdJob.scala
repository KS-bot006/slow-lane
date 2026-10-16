package nyc311

import java.nio.charset.StandardCharsets
import java.nio.file.{Files, Paths}
import org.apache.spark.{SparkConf, SparkContext}

object ThresholdJob {
  import Pipeline.{collectSmall, fail}

  def main(args: Array[String]): Unit = {
    val options = Pipeline.parseArgs(args)
    val input = Pipeline.required(options, "input")
    val outDir = options.getOrElse("out", Pipeline.DefaultOutput)
    val processed = options.getOrElse("processed", Pipeline.DefaultProcessed)
    val config = Pipeline.loadConfig()
    val sc = new SparkContext(new SparkConf().setAppName("ThresholdJob"))
    try {
      run(sc, input, outDir, processed, Pipeline.minPartitions(options), config)
    } finally {
      sc.stop()
    }
  }

  private def run(
      sc: SparkContext, input: String, outDir: String, processed: String, minPartitions: Int,
      config: Config
  ): Unit = {
    val clean = Pipeline.cleanRows(sc, input, minPartitions)
    // Keep only the history window. The job never reads a train or test row.
    val history = clean.filter(record =>
      Windows.windowOf(record.created.toLocalDate, config).contains(Windows.History))
    val candidates = config.candidateThresholdDays
    // Count the slow rows for every candidate in one pass over the history rows.
    val slowCounts = collectSmall(history.flatMap(record => candidates.map(days =>
      (days, if (record.durationDays > days) 1L else 0L))).reduceByKey(_ + _)).toMap
    val historyRows = history.count()
    if (historyRows == 0L) fail("The history window has no clean rows.", Pipeline.FailureExit)
    val shares = candidates.map(days =>
      days -> slowCounts.getOrElse(days, 0L).toDouble / historyRows)
    val selected = ThresholdRule.select(
      config.defaultThresholdDays, candidates, config.shareMin, config.shareMax, shares.toMap
    ).fold(message => fail(message, Pipeline.HumanDecisionExit), identity)

    writeSelection(outDir, candidates, historyRows, slowCounts, selected)
    writeRunParams(processed, selected, historyRows, shares.toMap.getOrElse(selected, 0.0))
    clean.unpersist(blocking = true)
    println(s"selected threshold: $selected days")
    println("THRESHOLD OK")
  }

  private def writeSelection(
      outDir: String, candidates: Seq[Int], historyRows: Long, slowCounts: Map[Int, Long],
      selected: Int
  ): Unit = {
    val rows: Seq[Seq[Any]] = candidates.sorted.map { days =>
      val slow = slowCounts.getOrElse(days, 0L)
      Seq[Any](days, historyRows, slow, slow.toDouble / historyRows, days == selected)
    }
    Csv.write(s"$outDir/threshold_selection.csv",
      Seq("candidate_days", "history_rows", "slow_rows", "slow_share", "selected"), rows)
  }

  private def writeRunParams(
      processed: String, selected: Int, historyRows: Long, historySlowShare: Double
  ): Unit = {
    val path = Paths.get(processed, RunParams.FileName)
    Files.createDirectories(path.getParent)
    val text = RunParams.render(selected, historyRows, historySlowShare)
    Files.write(path, text.getBytes(StandardCharsets.UTF_8))
    ()
  }
}
