package nyc311

import java.time.LocalDateTime
import nyc311.FixtureData.EitherValue
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.matchers.should.Matchers

class ParserSpec extends AnyFunSuite with Matchers {
  test("a valid line becomes a Request") {
    val request = Parser.parseLine(FixtureData.ValidLine).value
    request.uniqueKey shouldBe "1001"
    request.created shouldBe LocalDateTime.of(2025, 3, 1, 10, 15, 30)
    request.closed shouldBe Some(LocalDateTime.of(2025, 3, 2, 10, 15, 30))
    request.zip shouldBe "11201"
  }

  test("a line with 10 fields is rejected") {
    val line = FixtureData.ValidLine.split("\t", -1).take(10).mkString("\t")
    Parser.parseLine(line) shouldBe Left(Constants.RejectReason.BadFieldCount)
  }

  test("an empty key is rejected") {
    Parser.parseLine(FixtureData.lineWith(Map(0 -> ""))) shouldBe
      Left(Constants.RejectReason.MissingKey)
  }

  test("a bad created date is rejected") {
    Parser.parseLine(FixtureData.lineWith(Map(1 -> "03/01/2025"))) shouldBe
      Left(Constants.RejectReason.BadCreatedDate)
  }

  test("an empty closed date becomes None") {
    val request = Parser.parseLine(FixtureData.lineWith(Map(2 -> ""))).value
    request.closed shouldBe None
  }

  test("a bad closed date is rejected") {
    Parser.parseLine(FixtureData.lineWith(Map(2 -> "soon"))) shouldBe
      Left(Constants.RejectReason.BadClosedDate)
  }

  test("an empty text field becomes UNKNOWN") {
    val request = Parser.parseLine(FixtureData.lineWith(Map(4 -> ""))).value
    request.agency shouldBe Constants.UnknownText
  }
}
