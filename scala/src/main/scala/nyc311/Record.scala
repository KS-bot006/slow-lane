package nyc311

import java.time.LocalDateTime

// One parsed line. Empty text fields hold UNKNOWN. An empty closed date holds None.
final case class Request(
    uniqueKey: String,
    created: LocalDateTime,
    closed: Option[LocalDateTime],
    status: String,
    agency: String,
    complaintType: String,
    descriptor: String,
    locationType: String,
    borough: String,
    channel: String,
    zip: String
)

// One request that passed the cleaning rules. The duration is in days.
final case class CleanRecord(
    uniqueKey: String,
    created: LocalDateTime,
    closed: LocalDateTime,
    status: String,
    agency: String,
    complaintType: String,
    descriptor: String,
    locationType: String,
    borough: String,
    channel: String,
    zip: String,
    durationDays: Double,
    hourOfDay: Int,
    dayOfWeek: Int
)
