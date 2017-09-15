/**
 * Copyright 2016, deepsense.io
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

package io.deepsense.deeplang.doperations

import scala.reflect.runtime.universe.TypeTag

import io.deepsense.commons.utils.Version
import io.deepsense.deeplang.DOperation.Id
import io.deepsense.deeplang.documentation.OperationDocumentation
import io.deepsense.deeplang.doperables.PythonEvaluator

class CreatePythonEvaluator
  extends EvaluatorAsFactory[PythonEvaluator] with OperationDocumentation  {

  override val id: Id = "582748ff-b1e4-4821-94da-d6c411e76e7e"
  override val name: String = "Python Evaluator"
  override val description: String =
    "Creates a Python Evaluator"

  override val since: Version = Version(1, 2, 0)
}
