package nyc311

import org.apache.spark.{SparkConf, SparkContext}

object Smoke {
  private val FallbackMaster = "local[2]"
  private val LastNumber = 1000

  def main(args: Array[String]): Unit = {
    // Use local[2] only when spark-submit gives no master. A direct run then still works.
    val baseConf = new SparkConf().setAppName("Smoke")
    val conf = if (baseConf.contains("spark.master")) baseConf else baseConf.setMaster(FallbackMaster)
    val sc = new SparkContext(conf)
    try {
      val total = sc.parallelize(1 to LastNumber).reduce(_ + _)
      println(s"SMOKE OK $total")
    } finally {
      sc.stop()
    }
  }
}
