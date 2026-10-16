package nyc311

import java.time.LocalDate
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.matchers.should.Matchers

class ArgsAndConfigSpec extends AnyFunSuite with Matchers {
  test("Args turns key value pairs into a map") {
    Args.parse(Seq("--input", "a.tsv", "--out", "dir")) shouldBe
      Right(Map("input" -> "a.tsv", "out" -> "dir"))
  }

  test("Args gives an error when a key has no value") {
    Args.parse(Seq("--input")).isLeft shouldBe true
    Args.parse(Seq("--input", "--out", "dir")).isLeft shouldBe true
  }

  test("Config reads the typed values") {
    val config = FixtureData.config
    config.year shouldBe 2025
    config.trainStart shouldBe LocalDate.of(2025, 7, 1)
    config.candidateThresholdDays shouldBe Vector(1, 3, 7)
    config.shareMin shouldBe 0.10
    config.sparkMaster shouldBe "local[*]"
  }

  test("Config names the missing key") {
    val values = Config.parseProperties(FixtureData.ConfigText) - "seed"
    Config.fromMap(values).left.toOption.exists(_.contains("seed")) shouldBe true
  }
}
