// scalastyle:off println

import scala.sys.process._

val cleanWe = TaskKey[Unit]("cleanWe", "Execute clean in WE repo")

val shell = Seq("bash", "-c")

cleanWe := {
  Process(shell :+ "cd seahorse-workflow-executor && sbt clean").!
  ()
}

clean := (clean dependsOn cleanWe).value

// scalastyle:on
