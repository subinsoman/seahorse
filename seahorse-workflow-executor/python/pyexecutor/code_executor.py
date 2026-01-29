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
        print(f"DEBUG: Starting execution thread for workflow {workflow_id}, node {node_id}", file=sys.stderr)
        executor_thread = Thread(
            target=lambda: self._supervised_execution(workflow_id, node_id, custom_operation_code),
            name='Supervisor {}'.format(node_id))

        self.threads.append(executor_thread)

        executor_thread.daemon = True
        executor_thread.start()

    def _supervised_execution(self, workflow_id, node_id, custom_operation_code):
        # noinspection PyBroadException
        try:
            print(f"DEBUG: Beginning supervised execution for node {node_id}", file=sys.stderr)
            self._run_custom_code(workflow_id, node_id, custom_operation_code)
            self.entry_point.executionCompleted(workflow_id, node_id)
            print(f"DEBUG: Execution completed successfully for node {node_id}", file=sys.stderr)
        except Exception as e:
            log_error('AN ERROR OCCURED ==>')
            stacktrace = traceback.format_exc()
            log_error(stacktrace)
            print(f"DEBUG: Execution failed for node {node_id}: {str(e)}", file=sys.stderr)
            self.entry_point.executionFailed(workflow_id, node_id, stacktrace)
            log_error('ERROR END')

    def _convert_data_to_data_frame(self, data):
        spark_session = self.spark_session
        sc = self.spark_context
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
            print("DEBUG: Converting pandas DataFrame to Spark DataFrame", file=sys.stderr)
            # Use Java-based conversion to avoid Python RDD operations
            try:
                print("DEBUG: Using Java-based pandas conversion", file=sys.stderr)
                # Convert pandas to JSON and then to Spark DataFrame
                json_str = data.to_json(orient='records')
                
                # Create RDD from JSON string using Java directly
                java_rdd = spark_session._jvm.spark.sparkContext.parallelize(
                    spark_session._jvm.java.util.Arrays.asList(json_str)
                )
                
                # Read JSON RDD as DataFrame
                df = spark_session.read.json(java_rdd)
                return df
            except Exception as e:
                print(f"DEBUG: Error in Java-based conversion: {e}", file=sys.stderr)
                try:
                    # Alternative: Write to temp file and read back
                    import tempfile
                    import os
                    print("DEBUG: Using temp file conversion", file=sys.stderr)
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                        data.to_json(f, orient='records', lines=True)
                        temp_path = f.name
                    
                    # Read from temp file
                    df = spark_session.read.json(temp_path)
                    
                    # Clean up
                    os.unlink(temp_path)
                    return df
                except Exception as e2:
                    print(f"DEBUG: Error in temp file conversion: {e2}", file=sys.stderr)
                    # Last resort: Build DataFrame with proper types
                    try:
                        from pyspark.sql.types import StructType, StructField, StringType, IntegerType, LongType, FloatType, DoubleType, BooleanType, TimestampType
                        from pyspark.sql import Row
                        import numpy as np
                        
                        print("DEBUG: Using typed conversion with Row objects", file=sys.stderr)
                        
                        # Map pandas dtypes to Spark types
                        def pandas_to_spark_type(pandas_dtype):
                            dtype_str = str(pandas_dtype)
                            if dtype_str.startswith('int64'):
                                return LongType()
                            elif dtype_str.startswith('int'):
                                return IntegerType()
                            elif dtype_str.startswith('float64'):
                                return DoubleType()
                            elif dtype_str.startswith('float'):
                                return FloatType()
                            elif dtype_str.startswith('bool'):
                                return BooleanType()
                            elif dtype_str.startswith('datetime'):
                                return TimestampType()
                            else:
                                return StringType()
                        
                        # Create schema based on pandas dtypes
                        fields = []
                        for col in data.columns:
                            spark_type = pandas_to_spark_type(data[col].dtype)
                            fields.append(StructField(col, spark_type, True))
                        schema = StructType(fields)
                        
                        # Convert data to list of Rows, handling NaN values
                        rows = []
                        for idx, row in data.iterrows():
                            row_dict = {}
                            for col in data.columns:
                                val = row[col]
                                # Handle NaN values
                                if pandas.isna(val):
                                    row_dict[col] = None
                                elif isinstance(val, (np.integer, np.floating)):
                                    # Convert numpy types to Python types
                                    row_dict[col] = val.item()
                                else:
                                    row_dict[col] = val
                            rows.append(Row(**row_dict))
                        
                        # Create DataFrame with schema
                        return spark_session.createDataFrame(rows, schema)
                    except Exception as e3:
                        print(f"DEBUG: Error in typed conversion: {e3}", file=sys.stderr)
                        # Final fallback: simple conversion
                        rows = data.values.tolist()
                        columns = data.columns.tolist()
                        return spark_session.createDataFrame(rows, columns)
        elif isinstance(data, (list, tuple)) and all(isinstance(el, (list, tuple)) for el in data):
            print("DEBUG: Converting list of lists/tuples to DataFrame", file=sys.stderr)
            return spark_session.createDataFrame(data)
        elif isinstance(data, (list, tuple)):
            print("DEBUG: Converting list/tuple to DataFrame", file=sys.stderr)
            # Convert to list of single-element tuples
            rows = [(x,) for x in data]
            return spark_session.createDataFrame(rows)
        else:
            print("DEBUG: Converting single value to DataFrame", file=sys.stderr)
            return spark_session.createDataFrame([(data,)])

    def _run_custom_code(self, workflow_id, node_id, custom_operation_code):
        """
        :param workflow_id:
        :param node_id: id of node of the DOperation associated with the custom code
        :param custom_operation_code: The code is expected to include a top-level definition
        of a function named according to TRANSFORM_FUNCTION_NAME value
        :return: None
        """

        print(f"DEBUG: Running custom code for workflow {workflow_id}, node {node_id}", file=sys.stderr)
        
        # This should've been checked before running
        assert self.isValid(custom_operation_code)

        # In Spark 3.x, newSession() returns a new SparkSession
        print("DEBUG: Creating new Spark session", file=sys.stderr)
        new_spark_session = self.spark_session.newSession()
        
        # Ensure the new session has all required attributes
        if not hasattr(new_spark_session, '_wrapped'):
            print("DEBUG: Setting _wrapped attribute on new session", file=sys.stderr)
            new_spark_session._wrapped = new_spark_session._jsparkSession
            
        if not hasattr(new_spark_session, '_ssql_ctx'):
            print("DEBUG: Setting _ssql_ctx attribute on new session", file=sys.stderr)
            # Create a minimal SQLContext wrapper for the new session
            java_sql_context = new_spark_session._jsparkSession.sqlContext()
            class SQLContextWrapper:
                def __init__(self, java_sql_context):
                    self._jsqlContext = java_sql_context
                def read(self):
                    return self._jsqlContext.read()
            new_spark_session._ssql_ctx = SQLContextWrapper(java_sql_context)

        spark_version = self.spark_context.version
        print(f"DEBUG: Spark version: {spark_version}", file=sys.stderr)
        
        # For Spark 3.x, we don't need SQLContext anymore
        if not spark_version.startswith("3."):
            log_debug("Spark version {} is not supported".format(spark_version))
            raise ValueError("Spark version {} is not supported. This code is for Spark 3.x".format(spark_version))

        print("DEBUG: Retrieving input DataFrame from Java", file=sys.stderr)
        raw_input_data_frame = DataFrame(
            jdf=self.entry_point.retrieveInputDataFrame(workflow_id,
                                                        node_id,
                                                        CodeExecutor.INPUT_PORT_NUMBER),
            sql_ctx=new_spark_session._wrapped)  # In Spark 3.x, use _wrapped instead of sql_ctx
        
        print("DEBUG: Creating DataFrame in new session", file=sys.stderr)
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
            print(f"DEBUG: Error with temp view approach: {e}", file=sys.stderr)
            # Fallback: try to create directly from Java DataFrame
            input_data_frame = DataFrame(raw_input_data_frame._jdf, new_spark_session._wrapped)

        # For Spark 3.x, we provide the SparkSession as 'spark' and don't need sqlContext
        context = {
            'sc': self.spark_context,
            'spark': new_spark_session,
            'sqlContext': new_spark_session  # For backward compatibility, map sqlContext to spark session
        }

        print('DEBUG: Executing code with context keys: {}\n'.format(list(context.keys())), file=sys.stderr)
        try:
            exec(custom_operation_code, context)
            print("DEBUG: Code execution completed", file=sys.stderr)
        except ImportError as e:
            log_debug('ImportError!!! ==> {}\n'.format(str(e)))
            print(f"DEBUG: ImportError during code execution: {str(e)}", file=sys.stderr)
            raise Exception('ImportError!!! ==> {}\n'.format(str(e)))
        
        print("DEBUG: Calling transform function", file=sys.stderr)
        output_data = context[self.TRANSFORM_FUNCTION_NAME](input_data_frame)
        
        try:
            print("DEBUG: Converting output data to DataFrame", file=sys.stderr)
            output_data_frame = self._convert_data_to_data_frame(output_data)
        except:
            error_msg = 'Operation returned {} instead of a DataFrame'.format(output_data) + \
                ' (or pandas.DataFrame, single value, tuple/list of single values,' + \
                ' tuple/list of tuples/lists of single values) (pandas library available: ' + \
                str(self.is_pandas_available) + ').'
            log_debug(error_msg)
            print(f"DEBUG: {error_msg}", file=sys.stderr)
            raise Exception(error_msg)

        print("DEBUG: Registering output DataFrame", file=sys.stderr)
        # noinspection PyProtectedMember
        self.entry_point.registerOutputDataFrame(workflow_id,
                                                 node_id,
                                                 CodeExecutor.OUTPUT_PORT_NUMBER,
                                                 output_data_frame._jdf)
        print("DEBUG: Output DataFrame registered successfully", file=sys.stderr)

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
