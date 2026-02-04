import com.typesafe.sbt.SbtGit
import scala.sys.process._

enablePlugins(sbtdocker.DockerPlugin, JavaAppPackaging)

lazy val workflowExecutorProject = ProjectRef(file("./seahorse-workflow-executor"), "workflowexecutor")
lazy val assembly = taskKey[File]("Copied from sbt-assembly's keys.")
lazy val weJar = taskKey[File]("Workflow executor runnable jar")
weJar := (assembly in workflowExecutorProject).value

lazy val pythonAndRDeps = taskKey[File]("Generates we_deps.zip file with python and R dependencies")
pythonAndRDeps := {
  Process(Seq("sessionmanager/prepare-deps.sh", Version.spark)).!!
  target.value / "we-deps.zip"
}
pythonAndRDeps := (pythonAndRDeps dependsOn weJar).value

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
    runRaw("/opt/conda/bin/pip install py4j")
    runRaw("/opt/conda/bin/pip install mlxtend==0.22.0")
    runRaw("/opt/conda/bin/pip install scikit-learn")
    runRaw("/opt/conda/bin/pip install reportlab==3.6.5")
    /*runRaw(
      """/opt/conda/bin/pip install --no-cache-dir \
         pika==1.3.2 \
         py4j \
         mlxtend==0.22.0 \
         scikit-learn \
         reportlab==3.6.5"""
    )*/


    // Add Tini - so the python zombies can be collected
    env("TINI_VERSION", tiniVersion)
    addRaw(s"https://github.com/krallin/tini/releases/download/$tiniVersion/tini", "/bin/tini")
    runRaw("chmod +x /bin/tini")
    
    env("JDK_JAVA_OPTIONS", "--add-opens=java.base/java.nio=ALL-UNNAMED --add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/java.lang=ALL-UNNAMED --add-opens=java.base/java.util=ALL-UNNAMED -Dio.netty.tryReflectionSetAccessible=true")
    env("JAVA_OPTS", "--add-opens=java.base/java.nio=ALL-UNNAMED --add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/java.lang=ALL-UNNAMED --add-opens=java.base/java.util=ALL-UNNAMED -Dio.netty.tryReflectionSetAccessible=true")



    copy(pythonAndRDeps.value, "we-deps.zip")
    copy(weJar.value, "we.jar")
    //copy("/data/seahorse/mimepull-1.9.13.jar", "/opt/docker/app/lib/mimepull-1.9.13.jar")
    //copy(new File("sessionmanager/extra-lib/mimepull-1.9.13.jar"),"/opt/docker/app/lib/mimepull-1.9.13.jar")
    copy(sessionManagerAppDir, "app")

    entryPoint("/bin/tini", "--")
    cmd("app/bin/seahorse-sessionmanager")
  }
}
