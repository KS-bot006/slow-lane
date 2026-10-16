package nyc311

object ThresholdRule {
  // Start with the default. Move to the smallest or largest candidate if the share is out of range.
  // If the chosen share is still out of range, give an error. The human must decide.
  def select(
      defaultDays: Int,
      candidates: Seq[Int],
      shareMin: Double,
      shareMax: Double,
      shares: Map[Int, Double]
  ): Either[String, Int] = {
    val defaultShare = shares.getOrElse(defaultDays, Double.NaN)
    val chosen =
      if (defaultShare < shareMin) candidates.min
      else if (defaultShare > shareMax) candidates.max
      else defaultDays
    val share = shares.getOrElse(chosen, Double.NaN)
    if (share >= shareMin && share <= shareMax) {
      Right(chosen)
    } else {
      Left(f"The slow share $share%.4f for $chosen days is outside $shareMin to $shareMax.")
    }
  }
}
