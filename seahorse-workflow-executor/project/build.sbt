// IMPORTANT: This version MUST be kept in sync with swagger codegen version used in
// Scalatra Codegen, otherwise different code will be produced depending on where sbt is run from
libraryDependencies += "io.swagger" % "swagger-codegen" % "2.2.0"

/*
libraryDependencies ++= Seq(
  "io.swagger" % "swagger-codegen" % "2.4.21",
  "io.swagger" % "swagger-parser"  % "1.0.56"
)
*/

//resolvers += "Sonatype OSS Releases" at "https://oss.sonatype.org/content/repositories/releases"
//libraryDependencies += "io.swagger" % "swagger-codegen" % "2.4.19"
//libraryDependencies += "org.scala-lang.modules" %% "scala-xml" % "2.3.0"

ThisBuild / libraryDependencySchemes += "org.scala-lang.modules" %% "scala-xml" % "early-semver"


libraryDependencies ++= Seq(
  "org.scoverage" %% "scalac-scoverage-reporter" % "2.3.0" exclude("org.scala-lang.modules", "scala-xml_2.12"),
  "org.scalariform" %% "scalariform" % "0.2.0",
  "org.scala-lang.modules" %% "scala-xml" % "1.0.6" // or 1.0.6
)
// https://mvnrepository.com/artifact/org.threeten/threetenbp
//libraryDependencies += "org.threeten" % "threetenbp" % "1.4.1"
