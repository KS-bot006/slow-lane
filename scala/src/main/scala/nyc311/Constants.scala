package nyc311

object Constants {
  // The 11 columns in download order.
  val Columns: Vector[String] = Vector(
    "unique_key", "created_date", "closed_date", "status", "agency", "complaint_type",
    "descriptor", "location_type", "borough", "open_data_channel_type", "incident_zip"
  )
  val Header: String = Columns.mkString("\t")
  val FieldCount: Int = 11

  val Boroughs: Set[String] = Set("BRONX", "BROOKLYN", "MANHATTAN", "QUEENS", "STATEN ISLAND")
  val UnspecifiedBorough: String = "UNSPECIFIED"
  val UnknownText: String = "UNKNOWN"
  val ClosedStatus: String = "Closed"
  val SecondsPerDay: Double = 86400.0

  object RejectReason {
    val BadFieldCount: String = "bad_field_count"
    val MissingKey: String = "missing_key"
    val BadCreatedDate: String = "bad_created_date"
    val BadClosedDate: String = "bad_closed_date"
  }

  object DropReason {
    val OpenNoClosedDate: String = "open_no_closed_date"
    val StatusNotClosed: String = "status_not_closed"
    val OutsideYear: String = "outside_year"
    val ClosedBeforeCreated: String = "closed_before_created"
  }
}
