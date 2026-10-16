package nyc311

object Keys {
  private val Separator = "\u001f"

  val Agency: String = "agency"
  val ComplaintType: String = "complaint_type"
  val Borough: String = "borough"
  val Zip: String = "zip"
  val AgencyType: String = "agency_type"
  val TypeBorough: String = "type_borough"
  val Hour: String = "hour"
  val DayOfWeek: String = "dow"
  val Month: String = "month"

  val AllGrains: Vector[String] =
    Vector(Agency, ComplaintType, Borough, Zip, AgencyType, TypeBorough, Hour, DayOfWeek, Month)

  // The column names of the group parts for each grain.
  val GroupColumns: Map[String, Vector[String]] = Map(
    Agency -> Vector("agency"),
    ComplaintType -> Vector("complaint_type"),
    Borough -> Vector("borough"),
    Zip -> Vector("zip"),
    AgencyType -> Vector("agency", "complaint_type"),
    TypeBorough -> Vector("complaint_type", "borough"),
    Hour -> Vector("hour"),
    DayOfWeek -> Vector("day_of_week"),
    Month -> Vector("month")
  )

  def build(grain: String, parts: Seq[String]): String = (grain +: parts).mkString(Separator)

  def parse(key: String): (String, Vector[String]) =
    key.split(Separator, -1).toVector match {
      case grain +: parts => (grain, parts)
      case _ => ("", Vector.empty)
    }

  def grainOf(key: String): String = parse(key)._1

  // One key for each grain of one clean row.
  def grainKeys(record: CleanRecord): Vector[String] =
    Vector(
      build(Agency, Seq(record.agency)),
      build(ComplaintType, Seq(record.complaintType)),
      build(Borough, Seq(record.borough)),
      build(Zip, Seq(record.zip)),
      build(AgencyType, Seq(record.agency, record.complaintType)),
      build(TypeBorough, Seq(record.complaintType, record.borough)),
      build(Hour, Seq(f"${record.hourOfDay}%02d")),
      build(DayOfWeek, Seq(record.dayOfWeek.toString)),
      build(Month, Seq(f"${record.created.getMonthValue}%02d"))
    )
}
