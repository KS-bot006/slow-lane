package nyc311

import nyc311.FixtureData.EitherValue
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.matchers.should.Matchers

class CleaningSpec extends AnyFunSuite with Matchers {
  private val year = 2025

  private def classify(replacements: Map[Int, String]) =
    Cleaning.classify(Parser.parseLine(FixtureData.lineWith(replacements)).value, year)

  test("a valid line gives one day and the time fields") {
    val record = classify(Map.empty).value
    record.durationDays shouldBe 1.0
    record.hourOfDay shouldBe 10
    record.dayOfWeek shouldBe 6
    record.agency shouldBe "NYPD"
    record.complaintType shouldBe "NOISE - STREET"
  }

  test("an open request is dropped") {
    classify(Map(2 -> "")) shouldBe Left(Constants.DropReason.OpenNoClosedDate)
  }

  test("a status other than Closed is dropped") {
    classify(Map(3 -> "Open")) shouldBe Left(Constants.DropReason.StatusNotClosed)
  }

  test("the status Closed is accepted in any case") {
    classify(Map(3 -> "CLOSED")).isRight shouldBe true
  }

  test("a request created outside the year is dropped") {
    classify(Map(1 -> "2024-12-31T23:59:59.000", 2 -> "2025-01-01T00:00:00.000")) shouldBe
      Left(Constants.DropReason.OutsideYear)
  }

  test("a negative duration is dropped") {
    classify(Map(2 -> "2025-02-28T10:15:30.000")) shouldBe
      Left(Constants.DropReason.ClosedBeforeCreated)
  }

  test("a duration of zero is valid") {
    val record = classify(Map(2 -> "2025-03-01T10:15:30.000")).value
    record.durationDays shouldBe 0.0
  }

  test("ZIP forms") {
    Cleaning.normalizeZip("11201") shouldBe "11201"
    Cleaning.normalizeZip("11201-1234") shouldBe "11201"
    Cleaning.normalizeZip("N/A") shouldBe Constants.UnknownText
  }

  test("borough forms") {
    Cleaning.normalizeBorough("Brooklyn") shouldBe "BROOKLYN"
    Cleaning.normalizeBorough("0") shouldBe Constants.UnspecifiedBorough
    Cleaning.normalizeBorough("Unspecified") shouldBe Constants.UnspecifiedBorough
  }

  test("duration buckets follow powers of two hours") {
    val hour = 1.0 / 24.0
    Cleaning.durationBucket(0.5 * hour) shouldBe 0
    Cleaning.durationBucket(1.0 * hour) shouldBe 1
    Cleaning.durationBucket(1.9 * hour) shouldBe 1
    Cleaning.durationBucket(2.0 * hour) shouldBe 2
    Cleaning.durationBucket(8.0 * hour) shouldBe 4
    Cleaning.durationBucket(24.0 * hour) shouldBe 5
  }
}
