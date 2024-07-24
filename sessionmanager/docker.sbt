import com.typesafe.sbt.SbtGit
enablePlugins(sbtdocker.DockerPlugin, JavaAppPackaging)

lazy val workflowExecutorProject = ProjectRef(file("./seahorse-workflow-executor"), "workflowexecutor")
lazy val assembly = taskKey[File]("Copied from sbt-assembly's keys.")
lazy val weJar = taskKey[File]("Workflow executor runnable jar")
weJar := (assembly in workflowExecutorProject).value

lazy val pythonAndRDeps = taskKey[File]("Generates we_deps.zip file with python and R dependencies")
pythonAndRDeps := {
  Seq("sessionmanager/prepare-deps.sh", Version.spark).!!
  target.value / "we-deps.zip"
}
pythonAndRDeps := (pythonAndRDeps dependsOn weJar.toTask).value

dockerBaseImage :=
  s"seahorse-spark:${SbtGit.GitKeys.gitHeadCommit.value.get}"

lazy val tiniVersion = "v0.10.0"

imageNames in docker := Seq(ImageName(s"seahorse-sessionmanager:${SbtGit.GitKeys.gitHeadCommit.value.get}"))

dockerfile in docker := {
  val sessionManagerAppDir = stage.value

  new Dockerfile {
    from(dockerBaseImage.value)

    user("root")
    workDir("/opt/docker")

    runRaw("/opt/conda/bin/pip install pika==1.3.2")

    // Add Tini - so the python zombies can be collected
    env("TINI_VERSION", tiniVersion)
    addRaw(s"https://github.com/krallin/tini/releases/download/$tiniVersion/tini", "/bin/tini")
    runRaw("chmod +x /bin/tini")

    copy(pythonAndRDeps.value, "we-deps.zip")
    copy(weJar.value, "we.jar")
    copy(sessionManagerAppDir, "app")

    entryPoint("/bin/tini", "--")
    cmd("app/bin/seahorse-sessionmanager")
  }
}
