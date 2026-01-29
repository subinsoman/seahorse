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

package ai.deepsense.deeplang.doperables

import org.apache.spark.sql.{DataFrame => SparkDataFrame}
import ai.deepsense.deeplang.ExecutionContext
import ai.deepsense.deeplang.OperationExecutionDispatcher.Result
import ai.deepsense.deeplang.doperables.dataframe.DataFrame
import ai.deepsense.deeplang.doperations.exceptions.CustomOperationExecutionException
import ai.deepsense.deeplang.params.CodeSnippetParam
import ai.deepsense.commons.utils.Logging

abstract class CustomCodeTransformer extends Transformer {
  val InputPortNumber: Int = 0
  val OutputPortNumber: Int = 0

  val codeParameter: CodeSnippetParam
  def getCodeParameter: String = $(codeParameter)
  def setCodeParameter(value: String): this.type = set(codeParameter, value)

  override val params: Array[ai.deepsense.deeplang.params.Param[_]] = Array(codeParameter)

  def isValid(context: ExecutionContext, code: String): Boolean

  def runCode(context: ExecutionContext, code: String): Result

  override def applyTransform(ctx: ExecutionContext, df: DataFrame): DataFrame = {
    val code = $(codeParameter)

    if (!isValid(ctx, code)) {
      throw CustomOperationExecutionException("Code validation failed")
    }

    ctx.dataFrameStorage.withInputDataFrame(InputPortNumber, df.sparkDataFrame) {
      logger.info("--->   :: In info log")
      logger.debug("--->   :: In debug log")
      runCode(ctx, code) match {
        case Left(error) =>
          throw CustomOperationExecutionException(s"Execution exception:\n\n$error")

        case Right(_) =>
          // Log details about the output DataFrame
          val outputDataFrameOption = ctx.dataFrameStorage.getOutputDataFrame(OutputPortNumber)
          logger.info(s"Output DataFrame option: $outputDataFrameOption")
          
          outputDataFrameOption match {
            case Some(sparkDataFrame) =>
              logger.info(s"Output DataFrame type: ${sparkDataFrame.getClass.getName}")
              logger.info(s"Output DataFrame schema: ${sparkDataFrame.schema}")
              val rowCount = sparkDataFrame.count()
              logger.info(s"Output DataFrame row count: $rowCount")
              if (rowCount == 0) {
                logger.warn("Output DataFrame is empty (0 rows)")
              }
              DataFrame.fromSparkDataFrame(sparkDataFrame)
            case None =>
              logger.error("No output DataFrame found in dataFrameStorage for OutputPortNumber: " + OutputPortNumber)
              throw CustomOperationExecutionException(
                "Operation finished successfully, but did not produce a DataFrame.")
          }
      }
    }
  }
}
