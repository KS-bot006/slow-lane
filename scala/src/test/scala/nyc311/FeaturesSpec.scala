package nyc311

import nyc311.FixtureData.EitherValue
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.matchers.should.Matchers

class FeaturesSpec extends AnyFunSuite with Matchers {
  private def record(replacements: Map[Int, String] = Map.empty): CleanRecord =
    Cleaning.classify(Parser.parseLine(FixtureData.lineWith(replacements)).value, 2025).value

  // History: 10 rows in total, 3 slow, total ln(1 + days) of 5.0.
  private val overall = Agg(10L, 20.0, 5.0, 3L)

  private def tables(h1: Map[String, Agg] = Map.empty): HistoryTables =
    HistoryTables(
      h1, Map.empty, Map.empty, overall, Set("LOUD MUSIC"), Set("STREET/SIDEWALK"), 20.0, 3.0)

  test("the label is 1.0 only when the duration is strictly above N") {
    Features.label(3.0001, 3.0) shouldBe 1.0
    Features.label(3.0, 3.0) shouldBe 0.0
    Features.label(0.0, 3.0) shouldBe 0.0
  }

  test("a key that is not in the history gives the prior value") {
    val triple = Features.historyTriple(None, overall, 20.0)
    triple(0) shouldBe (0.3 +- 1e-12)
    triple(1) shouldBe (0.5 +- 1e-12)
    triple(2) shouldBe 0.0
  }

  test("a key in the history is smoothed toward the prior") {
    val triple = Features.historyTriple(Some(Agg(10L, 30.0, 8.0, 5L)), overall, 20.0)
    triple(0) shouldBe ((5.0 + 20.0 * 0.3) / 30.0 +- 1e-12)
    triple(1) shouldBe ((8.0 + 20.0 * 0.5) / 30.0 +- 1e-12)
    triple(2) shouldBe (math.log1p(10.0) +- 1e-12)
  }

  test("the weekend flag is 1 for day 6 and day 7") {
    (1 to 5).map(Features.isWeekend) shouldBe Seq.fill(5)(0)
    Features.isWeekend(6) shouldBe 1
    Features.isWeekend(7) shouldBe 1
  }

  test("a rare descriptor becomes OTHER") {
    Features.group("LOUD MUSIC", Set("LOUD MUSIC")) shouldBe "LOUD MUSIC"
    Features.group("RARE THING", Set("LOUD MUSIC")) shouldBe Features.Other
  }

  test("the three history keys use the planned fields") {
    val value = record()
    Keys.parse(Features.h1Key(value)) shouldBe
      ((Features.H1, Vector("NYPD", "NOISE - STREET", "LOUD MUSIC")))
    Keys.parse(Features.h2Key(value)) shouldBe
      ((Features.H2, Vector("NOISE - STREET", "BROOKLYN")))
    Keys.parse(Features.h3Key(value)) shouldBe ((Features.H3, Vector("11201")))
  }

  test("a feature row has the label, the groups, the ISO date, and nine history values") {
    val value = record()
    val row = Features.build(value, Windows.Train, tables())
    row.label shouldBe 0.0
    row.durationDays shouldBe 1.0
    row.createdDate shouldBe "2025-03-01T10:15:30"
    row.descriptorG shouldBe "LOUD MUSIC"
    row.locationTypeG shouldBe "STREET/SIDEWALK"
    row.isWeekend shouldBe 1
    row.history.length shouldBe 9
    row.history.take(3) shouldBe Features.historyTriple(None, overall, 20.0)
  }

  test("a feature row uses the history of a known key") {
    val value = record()
    val known = tables(Map(Features.h1Key(value) -> Agg(10L, 30.0, 8.0, 5L)))
    Features.build(value, Windows.Test, known).history(0) shouldBe ((5.0 + 6.0) / 30.0 +- 1e-12)
  }
}
