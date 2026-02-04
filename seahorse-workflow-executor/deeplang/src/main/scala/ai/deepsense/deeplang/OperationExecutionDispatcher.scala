/**
 * Copyright 2015 deepsense.ai (CodiLime, Inc)
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

package ai.deepsense.deeplang

import scala.collection.concurrent.TrieMap
import scala.concurrent.{Future, Promise}

import ai.deepsense.commons.models.Id
import ai.deepsense.commons.utils.Logging

class OperationExecutionDispatcher extends Logging {

  import OperationExecutionDispatcher._

  private val operationEndPromises: TrieMap[OperationId, Promise[Result]] = TrieMap.empty

  def executionStarted(workflowId: Id, nodeId: Id): Future[Result] = {
    logger.debug(s"${workflowId}_${nodeId}-Execution started in dispatcher")
    val promise: Promise[Result] = Promise()
    require(operationEndPromises.put((workflowId, nodeId), promise).isEmpty)
    promise.future
  }

  def executionEnded(workflowId: Id, nodeId: Id, result: Result): Unit = {
    logger.debug(s"${workflowId}_${nodeId}-Execution ended in dispatcher with result: $result")
    val promise = operationEndPromises.remove((workflowId, nodeId))
    require(promise.isDefined)
    promise.get.success(result)
  }

  def failAllPending(reason: String): Unit = {
    operationEndPromises.foreach { case (key, promise) =>
      promise.failure(new RuntimeException(reason))
    }
    operationEndPromises.clear()
  }
}

object OperationExecutionDispatcher {
  type OperationId = (Id, Id)
  type Error = String
  type Result = Either[Error, Unit]
}
