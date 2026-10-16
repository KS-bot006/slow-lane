package nyc311

import java.time.LocalDate

object Windows {
  val History: String = "history"
  val Train: String = "train"
  val Test: String = "test"

  // Both end dates belong to the window. Other dates give None.
  def windowOf(date: LocalDate, config: Config): Option[String] =
    if (within(date, config.historyStart, config.historyEnd)) Some(History)
    else if (within(date, config.trainStart, config.trainEnd)) Some(Train)
    else if (within(date, config.testStart, config.testEnd)) Some(Test)
    else None

  private def within(date: LocalDate, start: LocalDate, end: LocalDate): Boolean =
    !date.isBefore(start) && !date.isAfter(end)
}
