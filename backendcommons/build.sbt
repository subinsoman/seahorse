/**
 * Copyright (c) 2015, CodiLime Inc.
 */

import scala.sys.process._
import sbtbuildinfo.BuildInfoPlugin.autoImport._

name := "seahorse-commons"

libraryDependencies ++= Dependencies.commons
resolvers ++= Dependencies.resolvers
//resolvers += Resolver.mavenLocal
resolvers += "Local Maven Repository" at "file:///home/admin/.m2/repository"

Revolver.settings

Test / testOptions := Seq(
  Tests.Filter(unitFilter),
  // Put results in target/test-reports
  Tests.Argument(TestFrameworks.ScalaTest, "-o", "-u", "target/test-reports")
)
Test / fork := true
Test / javaOptions := Seq("-Denv=test", s"-DlogFile=${name.value}")
Test / unmanagedClasspath += baseDirectory.value / "conf"
Test / scalacOptions := Seq(
  "-unchecked", "-deprecation", "-encoding", "utf8",
  "-feature", "-language:existentials"
)

Runtime / unmanagedClasspath += baseDirectory.value / "conf"

lazy val IntegTest = config("it") extend Test
configs(IntegTest)

IntegTest / testOptions := Seq(
  Tests.Filter(integFilter),
  // Show full stacktraces (F), Put results in target/test-reports
  Tests.Argument(TestFrameworks.ScalaTest, "-oF", "-u", "target/test-reports")
)
IntegTest / javaOptions := Seq("-Denv=integtest", s"-DlogFile=${name.value}")
IntegTest / fork := true

def integFilter(name: String) = name.endsWith("IntegSpec")
def unitFilter(name: String) = name.endsWith("Spec") && !integFilter(name)

enablePlugins(BuildInfoPlugin)

buildInfoPackage := "ai.deepsense.commons.buildinfo"

buildInfoKeys ++= {
  val slices = 3
  val splitRegex = """[^\d]"""
  val versionSeparator = "."
  lazy val versionSplit: Seq[Int] = {
    val split = version.value.split(splitRegex)
      .filter(_.nonEmpty).map(_.toInt)
    assert(split.length >= slices, assertionMessage)
    val apiVersion = split.take(slices).mkString(versionSeparator)
    assert(version.value.startsWith(apiVersion), assertionMessage)
    split
  }

  lazy val assertionMessage = s"Version is set to '${version.value}' but should be in a format" +
    " X.Y.Z, where X and Y are non negative integers!"

  Seq[BuildInfoKey](
    BuildInfoKey.action("gitCommitId") {
      Process("git rev-parse HEAD").!!.trim
    },
    BuildInfoKey.action("apiVersionMajor") {
      versionSplit.head
    },
    BuildInfoKey.action("apiVersionMinor") {
      versionSplit(1)
    },
    BuildInfoKey.action("apiVersionPatch") {
      versionSplit(2)
    },
    BuildInfoKey("sparkVersion" -> Version.spark),
    BuildInfoKey("hadoopVersion" -> Version.hadoop)
  )
}
