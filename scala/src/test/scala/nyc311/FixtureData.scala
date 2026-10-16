package nyc311

// Fixture values for the unit tests. No job reads them.
object FixtureData {
  val ValidLine: String =
    "1001\t2025-03-01T10:15:30.000\t2025-03-02T10:15:30.000\tClosed\tNYPD\tNoise - Street" +
      "\tLoud Music\tStreet/Sidewalk\tBROOKLYN\tPHONE\t11201"

  val ConfigText: String =
    """year=2025
      |history_start=2025-01-01
      |history_end=2025-06-30
      |train_start=2025-07-01
      |train_end=2025-09-30
      |test_start=2025-10-01
      |test_end=2025-12-31
      |default_threshold_days=3
      |candidate_threshold_days=1,3,7
      |share_min=0.10
      |share_max=0.50
      |min_group_size=500
      |top_descriptors=100
      |top_location_types=30
      |smoothing_m=20
      |spark_master=local[*]
      |spark_driver_memory=4g
      |rf_num_trees=60
      |rf_max_depth=10
      |rf_subsampling_rate=0.5
      |rf_min_instances_per_node=20
      |lr_max_iter=50
      |seed=42
      |""".stripMargin

  def config: Config = Config.fromMap(Config.parseProperties(ConfigText)) match {
    case Right(value) => value
    case Left(message) => throw new IllegalStateException(message)
  }

  // Read the value of a Right. A Left stops the test with its message.
  implicit class EitherValue[A](either: Either[String, A]) {
    def value: A = either match {
      case Right(result) => result
      case Left(message) => throw new IllegalStateException(message)
    }
  }

  def lineWith(replacements: Map[Int, String]): String =
    ValidLine.split("\t", -1).zipWithIndex
      .map { case (value, index) => replacements.getOrElse(index, value) }
      .mkString("\t")
}
