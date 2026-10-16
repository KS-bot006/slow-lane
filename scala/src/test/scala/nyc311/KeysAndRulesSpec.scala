package nyc311

import nyc311.FixtureData.EitherValue
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.matchers.should.Matchers

class KeysAndRulesSpec extends AnyFunSuite with Matchers {
  test("a key survives the round trip through build and parse") {
    val parts = Seq("NOISE - STREET", "A|B,C \"D\"")
    Keys.parse(Keys.build(Keys.TypeBorough, parts)) shouldBe ((Keys.TypeBorough, parts.toVector))
  }

  test("a key with an empty part survives the round trip") {
    Keys.parse(Keys.build(Keys.Zip, Seq(""))) shouldBe ((Keys.Zip, Vector("")))
  }

  test("a record gives one key for each grain, and each key parses back") {
    val request = Parser.parseLine(FixtureData.ValidLine).value
    val record = Cleaning.classify(request, 2025).value
    val keys = Keys.grainKeys(record)
    keys.map(Keys.grainOf) shouldBe Keys.AllGrains
    Keys.parse(keys(4)) shouldBe ((Keys.AgencyType, Vector("NYPD", "NOISE - STREET")))
    Keys.parse(keys(6)) shouldBe ((Keys.Hour, Vector("10")))
    Keys.parse(keys(7)) shouldBe ((Keys.DayOfWeek, Vector("6")))
    Keys.parse(keys(8)) shouldBe ((Keys.Month, Vector("03")))
    Keys.AllGrains.forall(Keys.GroupColumns.contains) shouldBe true
  }

  private val candidates = Seq(1, 3, 7)

  private def select(share1: Double, share3: Double, share7: Double) =
    ThresholdRule.select(3, candidates, 0.10, 0.50, Map(1 -> share1, 3 -> share3, 7 -> share7))

  test("the default threshold stays when its share is in range") {
    select(0.60, 0.25, 0.05) shouldBe Right(3)
  }

  test("a low default share selects the smallest candidate") {
    select(0.30, 0.05, 0.01) shouldBe Right(1)
  }

  test("a high default share selects the largest candidate") {
    select(0.90, 0.60, 0.20) shouldBe Right(7)
  }

  test("a selected share out of range gives an error") {
    select(0.05, 0.04, 0.01).isLeft shouldBe true
    select(0.95, 0.90, 0.70).isLeft shouldBe true
  }

  test("the run parameters round trip") {
    val text = RunParams.render(3, 1734203L, 0.25)
    RunParams.thresholdDays(text) shouldBe Right(3)
    RunParams.thresholdDays("history_rows=1").isLeft shouldBe true
  }
}
