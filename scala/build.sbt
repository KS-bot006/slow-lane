ThisBuild / scalaVersion := "2.12.18"
ThisBuild / version      := "1.0.0"
ThisBuild / organization := "nyc311"

lazy val root = (project in file("."))
  .settings(
    name := "nyc311-resolution-time",
    libraryDependencies ++= Seq(
      "org.apache.spark" %% "spark-core" % "3.5.9"  % Provided,
      "org.apache.spark" %% "spark-sql"  % "3.5.9"  % Provided,
      "org.scalatest"    %% "scalatest"  % "3.2.18" % Test
    ),
    scalacOptions ++= Seq("-deprecation", "-feature", "-unchecked", "-Xlint")
  )
