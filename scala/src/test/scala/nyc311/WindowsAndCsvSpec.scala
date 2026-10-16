package nyc311

import java.time.LocalDate
import java.nio.file.{Files, Paths}
import java.nio.charset.StandardCharsets
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.matchers.should.Matchers

class WindowsAndCsvSpec extends AnyFunSuite with Matchers {
  private val config = FixtureData.config

  private def windowOf(year: Int, month: Int, day: Int) =
    Windows.windowOf(LocalDate.of(year, month, day), config)

  test("window boundaries include both end dates") {
    windowOf(2025, 1, 1) shouldBe Some(Windows.History)
    windowOf(2025, 6, 30) shouldBe Some(Windows.History)
    windowOf(2025, 7, 1) shouldBe Some(Windows.Train)
    windowOf(2025, 9, 30) shouldBe Some(Windows.Train)
    windowOf(2025, 10, 1) shouldBe Some(Windows.Test)
    windowOf(2025, 12, 31) shouldBe Some(Windows.Test)
  }

  test("dates outside the windows give None") {
    windowOf(2024, 12, 31) shouldBe None
    windowOf(2026, 1, 1) shouldBe None
  }

  test("Csv quotes a comma, a quote, and a newline") {
    Csv.escape("plain") shouldBe "plain"
    Csv.escape("a,b") shouldBe "\"a,b\""
    Csv.escape("say \"hi\"") shouldBe "\"say \"\"hi\"\"\""
    Csv.escape("line\nbreak") shouldBe "\"line\nbreak\""
  }

  test("Csv writes a header and rows with the line break \\n") {
    val path = Files.createTempFile("fixture", ".csv")
    Csv.write(path.toString, Seq("name", "rows"), Seq(Seq("a,b", 1L), Seq("c", 2L)))
    new String(Files.readAllBytes(path), StandardCharsets.UTF_8) shouldBe
      "name,rows\n\"a,b\",1\nc,2\n"
    Files.delete(Paths.get(path.toString))
  }
}
