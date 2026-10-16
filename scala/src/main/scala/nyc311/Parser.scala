package nyc311

import java.time.LocalDateTime
import scala.util.Try

object Parser {
  import Constants.RejectReason

  // Turn one tab separated line into a Request, or give the reject reason.
  def parseLine(line: String): Either[String, Request] = {
    val fields = line.split("\t", -1)
    if (fields.length != Constants.FieldCount) {
      Left(RejectReason.BadFieldCount)
    } else if (fields(0).trim.isEmpty) {
      Left(RejectReason.MissingKey)
    } else {
      for {
        created <- parseTime(fields(1)).toRight(RejectReason.BadCreatedDate)
        closed <- parseClosed(fields(2))
      } yield Request(
        uniqueKey = fields(0).trim,
        created = created,
        closed = closed,
        status = textOrUnknown(fields(3)),
        agency = textOrUnknown(fields(4)),
        complaintType = textOrUnknown(fields(5)),
        descriptor = textOrUnknown(fields(6)),
        locationType = textOrUnknown(fields(7)),
        borough = textOrUnknown(fields(8)),
        channel = textOrUnknown(fields(9)),
        zip = textOrUnknown(fields(10))
      )
    }
  }

  private def parseTime(text: String): Option[LocalDateTime] =
    Try(LocalDateTime.parse(text.trim)).toOption

  private def parseClosed(text: String): Either[String, Option[LocalDateTime]] =
    if (text.trim.isEmpty) {
      Right(None)
    } else {
      parseTime(text) match {
        case Some(time) => Right(Some(time))
        case None => Left(RejectReason.BadClosedDate)
      }
    }

  private def textOrUnknown(text: String): String = {
    val trimmed = text.trim
    if (trimmed.isEmpty) Constants.UnknownText else trimmed
  }
}
