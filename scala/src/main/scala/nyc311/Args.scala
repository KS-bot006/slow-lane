package nyc311

object Args {
  // Turn "--key value" pairs into a Map. A key without a value gives an error message.
  def parse(args: Seq[String]): Either[String, Map[String, String]] = {
    @scala.annotation.tailrec
    def loop(rest: List[String], found: Map[String, String]): Either[String, Map[String, String]] =
      rest match {
        case Nil => Right(found)
        case key :: value :: tail if key.startsWith("--") && !value.startsWith("--") =>
          loop(tail, found + (key.drop(2) -> value))
        case key :: _ if key.startsWith("--") => Left(s"Argument $key has no value.")
        case other :: _ => Left(s"Unexpected argument '$other'. Use the form --key value.")
      }
    loop(args.toList, Map.empty)
  }
}
