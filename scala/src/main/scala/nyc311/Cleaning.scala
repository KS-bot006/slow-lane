package nyc311

import java.time.Duration
import java.util.Locale

object Cleaning {
  import Constants.DropReason

  private val ZipPattern = "^\\d{5}(-\\d{4})?$".r
  private val ZipDigits = 5
  private val SecondsPerHour = 3600.0

  // Apply the drop rules in order. The first failed rule gives the drop reason.
  def classify(request: Request, year: Int): Either[String, CleanRecord] =
    request.closed match {
      case None => Left(DropReason.OpenNoClosedDate)
      case Some(closed) =>
        if (!request.status.equalsIgnoreCase(Constants.ClosedStatus)) {
          Left(DropReason.StatusNotClosed)
        } else if (request.created.getYear != year) {
          Left(DropReason.OutsideYear)
        } else if (closed.isBefore(request.created)) {
          Left(DropReason.ClosedBeforeCreated)
        } else {
          Right(normalize(request, closed))
        }
    }

  def normalizeBorough(text: String): String = {
    val value = text.trim.toUpperCase(Locale.ROOT)
    if (Constants.Boroughs.contains(value)) value else Constants.UnspecifiedBorough
  }

  def normalizeZip(text: String): String = {
    val value = text.trim
    if (ZipPattern.pattern.matcher(value).matches()) value.take(ZipDigits)
    else Constants.UnknownText
  }

  // Bucket 0 holds durations under 1 hour. Bucket b holds hours from 2^(b-1) up to 2^b.
  def durationBucket(durationDays: Double): Int = {
    val hours = durationDays * Constants.SecondsPerDay / SecondsPerHour
    if (hours < 1.0) 0 else java.lang.Long.SIZE - java.lang.Long.numberOfLeadingZeros(hours.toLong)
  }

  private def upper(text: String): String = text.toUpperCase(Locale.ROOT)

  private def normalize(request: Request, closed: java.time.LocalDateTime): CleanRecord = {
    val seconds = Duration.between(request.created, closed).getSeconds
    CleanRecord(
      uniqueKey = request.uniqueKey,
      created = request.created,
      closed = closed,
      status = request.status,
      agency = upper(request.agency),
      complaintType = upper(request.complaintType),
      descriptor = upper(request.descriptor),
      locationType = upper(request.locationType),
      borough = normalizeBorough(request.borough),
      channel = upper(request.channel),
      zip = normalizeZip(request.zip),
      durationDays = seconds / Constants.SecondsPerDay,
      hourOfDay = request.created.getHour,
      dayOfWeek = request.created.getDayOfWeek.getValue
    )
  }
}
