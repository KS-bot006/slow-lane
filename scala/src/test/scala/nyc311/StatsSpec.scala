package nyc311

import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.matchers.should.Matchers

class StatsSpec extends AnyFunSuite with Matchers {
  private val tolerance = 0.001

  test("wilson(5, 10) is 0.2366 to 0.7634") {
    val (low, high) = Stats.wilson(5, 10)
    low shouldBe (0.2366 +- tolerance)
    high shouldBe (0.7634 +- tolerance)
  }

  test("wilson(0, 10) is 0.0 to 0.2775") {
    val (low, high) = Stats.wilson(0, 10)
    low shouldBe (0.0 +- tolerance)
    high shouldBe (0.2775 +- tolerance)
  }

  test("wilson of an empty group is zero") {
    Stats.wilson(0, 0) shouldBe ((0.0, 0.0))
  }

  test("wilson interval stays between 0 and 1") {
    val (low, high) = Stats.wilson(10, 10)
    low should be >= 0.0
    high should be <= 1.0
  }

  test("single marks a row slow only above the threshold") {
    Stats.single(3.0, 3.0).slowCount shouldBe 0L
    Stats.single(3.5, 3.0).slowCount shouldBe 1L
    Stats.single(3.5, 3.0).sumLogDays shouldBe math.log1p(3.5)
  }

  test("merging the Agg of two halves equals the Agg of the whole") {
    val durations = Vector(0.5, 1.0, 2.5, 4.0, 7.5, 0.25)
    val threshold = 3.0
    val whole = durations.foldLeft(Stats.zero)((agg, days) => Stats.add(agg, days, threshold))
    val (first, second) = durations.splitAt(3)
    val left = first.foldLeft(Stats.zero)((agg, days) => Stats.add(agg, days, threshold))
    val right = second.foldLeft(Stats.zero)((agg, days) => Stats.add(agg, days, threshold))
    val merged = Stats.merge(left, right)
    merged.n shouldBe whole.n
    merged.slowCount shouldBe whole.slowCount
    merged.sumDays shouldBe (whole.sumDays +- 1e-9)
    merged.sumLogDays shouldBe (whole.sumLogDays +- 1e-9)
  }

  test("smooth pulls a small group toward the prior") {
    Stats.smooth(0.0, 0L, 20.0, 0.3) shouldBe 0.3
    Stats.smooth(10.0, 10L, 20.0, 0.3) shouldBe ((10.0 + 6.0) / 30.0)
    Stats.smooth(5000.0, 10000L, 20.0, 0.3) shouldBe (0.5 +- 0.001)
  }
}
