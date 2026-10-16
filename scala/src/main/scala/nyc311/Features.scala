package nyc311

import java.time.format.DateTimeFormatter

// History tables and sets that the workers need. All values come from the history window.
final case class HistoryTables(
    h1: Map[String, Agg],
    h2: Map[String, Agg],
    h3: Map[String, Agg],
    overall: Agg,
    topDescriptors: Set[String],
    topLocationTypes: Set[String],
    smoothingM: Double,
    thresholdDays: Double
)

final case class FeatureRow(
    uniqueKey: String,
    window: String,
    createdDate: String,
    label: Double,
    durationDays: Double,
    agency: String,
    complaintType: String,
    descriptorG: String,
    locationTypeG: String,
    borough: String,
    channel: String,
    zip: String,
    hour: Int,
    dow: Int,
    isWeekend: Int,
    history: Vector[Double]
)

object Features {
  val Other: String = "OTHER"
  val H1: String = "h1"
  val H2: String = "h2"
  val H3: String = "h3"
  val HistoryKeys: Vector[String] = Vector(H1, H2, H3)
  private val FirstWeekendDay = 6
  private val IsoSeconds = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss")

  // Agency, complaint type, and descriptor.
  def h1Key(record: CleanRecord): String =
    Keys.build(H1, Seq(record.agency, record.complaintType, record.descriptor))

  // Complaint type and borough.
  def h2Key(record: CleanRecord): String =
    Keys.build(H2, Seq(record.complaintType, record.borough))

  // ZIP code.
  def h3Key(record: CleanRecord): String = Keys.build(H3, Seq(record.zip))

  def keysOf(record: CleanRecord): Vector[(String, String)] =
    Vector((H1, h1Key(record)), (H2, h2Key(record)), (H3, h3Key(record)))

  def hasHistory(name: String, key: String, tables: HistoryTables): Boolean =
    tableOf(name, tables).contains(key)

  // The label is 1.0 only when the duration is strictly above the threshold.
  def label(durationDays: Double, thresholdDays: Double): Double =
    if (durationDays > thresholdDays) 1.0 else 0.0

  def isWeekend(dayOfWeek: Int): Int = if (dayOfWeek >= FirstWeekendDay) 1 else 0

  def group(value: String, allowed: Set[String]): String =
    if (allowed.contains(value)) value else Other

  // Smoothed slow rate, smoothed mean of ln(1 + days), and ln(1 + n). A missing key has n = 0.
  def historyTriple(found: Option[Agg], overall: Agg, smoothingM: Double): Vector[Double] = {
    val agg = found.getOrElse(Stats.zero)
    val priorSlow = overall.slowCount.toDouble / overall.n
    val priorLog = overall.sumLogDays / overall.n
    Vector(
      Stats.smooth(agg.slowCount.toDouble, agg.n, smoothingM, priorSlow),
      Stats.smooth(agg.sumLogDays, agg.n, smoothingM, priorLog),
      math.log1p(agg.n.toDouble)
    )
  }

  def build(record: CleanRecord, window: String, tables: HistoryTables): FeatureRow = {
    val history = Vector(
      tables.h1.get(h1Key(record)),
      tables.h2.get(h2Key(record)),
      tables.h3.get(h3Key(record))
    ).flatMap(found => historyTriple(found, tables.overall, tables.smoothingM))
    FeatureRow(
      uniqueKey = record.uniqueKey,
      window = window,
      createdDate = record.created.format(IsoSeconds),
      label = label(record.durationDays, tables.thresholdDays),
      durationDays = record.durationDays,
      agency = record.agency,
      complaintType = record.complaintType,
      descriptorG = group(record.descriptor, tables.topDescriptors),
      locationTypeG = group(record.locationType, tables.topLocationTypes),
      borough = record.borough,
      channel = record.channel,
      zip = record.zip,
      hour = record.hourOfDay,
      dow = record.dayOfWeek,
      isWeekend = isWeekend(record.dayOfWeek),
      history = history
    )
  }

  private def tableOf(name: String, tables: HistoryTables): Map[String, Agg] =
    name match {
      case H1 => tables.h1
      case H2 => tables.h2
      case _ => tables.h3
    }
}
