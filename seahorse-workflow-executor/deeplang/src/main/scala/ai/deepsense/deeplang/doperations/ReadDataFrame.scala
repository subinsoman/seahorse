/**
 * Copyright 2016 deepsense.ai (CodiLime, Inc)
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package ai.deepsense.deeplang.doperations

import java.io._
import java.net.UnknownHostException
import java.net.URLDecoder
import java.nio.charset.StandardCharsets

import scala.reflect.runtime.{universe => ru}
import org.apache.spark.sql.{DataFrame => SparkDataFrame}
import ai.deepsense.commons.utils.Version
import ai.deepsense.deeplang.DOperation.Id
import ai.deepsense.deeplang.documentation.OperationDocumentation
import ai.deepsense.deeplang.doperables.dataframe.DataFrame
import ai.deepsense.deeplang.doperations.ReadDataFrame.ReadDataFrameParameters
import ai.deepsense.deeplang.doperations.exceptions.{DeepSenseIOException, DeepSenseUnknownHostException}
import ai.deepsense.deeplang.doperations.inout._
import ai.deepsense.deeplang.doperations.readwritedataframe.filestorage.DataFrameFromFileReader
import ai.deepsense.deeplang.doperations.readwritedataframe.googlestorage.DataFrameFromGoogleSheetReader
import ai.deepsense.deeplang.doperations.readwritedataframe.validators.{FilePathHasValidFileScheme, ParquetSupportedOnClusterOnly}
import ai.deepsense.deeplang.inference.{InferContext, InferenceWarnings}
import ai.deepsense.deeplang.params.choice.ChoiceParam
import ai.deepsense.deeplang.params.{Param, Params}
import ai.deepsense.deeplang.{DKnowledge, DOperation0To1, ExecutionContext}

case class ReadDataFrame()
    extends DOperation0To1[DataFrame]
    with ReadDataFrameParameters
    with Params
    with OperationDocumentation {

  override val id: Id = "c48dd54c-6aef-42df-ad7a-42fc59a09f0e"
  override val name: String = "Read DataFrame"
  override val description: String =
    "Reads a DataFrame from a file or database"

  override val since: Version = Version(0, 4, 0)

  val specificParams: Array[Param[_]] = Array(storageType)
  setDefault(storageType, new InputStorageTypeChoice.File())

  override def execute()(context: ExecutionContext): DataFrame = {
    implicit val ec: ExecutionContext = context

    try {
      val dataframe = getStorageType() match {
        case jdbcChoice: InputStorageTypeChoice.Jdbc => readFromJdbc(jdbcChoice)
        case googleSheet: InputStorageTypeChoice.GoogleSheet =>
          DataFrameFromGoogleSheetReader.readFromGoogleSheet(googleSheet)
        case fileChoice: InputStorageTypeChoice.File =>
          DataFrameFromFileReader.readFromFile(fileChoice)
      }
      DataFrame.fromSparkDataFrame(dataframe)
    } catch {
      case e: UnknownHostException => throw DeepSenseUnknownHostException(e)
      case e: IOException => throw DeepSenseIOException(e)
    }
  }

  override def inferKnowledge()(context: InferContext): (DKnowledge[DataFrame], InferenceWarnings) = {
    FilePathHasValidFileScheme.validate(this)
    ParquetSupportedOnClusterOnly.validate(this)
    super.inferKnowledge()(context)
  }

  private def readFromJdbc(jdbcChoice: InputStorageTypeChoice.Jdbc)(implicit context: ExecutionContext): SparkDataFrame = {
    val jdbcUrl = jdbcChoice.getJdbcUrl

    // Function to extract query parameters from URL
    def extractQueryParam(url: String, param: String): Option[String] = {
      val decodedUrl = URLDecoder.decode(url, StandardCharsets.UTF_8.name())
      val queryParams = decodedUrl.split("\\?", 2).lift(1).getOrElse("")
      queryParams.split("&").collect {
        case s if s.startsWith(s"$param=") => s.split("=", 2).lift(1)
      }.flatten.headOption
    }

    // Extracting parameters with null as default value
    val partitionColumn = extractQueryParam(jdbcUrl, "partitionColumn").orNull
    val lowerBound = extractQueryParam(jdbcUrl, "lowerBound").orNull
    val upperBound = extractQueryParam(jdbcUrl, "upperBound").orNull
    val numPartitions = extractQueryParam(jdbcUrl, "numPartitions").orNull

    val reader = context.sparkSQLSession.read.format("jdbc")
      .option("driver", jdbcChoice.getJdbcDriverClassName) // Assuming there is a method to get the driver class name
      .option("url", jdbcUrl)
      .option("dbtable", jdbcChoice.getJdbcTableName)

    // Adding options conditionally based on the presence of parameters
    val readerWithPartitionColumn = if (partitionColumn != null) reader.option("partitionColumn", partitionColumn) else reader
    val readerWithLowerBound = if (lowerBound != null) readerWithPartitionColumn.option("lowerBound", lowerBound) else readerWithPartitionColumn
    val readerWithUpperBound = if (upperBound != null) readerWithLowerBound.option("upperBound", upperBound) else readerWithLowerBound
    val readerWithNumPartitions = if (numPartitions != null) readerWithUpperBound.option("numPartitions", numPartitions) else readerWithUpperBound

    readerWithNumPartitions.load()
  }

  @transient
  override lazy val tTagTO_0: ru.TypeTag[DataFrame] = ru.typeTag[DataFrame]
}

object ReadDataFrame {
  val recordDelimiterSettingName = "textinputformat.record.delimiter"

  trait ReadDataFrameParameters {
    this: Params =>

    val storageType = ChoiceParam[InputStorageTypeChoice](
      name = "data storage type",
      description = Some("Storage type.")
    )

    def getStorageType(): InputStorageTypeChoice = $(storageType)
    def setStorageType(value: InputStorageTypeChoice): this.type = set(storageType, value)
  }

  def apply(
      fileName: String,
      csvColumnSeparator: CsvParameters.ColumnSeparatorChoice,
      csvNamesIncluded: Boolean,
      csvConvertToBoolean: Boolean
  ): ReadDataFrame = {
    new ReadDataFrame()
      .setStorageType(
        new InputStorageTypeChoice.File()
          .setSourceFile(fileName)
          .setFileFormat(
            new InputFileFormatChoice.Csv()
              .setCsvColumnSeparator(csvColumnSeparator)
              .setNamesIncluded(csvNamesIncluded)
              .setShouldConvertToBoolean(csvConvertToBoolean)
          )
      )
  }
}
