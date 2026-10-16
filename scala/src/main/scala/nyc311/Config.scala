package nyc311

import java.nio.charset.StandardCharsets
import java.nio.file.{Files, Paths}
import java.time.LocalDate
import scala.util.Try

final case class Config(
    year: Int,
    historyStart: LocalDate,
    historyEnd: LocalDate,
    trainStart: LocalDate,
    trainEnd: LocalDate,
    testStart: LocalDate,
    testEnd: LocalDate,
    defaultThresholdDays: Int,
    candidateThresholdDays: Vector[Int],
    shareMin: Double,
    shareMax: Double,
    minGroupSize: Int,
    topDescriptors: Int,
    topLocationTypes: Int,
    smoothingM: Int,
    sparkMaster: String,
    sparkDriverMemory: String,
    rfNumTrees: Int,
    rfMaxDepth: Int,
    rfSubsamplingRate: Double,
    rfMinInstancesPerNode: Int,
    lrMaxIter: Int,
    seed: Int
)

object Config {
  // Read config/project.properties. Jobs run from the repository root.
  def load(path: String): Either[String, Config] =
    Try(new String(Files.readAllBytes(Paths.get(path)), StandardCharsets.UTF_8)).toEither.left
      .map(error => s"Cannot read $path: ${error.getMessage}")
      .flatMap(text => fromMap(parseProperties(text)))

  def parseProperties(text: String): Map[String, String] =
    text.split("\n").toVector
      .map(_.trim)
      .filter(line => line.nonEmpty && !line.startsWith("#") && line.contains("="))
      .map { line =>
        val index = line.indexOf('=')
        line.substring(0, index).trim -> line.substring(index + 1).trim
      }
      .toMap

  def fromMap(values: Map[String, String]): Either[String, Config] = {
    def text(key: String): Either[String, String] =
      values.get(key).toRight(s"Key '$key' is missing in the configuration.")
    def parsed[A](key: String, kind: String)(convert: String => A): Either[String, A] =
      text(key).flatMap(value =>
        Try(convert(value)).toOption.toRight(s"Key '$key' is not $kind: '$value'."))
    def int(key: String): Either[String, Int] = parsed(key, "an integer")(_.toInt)
    def double(key: String): Either[String, Double] = parsed(key, "a number")(_.toDouble)
    def date(key: String): Either[String, LocalDate] = parsed(key, "a date")(LocalDate.parse)
    def ints(key: String): Either[String, Vector[Int]] =
      parsed(key, "a list of integers")(_.split(",").toVector.map(_.trim.toInt))

    for {
      year <- int("year")
      historyStart <- date("history_start")
      historyEnd <- date("history_end")
      trainStart <- date("train_start")
      trainEnd <- date("train_end")
      testStart <- date("test_start")
      testEnd <- date("test_end")
      defaultThreshold <- int("default_threshold_days")
      candidates <- ints("candidate_threshold_days")
      shareMin <- double("share_min")
      shareMax <- double("share_max")
      minGroupSize <- int("min_group_size")
      topDescriptors <- int("top_descriptors")
      topLocationTypes <- int("top_location_types")
      smoothingM <- int("smoothing_m")
      master <- text("spark_master")
      memory <- text("spark_driver_memory")
      numTrees <- int("rf_num_trees")
      maxDepth <- int("rf_max_depth")
      subsampling <- double("rf_subsampling_rate")
      minInstances <- int("rf_min_instances_per_node")
      lrMaxIter <- int("lr_max_iter")
      seed <- int("seed")
    } yield Config(
      year, historyStart, historyEnd, trainStart, trainEnd, testStart, testEnd,
      defaultThreshold, candidates, shareMin, shareMax, minGroupSize, topDescriptors,
      topLocationTypes, smoothingM, master, memory, numTrees, maxDepth, subsampling,
      minInstances, lrMaxIter, seed
    )
  }
}
