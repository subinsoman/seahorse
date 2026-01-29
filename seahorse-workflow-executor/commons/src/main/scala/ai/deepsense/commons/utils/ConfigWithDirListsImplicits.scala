package ai.deepsense.commons.utils

import java.io.File
import scala.collection.JavaConverters._

import com.typesafe.config.Config

object ConfigWithDirListsImplicits {

  implicit class ConfigWithDirLists(val config: Config) {
    def getDirList(path: String): Seq[File] = {
      config.getStringList(path).asScala
        .map(new File(_))
        .filter(_.isDirectory)
        .toSeq // Optional, ensures it's a Scala Seq
    }
  }
}

