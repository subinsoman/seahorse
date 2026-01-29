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

package ai.deepsense.deeplang.doperables.spark.wrappers.transformers

import org.apache.spark.ml.feature.{OneHotEncoder => SparkOneHotEncoder, OneHotEncoderModel}
import org.apache.spark.ml.{Transformer, PipelineStage}
import org.apache.spark.ml.param.{Param, ParamMap}
import org.apache.spark.ml.util.{DefaultParamsWritable, Identifiable}
import org.apache.spark.sql.types.StructType
import org.apache.spark.sql.{DataFrame, Dataset}

import ai.deepsense.deeplang.doperables.SparkTransformerAsMultiColumnTransformer
import ai.deepsense.deeplang.params.Param
import ai.deepsense.deeplang.params.wrappers.spark.BooleanParamWrapper

// Wrapper to adapt Spark's OneHotEncoder to single-column interface
class SingleColumnOneHotEncoder(override val uid: String = Identifiable.randomUID("SingleColumnOneHotEncoder"))
  extends Transformer with DefaultParamsWritable {

  private var sparkEncoderModel: Option[OneHotEncoderModel] = None
  private val sparkEncoder = new SparkOneHotEncoder(uid)

  val inputCol = new org.apache.spark.ml.param.Param[String](this, "inputCol", "Input column name")
  val outputCol = new org.apache.spark.ml.param.Param[String](this, "outputCol", "Output column name")
  val dropLast = new org.apache.spark.ml.param.Param[Boolean](this, "dropLast", "Whether to drop the last category")

  def setInputCol(value: String): this.type = {
    sparkEncoder.setInputCols(Array(value))
    set(inputCol, value)
  }

  def setOutputCol(value: String): this.type = {
    sparkEncoder.setOutputCols(Array(value))
    set(outputCol, value)
  }

  def setDropLast(value: Boolean): this.type = {
    sparkEncoder.setDropLast(value)
    set(dropLast, value)
  }

  // Fit the encoder to a DataFrame to produce a model
  def fit(dataset: DataFrame): this.type = {
    sparkEncoderModel = Some(sparkEncoder.fit(dataset))
    this
  }

  override def transform(dataset: Dataset[_]): DataFrame = {
    if (sparkEncoderModel.isEmpty) {
      fit(dataset.toDF())
    }
    sparkEncoderModel.get.transform(dataset)
  }

  override def transformSchema(schema: StructType): StructType = {
    sparkEncoder.transformSchema(schema)
  }

  override def copy(extra: ParamMap): Transformer = {
    val copied = new SingleColumnOneHotEncoder(uid)
    copyValues(copied, extra)
    copied.sparkEncoder.setInputCols(sparkEncoder.getInputCols)
    copied.sparkEncoder.setOutputCols(sparkEncoder.getOutputCols)
    copied.sparkEncoder.setDropLast(sparkEncoder.getDropLast)
    copied.sparkEncoderModel = sparkEncoderModel
    copied
  }
}

class OneHotEncoder extends SparkTransformerAsMultiColumnTransformer[SingleColumnOneHotEncoder] {

  val dropLast = new BooleanParamWrapper[SingleColumnOneHotEncoder](
    name = "dropLast",
    description = Some("Whether to drop the last category in the encoded vector"),
    sparkParamGetter = (encoder: SingleColumnOneHotEncoder) => encoder.dropLast
  )
  setDefault(dropLast -> true)

  override protected def getSpecificParams: Array[ai.deepsense.deeplang.params.Param[_]] = Array(dropLast)
}
