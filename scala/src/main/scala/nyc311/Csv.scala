package nyc311

import java.nio.charset.StandardCharsets
import java.nio.file.{Files, Paths}

object Csv {
  private val LineBreak = "\n"

  // Quote a value that has a comma, a quote, or a line break.
  def escape(value: String): String =
    if (value.exists(character => character == ',' || character == '"' ||
        character == '\n' || character == '\r')) {
      "\"" + value.replace("\"", "\"\"") + "\""
    } else {
      value
    }

  def line(values: Seq[Any]): String = values.map(value => escape(value.toString)).mkString(",")

  // Write a UTF-8 file with a header. Missing folders are created.
  def write(path: String, header: Seq[String], rows: Seq[Seq[Any]]): Unit = {
    val text = (line(header) +: rows.map(line)).mkString("", LineBreak, LineBreak)
    val target = Paths.get(path)
    Option(target.getParent).foreach(parent => Files.createDirectories(parent))
    Files.write(target, text.getBytes(StandardCharsets.UTF_8))
    ()
  }
}
