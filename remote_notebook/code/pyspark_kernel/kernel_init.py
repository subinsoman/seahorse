# Copyright 2016 deepsense.ai (CodiLime, Inc)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

import os
import sys
import tempfile

from pyspark import SparkContext, SparkConf
from pyspark.sql import SQLContext, DataFrame
from py4j.java_gateway import JavaGateway, GatewayClient, java_import
from py4j.protocol import Py4JJavaError

# ------------------------------------------------------------------------------
# The kernel injects these:
#   gateway_address, gateway_port
#   workflow_id, node_id, port_number, dataframe_storage_type ('input' | 'output')
# ------------------------------------------------------------------------------

# Build a Py4J gateway to the already-running JVM
gateway = JavaGateway(
    GatewayClient(address=gateway_address, port=gateway_port),
    start_callback_server=False,
    auto_convert=True,
)

# Get existing Spark handles from the entry point
java_spark_context = gateway.entry_point.getSparkContext()
java_spark_conf = gateway.entry_point.getSparkConf()

# Helpful JVM imports
java_import(gateway.jvm, "org.apache.spark.SparkEnv")
java_import(gateway.jvm, "org.apache.spark.SparkConf")
java_import(gateway.jvm, "org.apache.spark.api.java.*")
java_import(gateway.jvm, "org.apache.spark.api.python.*")
java_import(gateway.jvm, "org.apache.spark.mllib.api.python.*")
java_import(gateway.jvm, "org.apache.spark.sql.*")
java_import(gateway.jvm, "org.apache.spark.sql.hive.*")
java_import(gateway.jvm, "scala.Tuple2")
java_import(gateway.jvm, "scala.collection.immutable.List")

# Some environments gate PySpark with an auth token; disable that path
os.environ["PYSPARK_GATEWAY_ENABLED"] = "1"

# ------------------------------------------------------------------------------
# Create a Python SparkContext wrapper around the existing JVM SparkContext
# ------------------------------------------------------------------------------
if SparkContext._active_spark_context is None:
    SparkContext._ensure_initialized(gateway=gateway)

    sc = object.__new__(SparkContext)
    sc._jsc = java_spark_context
    sc._jvm = gateway.jvm
    sc._gateway = gateway
    sc._conf = SparkConf(_jvm=gateway.jvm, _jconf=java_spark_conf)

    # Minimal serializer setup
    from pyspark.serializers import PickleSerializer, BatchedSerializer
    sc._batchSize = 1
    sc._unbatched_serializer = PickleSerializer()
    sc._serializer = BatchedSerializer(sc._unbatched_serializer, batchSize=sc._batchSize)
    sc.serializer = sc._serializer

    # Python exec/version
    sc.pythonExec = sys.executable
    sc._pythonExec = sys.executable
    sc.pythonVer = "%d.%d" % sys.version_info[:2]

    # Misc state expected by PySpark
    sc.environment = {}
    sc._pickled_broadcast_vars = []
    sc._encryption_enabled = False
    sc.master = sc._conf.get("spark.master", "unknown")
    sc._temp_dir = tempfile.mkdtemp(prefix="pyspark-")
    sc._python_includes = []
    sc._javaAccumulator = None
    sc.profiler_collector = None
    sc._profile_stats = []
    sc._next_rdd_id = 0
    sc._stopped = False
    sc._default_parallelism = None

    SparkContext._active_spark_context = sc
else:
    sc = SparkContext._active_spark_context

# ------------------------------------------------------------------------------
# SparkSession / SQLContext wrapping (bound to the same JVM session)
# ------------------------------------------------------------------------------
from pyspark.sql import SparkSession

# Get the JVM SparkSession from your entry point and wrap it
java_spark_sql_session = gateway.entry_point.getNewSparkSQLSession()
java_spark_session = java_spark_sql_session.getSparkSession()
spark = SparkSession(sc, jsparkSession=java_spark_session)

# Build a SQLContext that is explicitly tied to the *same* JVM SQLContext
java_sql_context = java_spark_session.sqlContext()
sqlContext = SQLContext(sc, sparkSession=spark, jsqlContext=java_sql_context)

# ------------------------------------------------------------------------------
# DataFrame helpers
# ------------------------------------------------------------------------------
def dataframe():
    """
    Retrieve a DataFrame from Seahorse storage via the JVM entry point and wrap it
    with a SQLContext (not SparkSession) so PySpark internals like .toPandas() work.
    """
    if node_id is None or port_number is None:
        raise Exception("No edge is connected to this Notebook")

    try:
        if dataframe_storage_type == "output":
            java_df = gateway.entry_point.retrieveOutputDataFrame(workflow_id, node_id, port_number)
        else:
            assert dataframe_storage_type == "input"
            java_df = gateway.entry_point.retrieveInputDataFrame(workflow_id, node_id, port_number)
    except Py4JJavaError:
        raise Exception("Input operation is not yet executed")

    # IMPORTANT: pass a SQLContext here (DataFrame.toPandas expects df.sql_ctx._conf)
    return DataFrame(jdf=java_df, sql_ctx=sqlContext)


def move_to_local_sqlContext(df):
    """
    If you need to 'detach' df from its original plan, recreate it via a temp view.
    Use the same session that owns df, materialize, then drop the view.
    """
    import uuid
    temp_view = "temp_view_" + uuid.uuid4().hex

    # Register view on df's own session
    df.createOrReplaceTempView(temp_view)

    # Use the session tied to this DF/SQLContext
    # SQLContext in Spark 3 exposes .sparkSession
    sess = getattr(df.sql_ctx, "sparkSession", spark)

    # Query with the same session/catalog and materialize before dropping the view
    result_df = sess.sql(f"SELECT * FROM `{temp_view}`").cache()
    _ = result_df.count()
    try:
        sess.catalog.dropTempView(temp_view)
    except Exception:
        pass

    return result_df

# ------------------------------------------------------------------------------
# Example:
# df = dataframe()
# pdf = move_to_local_sqlContext(df).toPandas()
# ------------------------------------------------------------------------------

