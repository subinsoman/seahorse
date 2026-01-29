// Copyright (c) 2015, CodiLime Inc.

resolvers ++= Seq(
  Classpaths.sbtPluginReleases,
  "sonatype-releases" at "https://oss.sonatype.org/content/repositories/releases/",
  "sonatype-public" at "https://oss.sonatype.org/content/groups/public/"
)

dependencyOverrides += "org.scala-lang.modules" %% "scala-xml" % "2.1.0"

addSbtPlugin("org.scoverage" % "sbt-scoverage" % "2.3.1")

// Comment out if not needed or causing issues
 addSbtPlugin("org.scalastyle" %% "scalastyle-sbt-plugin" % "1.0.0")

addSbtPlugin("io.spray" % "sbt-revolver" % "0.10.0")

addSbtPlugin("com.eed3si9n" % "sbt-buildinfo" % "0.13.1")

addSbtPlugin("com.github.sbt" % "sbt-native-packager" % "1.9.10")

addSbtPlugin("com.github.sbt" % "sbt-release" % "1.2.0")

addSbtPlugin("com.typesafe.sbt" % "sbt-git" % "1.0.1")
//addSbtPlugin("com.github.sbt" % "sbt-git" % "2.3.0")

// Comment out if not needed
addSbtPlugin("ai.deepsense" % "scalatra-swagger-codegen" % "1.7")

addSbtPlugin("se.marcuslonnberg" % "sbt-docker" % "1.9.0")

addSbtPlugin("com.geirsson" % "sbt-scalafmt" % "1.5.1")

addSbtPlugin("net.virtual-void" % "sbt-dependency-graph" % "0.9.0")
