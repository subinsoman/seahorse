/**
 * Copyright 2018 Astraea, Inc.
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
package ai.deepsense.deeplang.catalogs.spi

import java.util.ServiceLoader

import scala.collection.JavaConverters._

trait CatalogRegistrant {
  def register(registrar: CatalogRegistrar): Unit
}

object CatalogRegistrant {
  private[deeplang] def load(registrar: CatalogRegistrar, loader: ClassLoader): Unit = {
    val registrants = ServiceLoader.load(classOf[CatalogRegistrant], loader).iterator().asScala.toSeq
    for (r <- registrants) {
      r.register(registrar)
    }
  }
}

