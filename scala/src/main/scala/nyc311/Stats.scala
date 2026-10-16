package nyc311

// Sums for one group. sumLogDays holds the sum of log(1 + days).
final case class Agg(n: Long, sumDays: Double, sumLogDays: Double, slowCount: Long)

object Stats {
  private val WilsonZ = 1.96

  val zero: Agg = Agg(0L, 0.0, 0.0, 0L)

  // The Agg of one row. The row is slow when its duration is above the threshold.
  def single(durationDays: Double, thresholdDays: Double): Agg =
    Agg(1L, durationDays, math.log1p(durationDays), if (durationDays > thresholdDays) 1L else 0L)

  def add(agg: Agg, durationDays: Double, thresholdDays: Double): Agg =
    merge(agg, single(durationDays, thresholdDays))

  def merge(left: Agg, right: Agg): Agg =
    Agg(
      left.n + right.n,
      left.sumDays + right.sumDays,
      left.sumLogDays + right.sumLogDays,
      left.slowCount + right.slowCount
    )

  // Wilson score interval for k slow rows out of n rows. An empty group gives (0, 0).
  def wilson(k: Long, n: Long): (Double, Double) =
    if (n <= 0L) {
      (0.0, 0.0)
    } else {
      val total = n.toDouble
      val share = k.toDouble / total
      val zSquared = WilsonZ * WilsonZ
      val center = share + zSquared / (2.0 * total)
      val margin = WilsonZ *
        math.sqrt(share * (1.0 - share) / total + zSquared / (4.0 * total * total))
      val scale = 1.0 + zSquared / total
      (math.max(0.0, (center - margin) / scale), math.min(1.0, (center + margin) / scale))
    }

  // Pull the mean of a small group toward the prior. The weight m acts as m extra rows.
  def smooth(sum: Double, n: Long, m: Double, prior: Double): Double =
    (sum + m * prior) / (n + m)
}
