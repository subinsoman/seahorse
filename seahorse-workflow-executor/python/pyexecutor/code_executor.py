# Copyright 2015 deepsense.ai (CodiLime, Inc)
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
# See the License for the specific language governing permissions and
# limitations under the License.


import ast
import sys
import traceback
from pyspark.sql import SparkSession
from pyspark.sql.dataframe import DataFrame
from pyspark.sql.types import *
from threading import Thread
from simple_logging import log_debug, log_error

class CodeExecutor(object):
    """
    This class handles code execution requests from Session Executor.
    """

    TRANSFORM_FUNCTION_NAME = 'transform'
    TRANSFORM_FUNCTION_ARITIES = [1]

    INPUT_PORT_NUMBER = 0
    OUTPUT_PORT_NUMBER = 0

    def __init__(self, spark_context, spark_session, entry_point):
        self.entry_point = entry_point
        self.spark_context = spark_context
        self.spark_session = spark_session  # This is now a SparkSession instead of spark_sql_session

        self.threads = []

    def run(self, workflow_id, node_id, custom_operation_code):
        log_debug(f"{workflow_id}_{node_id}-Starting execution thread")
        executor_thread = Thread(
            target=lambda: self._supervised_execution(workflow_id, node_id, custom_operation_code),
            name='Supervisor {}'.format(node_id))

        self.threads.append(executor_thread)

        executor_thread.daemon = True
        executor_thread.start()

    def _supervised_execution(self, workflow_id, node_id, custom_operation_code):
        # noinspection PyBroadException
        try:

            log_debug(f"{workflow_id}_{node_id}-python tranformation job exicution starts-Beginning supervised execution")
            self._run_custom_code(workflow_id, node_id, custom_operation_code)
            self.entry_point.executionCompleted(workflow_id, node_id)
            log_debug(f"{workflow_id}_{node_id}-python tranformation job exicution completed successfully")
        except Exception as e:
            stacktrace = traceback.format_exc()
            log_error(f"{workflow_id}_{node_id}-Execution failed: {str(e)}\\n{stacktrace}")
            self.entry_point.executionFailed(workflow_id, node_id, stacktrace)

    def _convert_data_to_data_frame(self, data_wrapper, workflow_id, node_id):
        """
        Accepts a list wrapper [data] to allow clearing the caller's reference.
        """
        spark_session = self.spark_session
        
        # Extract data from wrapper
        data = data_wrapper[0]
        
        log_debug(f"{workflow_id}_{node_id}-Converting data of type {type(data)} to DataFrame")
        
        try:
            import pandas
            self.is_pandas_available = True
            log_debug(f"{workflow_id}_{node_id}-Pandas is available")
        except ImportError:
            self.is_pandas_available = False
            log_debug(f"{workflow_id}_{node_id}-Pandas is not available")
            
        if isinstance(data, DataFrame):
            log_debug(f"{workflow_id}_{node_id}-Data is already a DataFrame")
            return data
        elif self.is_pandas_available and isinstance(data, pandas.DataFrame):
            return self._pandas_to_spark_arrow(data, data_wrapper, workflow_id, node_id)

        elif isinstance(data, (list, tuple)) and all(isinstance(el, (list, tuple)) for el in data):
            log_debug(f"{workflow_id}_{node_id}-Converting list of lists/tuples to DataFrame")
            return spark_session.createDataFrame(data)
        elif isinstance(data, (list, tuple)):
            log_debug(f"{workflow_id}_{node_id}-Converting list/tuple to DataFrame")
            # Convert to single-element tuples
            rows = [(x,) for x in data]
            return spark_session.createDataFrame(rows)
        else:
            log_debug(f"{workflow_id}_{node_id}-Converting single value to DataFrame")
            return spark_session.createDataFrame([(data,)])

    def _pandas_to_spark_arrow(self, data, data_wrapper, workflow_id, node_id):
        """
        Converts a Pandas DataFrame to a Spark DataFrame using Arrow optimization.
        This is the most efficient approach for Pandas-to-Spark conversion.
        """
        import time
        
        start_time = time.time()
        spark_session = self.spark_session
        
        # Capture schema if attached
        schema = getattr(data, "_spark_schema", None)
        
        # Calculate input metrics
        total_rows = len(data)
        total_cols = len(data.columns)
        memory_mb = data.memory_usage(deep=True).sum() / 1024 / 1024
        
        log_debug(f"{workflow_id}_{node_id}-========== Pandas to Spark Conversion ==========")
        log_debug(f"{workflow_id}_{node_id}-Input: {total_rows:,} rows × {total_cols} cols (~{memory_mb:.1f} MB)")
        if schema:
            log_debug(f"{workflow_id}_{node_id}-Using attached _spark_schema")

        try:
            # Step 1: Configure Arrow
            log_debug(f"{workflow_id}_{node_id}-[Step 1/5] Configuring Arrow optimization...")
            spark_session.conf.set("spark.sql.execution.arrow.pyspark.enabled", "true")
            spark_session.conf.set("spark.sql.execution.arrow.pyspark.fallback.enabled", "true")  # Enable fallback
            spark_session.conf.set("spark.sql.execution.arrow.maxRecordsPerBatch", "10000")
            
            # Step 2: Create DataFrame
            log_debug(f"{workflow_id}_{node_id}-[Step 2/5] Creating Spark DataFrame with Arrow...")
            create_start = time.time()
            result = spark_session.createDataFrame(data, schema=schema)
            create_time = time.time() - create_start
            log_debug(f"{workflow_id}_{node_id}-[Step 2/5] DataFrame created in {create_time:.2f}s")
            
            # Step 3: Repartition for better parallelism
            num_partitions = max(1, total_rows // 1000000)  # ~1M rows per partition
            if num_partitions > 1:
                log_debug(f"{workflow_id}_{node_id}-[Step 3/5] Repartitioning to {num_partitions} partitions...")
                repartition_start = time.time()
                result = result.repartition(num_partitions)
                repartition_time = time.time() - repartition_start
                log_debug(f"{workflow_id}_{node_id}-[Step 3/5] Repartitioned in {repartition_time:.2f}s")
            else:
                log_debug(f"{workflow_id}_{node_id}-[Step 3/5] Skipping repartition (single partition)")
            
            # Step 4: Cache the DataFrame
            log_debug(f"{workflow_id}_{node_id}-[Step 4/5] Caching DataFrame...")
            result = result.cache()
            
            # Step 5: Materialize and count
            log_debug(f"{workflow_id}_{node_id}-[Step 5/5] Materializing and counting rows...")
            count_start = time.time()
            row_count = result.count()  # Triggers Spark job, visible in UI
            count_time = time.time() - count_start
            log_debug(f"{workflow_id}_{node_id}-[Step 5/5] Counted {row_count:,} rows in {count_time:.2f}s")
            
            # Calculate final metrics
            total_time = time.time() - start_time
            throughput = row_count / total_time if total_time > 0 else 0
            
            log_debug(f"{workflow_id}_{node_id}-========== Conversion Complete ==========")
            log_debug(f"{workflow_id}_{node_id}-✓ Total time: {total_time:.2f}s")
            log_debug(f"{workflow_id}_{node_id}-✓ Throughput: {throughput:,.0f} rows/sec")
            log_debug(f"{workflow_id}_{node_id}-✓ Create time: {create_time:.2f}s, Count time: {count_time:.2f}s")
            log_debug(f"{workflow_id}_{node_id}-=============================================")
            
            # Cleanup driver memory after conversion
            log_debug(f"{workflow_id}_{node_id}-Cleaning up driver memory...")
            import gc
            data_wrapper[0] = None  # Clear the wrapper reference
            gc.collect()
            
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            log_error(f"{workflow_id}_{node_id}-Arrow conversion failed after {elapsed:.2f}s: {e} - Falling back to non-Arrow conversion")
            
            # Fallback: Disable Arrow and try again
            try:
                spark_session.conf.set("spark.sql.execution.arrow.pyspark.enabled", "false")
                fallback_start = time.time()
                result = spark_session.createDataFrame(data, schema=schema)
                fallback_time = time.time() - fallback_start
                log_debug(f"{workflow_id}_{node_id}-Fallback conversion succeeded in {fallback_time:.2f}s")
                
                # Cleanup
                import gc
                data_wrapper[0] = None
                gc.collect()
                
                return result
            except Exception as fallback_error:
                log_error(f"{workflow_id}_{node_id}-Fallback conversion also failed: {fallback_error}")
                raise

    def _run_custom_code(self, workflow_id, node_id, custom_operation_code):
        """
        :param workflow_id:
        :param node_id: id of node of the DOperation associated with the custom code
        :param custom_operation_code: The code is expected to include a top-level definition
        of a function named according to TRANSFORM_FUNCTION_NAME value
        :return: None
        """

        log_debug(f"{workflow_id}_{node_id}-Running custom code")
        
        # This should've been checked before running
        assert self.isValid(custom_operation_code)

        # In Spark 3.x, newSession() returns a new SparkSession
        log_debug(f"{workflow_id}_{node_id}-Creating new Spark session")
        new_spark_session = self.spark_session.newSession()
        
        # Enable Arrow optimization for toPandas()
        log_debug("Enabling Arrow optimization")
        new_spark_session.conf.set("spark.sql.execution.arrow.pyspark.enabled", "true")
        
        # Ensure the new session has all required attributes
        if not hasattr(new_spark_session, '_wrapped'):
            log_debug(f"{workflow_id}_{node_id}-Setting _wrapped attribute on new session")
            class WrappedHelper:
                def __init__(self, java_spark_session, spark_context):
                    log_debug("Wrapped helper for _wrapped in new session initialized")
                    self._jsparkSession = java_spark_session
                    self._sc = spark_context
                        
                @property
                def _conf(self):
                    return self._jsparkSession.sessionState().conf()
            new_spark_session._wrapped = WrappedHelper(new_spark_session._jsparkSession, self.spark_context)
            
        if not hasattr(new_spark_session, '_ssql_ctx'):
            log_debug(f"{workflow_id}_{node_id}-Setting _ssql_ctx attribute on new session")
            # Create a minimal SQLContext wrapper for the new session
            java_sql_context = new_spark_session._jsparkSession.sqlContext()
            class SQLContextWrapper:
                def __init__(self, java_sql_context):
                    self._jsqlContext = java_sql_context
                def read(self):
                    return self._jsqlContext.read()
            new_spark_session._ssql_ctx = SQLContextWrapper(java_sql_context)

        spark_version = self.spark_context.version
        log_debug(f"{workflow_id}_{node_id}-Spark version: {spark_version}")
        
        # For Spark 3.x, we don't need SQLContext anymore
        if not spark_version.startswith("3."):
            log_debug("Spark version {} is not supported".format(spark_version))
            raise ValueError("Spark version {} is not supported. This code is for Spark 3.x".format(spark_version))

        log_debug(f"{workflow_id}_{node_id}-Retrieving input DataFrame from Java")
        raw_input_data_frame = DataFrame(
            jdf=self.entry_point.retrieveInputDataFrame(workflow_id,
                                                        node_id,
                                                        CodeExecutor.INPUT_PORT_NUMBER),
            sql_ctx=new_spark_session._wrapped)  # In Spark 3.x, use _wrapped instead of sql_ctx
        
        log_debug(f"{workflow_id}_{node_id}-Creating DataFrame in new session")
        # For Spark 3.x, we can use the Java DataFrame directly in the new session
        # Instead of going through RDD, which causes serialization issues
        try:
            # Register the DataFrame as a temp view and recreate it
            temp_view_name = f"temp_input_{workflow_id}_{node_id}".replace("-", "_")
            raw_input_data_frame.createOrReplaceTempView(temp_view_name)
            input_data_frame = new_spark_session.sql(f"SELECT * FROM {temp_view_name}")
            # Clean up the temp view
            new_spark_session.catalog.dropTempView(temp_view_name)
        except Exception as e:
            log_error(f"{workflow_id}_{node_id}-Error with temp view approach: {e}")
            # Fallback: try to create directly from Java DataFrame
            input_data_frame = DataFrame(raw_input_data_frame._jdf, new_spark_session._wrapped)

        # For Spark 3.x, we provide the SparkSession as 'spark' and don't need sqlContext
        context = {
            'sc': self.spark_context,
            'spark': new_spark_session,
            'sqlContext': new_spark_session  # For backward compatibility, map sqlContext to spark session
        }

        log_debug(f"{workflow_id}_{node_id}-Executing code with context keys: {list(context.keys())}")
        try:
            exec(custom_operation_code, context)
            log_debug(f"{workflow_id}_{node_id}-Code execution completed")
        except ImportError as e:
            log_error(f"{workflow_id}_{node_id}-ImportError during code execution: {str(e)}")
            raise Exception(f"ImportError!!! ==> {str(e)}\n")
        
        log_debug(f"{workflow_id}_{node_id}-Calling transform function")
        output_data = context[self.TRANSFORM_FUNCTION_NAME](input_data_frame)
        
        try:
            log_debug(f"{workflow_id}_{node_id}-Converting output data to DataFrame")
            # Wrap output_data in a list to allow _convert_data_to_data_frame to clear the reference
            output_wrapper = [output_data]
            del output_data # Remove local reference immediately, now only wrapper holds it
            output_data_frame = self._convert_data_to_data_frame(output_wrapper, workflow_id, node_id)
        except:
            # We can't access output_data here easily as we deleted it, but usually exception info is enough
            error_msg = 'Operation returned invalid data or DataFrame conversion failed (pandas library available: ' + \
                str(self.is_pandas_available) + ').'
            log_error(f"{workflow_id}_{node_id}-{error_msg}")
            raise Exception(error_msg)
        finally:
             log_debug(f"{workflow_id}_{node_id}-Cleaning up wrapper and context in finally block")
             import gc
             if 'output_wrapper' in locals():
                 output_wrapper[0] = None
                 del output_wrapper
             if 'output_data' in locals():
                 del output_data
             if 'input_data_frame' in locals():
                 del input_data_frame
             gc.collect()

        log_debug(f"{workflow_id}_{node_id}-Registering output DataFrame")
        # noinspection PyProtectedMember
        self.entry_point.registerOutputDataFrame(workflow_id,
                                                 node_id,
                                                 CodeExecutor.OUTPUT_PORT_NUMBER,
                                                 output_data_frame._jdf)
        log_debug(f"{workflow_id}_{node_id}-Output DataFrame registered successfully")

    # noinspection PyPep8Naming
    def isValid(self, custom_operation_code):
        def is_transform_function(field):
            return (isinstance(field, ast.FunctionDef) and
                    field.name == self.TRANSFORM_FUNCTION_NAME and
                    len(field.args.args) in self.TRANSFORM_FUNCTION_ARITIES)

        try:
            parsed = ast.parse(custom_operation_code)
        except SyntaxError:
            log_debug("SyntaxError in custom operation code")
            return False

        is_valid = any(filter(is_transform_function, parsed.body))
        log_debug('Valid code? {}: {}'.format(is_valid, custom_operation_code))
        log_debug(f"Code validation result: {is_valid}")
        return is_valid

    # noinspection PyClassHasNoInit
    class Java:
        implements = ['ai.deepsense.deeplang.CustomCodeExecutor']
