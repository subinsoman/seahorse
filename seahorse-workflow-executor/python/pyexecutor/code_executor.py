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
        print(f"DEBUG: {workflow_id}_{node_id}-Starting execution thread", file=sys.stderr)
        executor_thread = Thread(
            target=lambda: self._supervised_execution(workflow_id, node_id, custom_operation_code),
            name='Supervisor {}'.format(node_id))

        self.threads.append(executor_thread)

        executor_thread.daemon = True
        executor_thread.start()

    def _supervised_execution(self, workflow_id, node_id, custom_operation_code):
        # noinspection PyBroadException
        try:
            print("+++++++++++++++++++++++++++++", file=sys.stderr)
            print("python tranformation job exicution starts", file=sys.stderr)
            print("+++++++++++++++++++++++++++++", file=sys.stderr)
            print(f"DEBUG: {workflow_id}_{node_id}-Beginning supervised execution", file=sys.stderr)
            self._run_custom_code(workflow_id, node_id, custom_operation_code)
            self.entry_point.executionCompleted(workflow_id, node_id)
            print(f"DEBUG: {workflow_id}_{node_id}-Execution completed successfully", file=sys.stderr)
            print("+++++++++++++++++++++++++++++", file=sys.stderr)
            print("python tranformation job exicution ends", file=sys.stderr)
            print("+++++++++++++++++++++++++++++", file=sys.stderr)
        except Exception as e:
            log_error(f"{workflow_id}_{node_id}-AN ERROR OCCURRED ==>")
            stacktrace = traceback.format_exc()
            log_error(f"{workflow_id}_{node_id}-{stacktrace}")
            print(f"DEBUG: {workflow_id}_{node_id}-Execution failed: {str(e)}", file=sys.stderr)
            self.entry_point.executionFailed(workflow_id, node_id, stacktrace)
            log_error(f"{workflow_id}_{node_id}-ERROR END")

    def _convert_data_to_data_frame(self, data_wrapper):
        """
        Accepts a list wrapper [data] to allow clearing the caller's reference.
        """
        spark_session = self.spark_session
        
        # Extract data from wrapper
        data = data_wrapper[0]
        
        print(f"DEBUG: Converting data of type {type(data)} to DataFrame", file=sys.stderr)
        
        try:
            import pandas
            self.is_pandas_available = True
            print("DEBUG: Pandas is available", file=sys.stderr)
        except ImportError:
            self.is_pandas_available = False
            print("DEBUG: Pandas is not available", file=sys.stderr)
            
        if isinstance(data, DataFrame):
            print("DEBUG: Data is already a DataFrame", file=sys.stderr)
            return data
        elif self.is_pandas_available and isinstance(data, pandas.DataFrame):
            return self._distributed_pandas_to_spark(data, data_wrapper)

        elif isinstance(data, (list, tuple)) and all(isinstance(el, (list, tuple)) for el in data):
            print("DEBUG: Converting list of lists/tuples to DataFrame", file=sys.stderr)
            return spark_session.createDataFrame(data)
        elif isinstance(data, (list, tuple)):
            print("DEBUG: Converting list/tuple to DataFrame", file=sys.stderr)
            # Convert to single-element tuples
            rows = [(x,) for x in data]
            return spark_session.createDataFrame(rows)
        else:
            print("DEBUG: Converting single value to DataFrame", file=sys.stderr)
            return spark_session.createDataFrame([(data,)])

    def _distributed_pandas_to_spark(self, data, data_wrapper):
        """
        Converts a Pandas DataFrame to a Spark DataFrame using a distributed strategy.
        Splits the Pandas DF into chunks, parallelizes them, and converts to rows on executors.
        This avoids converting the entire DF to a list of rows on the driver.
        """
        print("DEBUG: Converting pandas DataFrame to Spark DataFrame using Distributed Strategy", file=sys.stderr)
        sc = self.spark_context
        spark_session = self.spark_session
        
        # Capture schema if attached
        schema = getattr(data, "_spark_schema", None)
        if schema:
             print("DEBUG: Found attached _spark_schema", file=sys.stderr)

        try:
            # OPTION 1: Distributed Conversion (Cluster Bound)
            print("DEBUG: Using Distributed Conversion Strategy to force Cluster execution", file=sys.stderr)
            import numpy as np
            
            # 1. Determine partitions
            try:
                # Aggressive partitioning to keep chunk sizes small
                num_partitions = int(sc.defaultParallelism) * 10
            except:
                num_partitions = 16 
                
            if num_partitions < 8: 
                num_partitions = 8
            
            print(f"DEBUG: Splitting Pandas DataFrame into {num_partitions} chunks", file=sys.stderr)
            
            # 2. Split Pandas DF into Views using iloc (Manual Slicing)
            # np.array_split typically creates copies or complex objects. Manual slicing creates views.
            # We must be careful to use integer indexing.
            rows = len(data)
            chunk_size = int(np.ceil(rows / num_partitions))
            pdf_chunks = [data.iloc[i : i + chunk_size] for i in range(0, rows, chunk_size)]
            
            # Cache info for fallback
            data_columns = list(data.columns)
            data_dtypes = data.dtypes
            
            # Generate schema on driver if not provided
            driver_generated_schema = None
            if not schema:
                print("DEBUG: Generating Spark Schema from Pandas dtypes on Driver", file=sys.stderr)
                try:
                    fields = []
                    for col_name, dtype in data_dtypes.items():
                        if str(dtype) == 'int64':
                            spark_type = LongType()
                        elif str(dtype) == 'float64':
                            spark_type = DoubleType()
                        elif str(dtype) == 'bool':
                            spark_type = BooleanType()
                        elif str(dtype).startswith('datetime'):
                            spark_type = TimestampType()
                        else:
                            spark_type = StringType()
                        fields.append(StructField(str(col_name), spark_type, True))
                    
                    driver_generated_schema = StructType(fields)
                    print(f"DEBUG: Generated Schema: {driver_generated_schema}", file=sys.stderr)
                except Exception as e:
                    print(f"DEBUG: Failed to generate schema on driver: {e}", file=sys.stderr)

            # 3. Parallelize chunks
            chunk_rdd = sc.parallelize(pdf_chunks, num_partitions)
            
            # CLEANUP DRIVER MEMORY
            print("DEBUG: Cleaning up driver memory (Pandas DF + Chunks)", file=sys.stderr)
            import gc
            del data
            del pdf_chunks
            data_wrapper[0] = None # Clear caller ref
            gc.collect()
            
            # 4. Define conversion logic
            def process_chunk_to_rows(chunk_iterator):
                import gc
                # Note: chunk_iterator yields logic chunks (numpy arrays of DF), 
                # but parallelize(list_of_dfs) means each item is a DF.
                # mapPartitions yields an iterator of items in the partition.
                # If we parallelized N chunks into N partitions, 
                # each partition has exactly 1 chunk (DataFrame).
                
                for chunk in chunk_iterator:
                    if not chunk.empty:
                        # itertuples is efficient
                        yield from chunk.itertuples(index=False, name=None)
                
                gc.collect()
                        
            # 5. Execute on cluster
            print("DEBUG: Processing chunks on executors...", file=sys.stderr)
            data_rdd = chunk_rdd.mapPartitions(process_chunk_to_rows)
            
            # 6. Create DataFrame
            print("DEBUG: Creating DataFrame from Distributed RDD", file=sys.stderr)
            
            # Enable Arrow just in case
            spark_session.conf.set("spark.sql.execution.arrow.pyspark.enabled", "true")

            if schema:
                 return spark_session.createDataFrame(data_rdd, schema=schema)
            elif driver_generated_schema:
                 return spark_session.createDataFrame(data_rdd, schema=driver_generated_schema)
            else:
                 return spark_session.createDataFrame(data_rdd, schema=data_columns)

        except Exception as e:
            print(f"DEBUG: Distributed conversion failed: {e}. Fallback...", file=sys.stderr)
            # If we already deleted data (data_wrapper[0] is None), we can't fallback easily
            # But 'data' in this scope might be gone if we del'd it.
            # However, if exception happened BEFORE del, we are good.
            # If AFTER del, we are in trouble.
            # We check locals.
            
            # Since we can't reliably recover if data is deleted, we re-raise if it's gone.
            if data_wrapper[0] is None:
                 print("DEBUG: Data already cleared from driver, cannot fallback.", file=sys.stderr)
                 raise e
            
            # Fallback
            return spark_session.createDataFrame(data, schema=schema)

    def _run_custom_code(self, workflow_id, node_id, custom_operation_code):
        """
        :param workflow_id:
        :param node_id: id of node of the DOperation associated with the custom code
        :param custom_operation_code: The code is expected to include a top-level definition
        of a function named according to TRANSFORM_FUNCTION_NAME value
        :return: None
        """

        print(f"DEBUG: {workflow_id}_{node_id}-Running custom code", file=sys.stderr)
        
        # This should've been checked before running
        assert self.isValid(custom_operation_code)

        # In Spark 3.x, newSession() returns a new SparkSession
        print(f"DEBUG: {workflow_id}_{node_id}-Creating new Spark session", file=sys.stderr)
        new_spark_session = self.spark_session.newSession()
        
        # Enable Arrow optimization for toPandas()
        print("DEBUG: Enabling Arrow optimization", file=sys.stderr)
        new_spark_session.conf.set("spark.sql.execution.arrow.pyspark.enabled", "true")
        
        # Ensure the new session has all required attributes
        if not hasattr(new_spark_session, '_wrapped'):
            print(f"DEBUG: {workflow_id}_{node_id}-Setting _wrapped attribute on new session", file=sys.stderr)
            class WrappedHelper:
                def __init__(self, java_spark_session, spark_context):
                    print("DEBUGGING: Wrapped helper for _wrapped in new session initialized", file=sys.stderr)
                    self._jsparkSession = java_spark_session
                    self._sc = spark_context
                        
                @property
                def _conf(self):
                    return self._jsparkSession.sessionState().conf()
            new_spark_session._wrapped = WrappedHelper(new_spark_session._jsparkSession, self.spark_context)
            
        if not hasattr(new_spark_session, '_ssql_ctx'):
            print(f"DEBUG: {workflow_id}_{node_id}-Setting _ssql_ctx attribute on new session", file=sys.stderr)
            # Create a minimal SQLContext wrapper for the new session
            java_sql_context = new_spark_session._jsparkSession.sqlContext()
            class SQLContextWrapper:
                def __init__(self, java_sql_context):
                    self._jsqlContext = java_sql_context
                def read(self):
                    return self._jsqlContext.read()
            new_spark_session._ssql_ctx = SQLContextWrapper(java_sql_context)

        spark_version = self.spark_context.version
        print(f"DEBUG: {workflow_id}_{node_id}-Spark version: {spark_version}", file=sys.stderr)
        
        # For Spark 3.x, we don't need SQLContext anymore
        if not spark_version.startswith("3."):
            log_debug("Spark version {} is not supported".format(spark_version))
            raise ValueError("Spark version {} is not supported. This code is for Spark 3.x".format(spark_version))

        print(f"DEBUG: {workflow_id}_{node_id}-Retrieving input DataFrame from Java", file=sys.stderr)
        raw_input_data_frame = DataFrame(
            jdf=self.entry_point.retrieveInputDataFrame(workflow_id,
                                                        node_id,
                                                        CodeExecutor.INPUT_PORT_NUMBER),
            sql_ctx=new_spark_session._wrapped)  # In Spark 3.x, use _wrapped instead of sql_ctx
        
        print(f"DEBUG: {workflow_id}_{node_id}-Creating DataFrame in new session", file=sys.stderr)
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
            print(f"DEBUG: {workflow_id}_{node_id}-Error with temp view approach: {e}", file=sys.stderr)
            # Fallback: try to create directly from Java DataFrame
            input_data_frame = DataFrame(raw_input_data_frame._jdf, new_spark_session._wrapped)

        # For Spark 3.x, we provide the SparkSession as 'spark' and don't need sqlContext
        context = {
            'sc': self.spark_context,
            'spark': new_spark_session,
            'sqlContext': new_spark_session  # For backward compatibility, map sqlContext to spark session
        }

        print(f"DEBUG: {workflow_id}_{node_id}-Executing code with context keys: {list(context.keys())}\n", file=sys.stderr)
        try:
            exec(custom_operation_code, context)
            print(f"DEBUG: {workflow_id}_{node_id}-Code execution completed", file=sys.stderr)
        except ImportError as e:
            log_debug(f"{workflow_id}_{node_id}-ImportError!!! ==> {str(e)}\n")
            print(f"DEBUG: {workflow_id}_{node_id}-ImportError during code execution: {str(e)}", file=sys.stderr)
            raise Exception(f"ImportError!!! ==> {str(e)}\n")
        
        print(f"DEBUG: {workflow_id}_{node_id}-Calling transform function", file=sys.stderr)
        output_data = context[self.TRANSFORM_FUNCTION_NAME](input_data_frame)
        
        try:
            print(f"DEBUG: {workflow_id}_{node_id}-Converting output data to DataFrame", file=sys.stderr)
            # Wrap output_data in a list to allow _convert_data_to_data_frame to clear the reference
            output_wrapper = [output_data]
            del output_data # Remove local reference immediately, now only wrapper holds it
            output_data_frame = self._convert_data_to_data_frame(output_wrapper)
        except:
            # We can't access output_data here easily as we deleted it, but usually exception info is enough
            error_msg = 'Operation returned invalid data or DataFrame conversion failed (pandas library available: ' + \
                str(self.is_pandas_available) + ').'
            log_debug(f"{workflow_id}_{node_id}-{error_msg}")
            print(f"DEBUG: {workflow_id}_{node_id}-{error_msg}", file=sys.stderr)
            raise Exception(error_msg)
        finally:
             print(f"DEBUG: {workflow_id}_{node_id}-Cleaning up wrapper and context in finally block", file=sys.stderr)
             import gc
             if 'output_wrapper' in locals():
                 output_wrapper[0] = None
                 del output_wrapper
             if 'output_data' in locals():
                 del output_data
             if 'input_data_frame' in locals():
                 del input_data_frame
             gc.collect()

        print(f"DEBUG: {workflow_id}_{node_id}-Registering output DataFrame", file=sys.stderr)
        # noinspection PyProtectedMember
        self.entry_point.registerOutputDataFrame(workflow_id,
                                                 node_id,
                                                 CodeExecutor.OUTPUT_PORT_NUMBER,
                                                 output_data_frame._jdf)
        print(f"DEBUG: {workflow_id}_{node_id}-Output DataFrame registered successfully", file=sys.stderr)

    # noinspection PyPep8Naming
    def isValid(self, custom_operation_code):
        def is_transform_function(field):
            return (isinstance(field, ast.FunctionDef) and
                    field.name == self.TRANSFORM_FUNCTION_NAME and
                    len(field.args.args) in self.TRANSFORM_FUNCTION_ARITIES)

        try:
            parsed = ast.parse(custom_operation_code)
        except SyntaxError:
            print("DEBUG: SyntaxError in custom operation code", file=sys.stderr)
            return False

        is_valid = any(filter(is_transform_function, parsed.body))
        log_debug('Valid code? {}: {}'.format(is_valid, custom_operation_code))
        print(f"DEBUG: Code validation result: {is_valid}", file=sys.stderr)
        return is_valid

    # noinspection PyClassHasNoInit
    class Java:
        implements = ['ai.deepsense.deeplang.CustomCodeExecutor']
