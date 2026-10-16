package nyc311

import java.io.File
import org.apache.spark.SparkContext
import org.apache.spark.rdd.RDD
import org.apache.spark.storage.StorageLevel

// Shared steps of the jobs. Pipeline and the jobs are the only objects that import Spark.
object Pipeline {
  val ConfigPath: String = "config/project.properties"
  val DefaultOutput: String = "results/tables"
  val DefaultProcessed: String = "data/processed"
  val DefaultMinPartitions: Int = 8
  val FailureExit: Int = 1
  val HumanDecisionExit: Int = 2
  private val MaxCollectRows = 10000

  def fail(message: String, code: Int): Nothing = {
    System.err.println(s"ERROR $message")
    sys.exit(code)
  }

  def parseArgs(args: Array[String]): Map[String, String] =
    Args.parse(args.toSeq).fold(message => fail(message, FailureExit), identity)

  def required(options: Map[String, String], key: String): String =
    options.getOrElse(key, fail(s"Argument --$key is missing.", FailureExit))

  def minPartitions(options: Map[String, String]): Int =
    options.get("min-partitions").map(_.toInt).getOrElse(DefaultMinPartitions)

  def loadConfig(): Config =
    Config.load(ConfigPath).fold(message => fail(message, FailureExit), identity)

  // Check the size before collect. A result above the limit stops the job.
  def collectSmall[T](rdd: RDD[T]): Array[T] = {
    val rows = rdd.take(MaxCollectRows + 1)
    if (rows.length > MaxCollectRows) {
      fail(s"A result has more than $MaxCollectRows rows. Stop before collect.", FailureExit)
    }
    rows
  }

  // Read the file, check the header, parse, clean, and keep the clean rows in memory or disk.
  def cleanRows(sc: SparkContext, path: String, minPartitions: Int): RDD[CleanRecord] = {
    val year = loadConfig().year
    // Use an absolute file URI so that the path does not depend on the Spark working folder.
    val lines = sc.textFile(new File(path).getAbsoluteFile.toURI.toString, minPartitions)
    println(s"partitions: ${lines.getNumPartitions}")
    if (lines.first() != Constants.Header) {
      fail(s"The first line of $path is not the expected header.", HumanDecisionExit)
    }
    lines.filter(line => line != Constants.Header)
      .map(Parser.parseLine)
      .flatMap(_.toOption)
      .map(request => Cleaning.classify(request, year))
      .flatMap(_.toOption)
      .persist(StorageLevel.MEMORY_AND_DISK)
  }
}
