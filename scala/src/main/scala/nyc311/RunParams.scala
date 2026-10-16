package nyc311

import scala.util.Try

object RunParams {
  val FileName: String = "run_params.properties"

  def render(thresholdDays: Int, historyRows: Long, historySlowShare: Double): String =
    s"slow_threshold_days=$thresholdDays\nhistory_rows=$historyRows\n" +
      s"history_slow_share=$historySlowShare\n"

  def thresholdDays(text: String): Either[String, Int] =
    Config.parseProperties(text).get("slow_threshold_days")
      .flatMap(value => Try(value.toInt).toOption)
      .toRight(s"Key 'slow_threshold_days' is missing or not an integer in $FileName.")
}
