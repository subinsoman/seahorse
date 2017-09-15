/**
 * Copyright (c) 2015, CodiLime Inc.
 */

package io.deepsense.deeplang.doperations.transformations

import io.deepsense.deeplang.ExecutionContext
import io.deepsense.deeplang.doperables.dataframe.DataFrame
import io.deepsense.deeplang.doperables.{Report, Transformation}
import io.deepsense.deeplang.doperations.exceptions.MathematicalOperationExecutionException
import io.deepsense.reportlib.model.ReportContent

class MathematicalTransformation(formula: Option[String]) extends Transformation {

  def this() = this(None)

  override def transform(dataFrame: DataFrame): DataFrame = {
    try {
      DataFrame(dataFrame.sparkDataFrame.selectExpr("*", formula.get))
    } catch {
      case e: Exception => throw new MathematicalOperationExecutionException(formula.get, Some(e))
    }
  }

  override def report: Report = Report(ReportContent("Report for MathematicalTransformation.\n" +
    s"Formula: $formula"))

  override def save(executionContext: ExecutionContext)(path: String): Unit = ???
}
