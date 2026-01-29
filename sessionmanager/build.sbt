// Copyright (c) 2016, CodiLime Inc.

// scalastyle:off println

import com.typesafe.sbt.SbtGit
import com.typesafe.sbt.packager.docker._

//import com.github.sbt.SbtGit
//import com.github.sbt.packager.docker._

import sbt.ProjectRef

name := "seahorse-sessionmanager"

libraryDependencies ++= Dependencies.sessionmanager
resolvers ++= Dependencies.resolvers

libraryDependencies += "org.jvnet" % "mimepull" % "1.6"

Revolver.settings

enablePlugins(JavaAppPackaging, GitVersioning, DeepsenseUniversalSettingsPlugin)

// If there are many `App` objects in project, docker image will crash with cryptic message
mainClass in Compile := Some("ai.deepsense.sessionmanager.SessionManagerApp")

// scalastyle:on
