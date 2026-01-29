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

import argparse
import os
import sys
import time
from py4j.java_gateway import JavaGateway, GatewayClient, CallbackServerParameters, java_import
from py4j.protocol import Py4JError
from pyspark import SparkContext, SparkConf
from pyspark.sql import SparkSession

from code_executor import CodeExecutor
from simple_logging import log_debug, log_error


class PyExecutor(object):
    def __init__(self, gateway_address):
        self.gateway_address = gateway_address

    def run(self):
        print("DEBUG: Starting PyExecutor initialization", file=sys.stderr)
        gateway = self._initialize_gateway(self.gateway_address)
        if not gateway:
            log_error('Failed to initialize java gateway')
            return

        # noinspection PyProtectedMember
        callback_server_port = gateway._callback_server.server_socket.getsockname()[1]
        print(f"DEBUG: Callback server port: {callback_server_port}", file=sys.stderr)
        
        spark_context, spark_session = self._initialize_spark_contexts(gateway)
        code_executor = CodeExecutor(spark_context, spark_session, gateway.entry_point)

        try:
            print("DEBUG: Registering callback server port", file=sys.stderr)
            gateway.entry_point.registerCallbackServerPort(callback_server_port)
            print("DEBUG: Registering code executor", file=sys.stderr)
            gateway.entry_point.registerCodeExecutor(code_executor)
            print("DEBUG: Registration complete", file=sys.stderr)
        except Py4JError as e:
            log_error('Exception while registering codeExecutor, or callback server port: {}'.format(e))
            gateway.close()
            return

        # Wait for the end of the world or being orphaned
        try:
            print("DEBUG: Entering main loop", file=sys.stderr)
            while True:
                if os.getppid() == 1:
                    log_debug("I am an orphan - stopping")
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            log_debug('Exiting on user\'s request')

        gateway.close()

    @staticmethod
    def _initialize_spark_contexts(gateway):
        print("DEBUG: About to call getSparkContext", file=sys.stderr)
        java_spark_context = gateway.entry_point.getSparkContext()
        print("DEBUG: Got JavaSparkContext", file=sys.stderr)
        
        java_spark_conf = java_spark_context.getConf()
        print("DEBUG: Got JavaSparkConf", file=sys.stderr)

        # For Spark 3.x, we need to handle the security check
        print("DEBUG: Setting up PySpark with existing Java context", file=sys.stderr)
        
        try:
            # First, we need to set up the environment to bypass the security check
            # This is done by setting the gateway as authorized
            print("DEBUG: Setting up authorized gateway", file=sys.stderr)
            
            # Set environment variable to mark this as an authorized gateway
            os.environ["PYSPARK_GATEWAY_ENABLED"] = "1"
            
            # Initialize PySpark internals
            print("DEBUG: Initializing PySpark internals", file=sys.stderr)
            SparkContext._ensure_initialized(gateway=gateway)
            
            # Check if there's already an active context
            if SparkContext._active_spark_context is None:
                print("DEBUG: No active SparkContext, creating wrapper", file=sys.stderr)
                
                # For Spark 3.x with existing Java context, we need to use a different approach
                # We'll create the context without initializing a new Java context
                spark_context = SparkContext._active_spark_context = object.__new__(SparkContext)
                spark_context._jsc = java_spark_context
                spark_context._jvm = gateway.jvm
                spark_context._gateway = gateway
                
                # Get the accumulator server port
                print("DEBUG: Getting accumulator server port", file=sys.stderr)
                spark_context._accumulatorServer = None
                
                # Set up the Python accumulator server if needed
                try:
                    from pyspark.accumulators import _start_update_server
                    print("DEBUG: Starting accumulator server", file=sys.stderr)
                    # For Spark 3.x, we need to provide an auth token
                    auth_token = None
                    if hasattr(spark_context._jsc, "authHelper"):
                        auth_token = spark_context._jsc.authHelper().secret()
                    spark_context._accumulatorServer = _start_update_server(auth_token)
                    spark_context._jsc.sc().setLocalProperty(
                        "spark.python.accumulatorServer.port",
                        str(spark_context._accumulatorServer.port)
                    )
                except Exception as e:
                    print(f"DEBUG: Could not start accumulator server: {e}", file=sys.stderr)
                
                # Initialize other SparkContext attributes
                spark_context._conf = SparkConf(_jvm=gateway.jvm, _jconf=java_spark_conf)
                spark_context._batchSize = 1  # Default batch size
                spark_context._pythonExec = sys.executable
                spark_context._javaAccumulator = None
                
                # Set Python executable and version info
                # Get the Python executable from Spark configuration or use a default
                try:
                    # Check if there's a configured Python executable for executors
                    pyspark_python = os.environ.get('PYSPARK_PYTHON')
                    if not pyspark_python:
                        # Try to get from Spark conf
                        pyspark_python = spark_context._conf.get('spark.pyspark.python', None)
                    
                    if not pyspark_python:
                        # Use a common Python path that should exist on executors
                        # Common paths: /usr/bin/python3, /usr/bin/python, python3, python
                        for python_path in ['/usr/bin/python3', '/usr/bin/python3.7', '/usr/bin/python', 'python3', 'python']:
                            try:
                                # Check if this Python exists by trying to get its version
                                import subprocess
                                result = subprocess.run([python_path, '--version'], 
                                                      capture_output=True, 
                                                      text=True, 
                                                      timeout=5)
                                if result.returncode == 0:
                                    pyspark_python = python_path
                                    print(f"DEBUG: Found Python at {python_path}", file=sys.stderr)
                                    break
                            except:
                                continue
                    
                    if not pyspark_python:
                        # Fallback to current Python
                        pyspark_python = sys.executable
                        print(f"WARNING: Using driver Python {pyspark_python}, may not exist on executors", file=sys.stderr)
                    
                    spark_context.pythonExec = pyspark_python
                    spark_context._pythonExec = pyspark_python
                    
                    # Also set the environment variable
                    os.environ['PYSPARK_PYTHON'] = pyspark_python
                    
                    print(f"DEBUG: Set Python executable to {pyspark_python}", file=sys.stderr)
                    
                except Exception as e:
                    print(f"DEBUG: Error setting Python executable: {e}", file=sys.stderr)
                    spark_context.pythonExec = sys.executable
                    spark_context._pythonExec = sys.executable
                
                spark_context.pythonVer = "%d.%d" % sys.version_info[:2]
                
                # Initialize environment as empty dict
                spark_context.environment = {}
                # Try to get some basic environment info
                try:
                    # Add Python version to environment
                    spark_context.environment['PYTHONVERSION'] = spark_context.pythonVer
                    # Add any Spark Python specific env vars
                    for key, value in os.environ.items():
                        if key.startswith('PYSPARK_'):
                            spark_context.environment[key] = value
                except Exception as e:
                    print(f"DEBUG: Error setting environment: {e}", file=sys.stderr)
                
                # Initialize serializers - CRITICAL for RDD operations
                print("DEBUG: Initializing serializers", file=sys.stderr)
                from pyspark.serializers import PickleSerializer, BatchedSerializer
                spark_context._unbatched_serializer = PickleSerializer()
                spark_context._serializer = BatchedSerializer(spark_context._unbatched_serializer,
                                                              batchSize=spark_context._batchSize)
                spark_context.serializer = spark_context._serializer
                
                # Initialize encryption settings - handle missing method gracefully
                try:
                    spark_context._encryption_enabled = spark_context._jsc.sc().isEncryptionEnabled()
                except Exception as e:
                    print(f"DEBUG: Could not get encryption status: {e}, defaulting to False", file=sys.stderr)
                    spark_context._encryption_enabled = False
                
                # Initialize Python server if needed
                print("DEBUG: Setting up Python server", file=sys.stderr)
                spark_context._python_includes = []
                
                # Initialize temp directory for RDD operations
                print("DEBUG: Setting up temp directory", file=sys.stderr)
                import tempfile
                import atexit
                import shutil
                spark_context._temp_dir = tempfile.mkdtemp(prefix="pyspark-")
                # Register cleanup
                def cleanup_temp_dir():
                    try:
                        shutil.rmtree(spark_context._temp_dir)
                    except Exception:
                        pass
                atexit.register(cleanup_temp_dir)
                
                # Set master URL from conf
                try:
                    spark_context.master = spark_context._conf.get("spark.master", "unknown")
                except Exception as e:
                    print(f"DEBUG: Could not get master: {e}", file=sys.stderr)
                    spark_context.master = "unknown"
                
                # Set application ID
                try:
                    spark_context._jsc_application_id = spark_context._jsc.sc().applicationId()
                except Exception as e:
                    print(f"DEBUG: Could not get application ID: {e}", file=sys.stderr)
                    spark_context._jsc_application_id = None
                    
                # Initialize profiler settings
                spark_context._profile_stats = []
                spark_context._profile_dump_path = None
                spark_context.profiler_collector = None
                
                # Initialize RDD settings
                spark_context._next_rdd_id = 0
                spark_context._jvm_dumping_enabled = False
                spark_context._checkpointDir = None
                
                # Initialize broadcast variables
                spark_context._pickled_broadcast_vars = []
                spark_context._broadcast_vars = {}
                
                # Initialize other required attributes for RDD operations
                spark_context._stopped = False
                spark_context._default_parallelism = None
                
                print("DEBUG: SparkContext wrapper created", file=sys.stderr)
            else:
                print("DEBUG: Using existing active SparkContext", file=sys.stderr)
                spark_context = SparkContext._active_spark_context
                
        except Exception as e:
            print(f"DEBUG: Error creating SparkContext: {str(e)}", file=sys.stderr)
            import traceback
            print(f"DEBUG: Traceback: {traceback.format_exc()}", file=sys.stderr)
            raise
        
        print(f"DEBUG: SparkContext ready, version: {spark_context.version}", file=sys.stderr)

        print("DEBUG: About to call getSparkSQLSession", file=sys.stderr)
        java_spark_sql_session = gateway.entry_point.getSparkSQLSession()
        print("DEBUG: Got JavaSparkSQLSession", file=sys.stderr)
        
        spark_version = spark_context.version
        spark_session = None
        
        # For Spark 3.0.0 and later versions
        if spark_version.startswith("3."):
            print("DEBUG: Initializing SparkSession for Spark 3.x", file=sys.stderr)
            try:
                # Get the Java SparkSession from the Java SQL session
                print("DEBUG: Getting Java SparkSession from JavaSparkSQLSession", file=sys.stderr)
                java_spark_session = java_spark_sql_session.getSparkSession()
                print("DEBUG: Got Java SparkSession object", file=sys.stderr)
                
                # Check if SparkSession already exists
                if hasattr(SparkSession, "_instantiatedSession") and SparkSession._instantiatedSession is not None:
                    print("DEBUG: Using existing SparkSession", file=sys.stderr)
                    spark_session = SparkSession._instantiatedSession
                else:
                    # Create Python wrapper for the existing SparkSession
                    print("DEBUG: Creating new Python SparkSession wrapper", file=sys.stderr)
                    # In Spark 3.x, we can create the wrapper directly
                    spark_session = object.__new__(SparkSession)
                    spark_session._sc = spark_context
                    spark_session._jsparkSession = java_spark_session
                    spark_session._jvm = gateway.jvm
                    # Add _wrapped attribute which should be the Java session's wrapped object
                    spark_session._wrapped = java_spark_session
                    
                    # For Spark 3.x compatibility, set up the internal SQLContext
                    print("DEBUG: Setting up internal SQLContext", file=sys.stderr)
                    # Get the Java SQLContext from the SparkSession
                    java_sql_context = java_spark_session.sqlContext()
                    # Create a minimal SQLContext wrapper
                    class SQLContextWrapper:
                        def __init__(self, java_sql_context):
                            self._jsqlContext = java_sql_context
                        def read(self):
                            return self._jsqlContext.read()
                    
                    spark_session._ssql_ctx = SQLContextWrapper(java_sql_context)
                    
                    # Initialize other required internal attributes
                    spark_session._instantiatedSession = spark_session
                    spark_session._activeSession = spark_session
                    
                    # Set the shared state and session state from Java session
                    spark_session._jsparkSession = java_spark_session
                    spark_session._jwrapped = java_spark_session
                    
                    SparkSession._instantiatedSession = spark_session
                    print("DEBUG: SparkSession wrapper created successfully", file=sys.stderr)
                
            except Exception as e:
                print(f"DEBUG: Error creating SparkSession: {str(e)}", file=sys.stderr)
                print(f"DEBUG: Error type: {type(e).__name__}", file=sys.stderr)
                import traceback
                print(f"DEBUG: Traceback: {traceback.format_exc()}", file=sys.stderr)
                raise
        else:
            log_error("Spark version {} is not supported. This code is for Spark 3.x".format(spark_version))
            raise ValueError("Spark version {} is not supported. This code is for Spark 3.x".format(spark_version))

        print(f"DEBUG: Successfully initialized contexts", file=sys.stderr)
        return spark_context, spark_session

    @staticmethod
    def _initialize_gateway(gateway_address):
        (host, port) = gateway_address
        print(f"DEBUG: Initializing gateway at {host}:{port}", file=sys.stderr)

        callback_params = CallbackServerParameters(address=host, port=0)

        gateway = JavaGateway(GatewayClient(address=host, port=port),
                              start_callback_server=True,
                              auto_convert=True,
                              callback_server_parameters=callback_params)
        try:
            print("DEBUG: Importing Java classes", file=sys.stderr)
            java_import(gateway.jvm, "org.apache.spark.SparkEnv")
            java_import(gateway.jvm, "org.apache.spark.SparkConf")
            java_import(gateway.jvm, "org.apache.spark.api.java.*")
            java_import(gateway.jvm, "org.apache.spark.api.python.*")
            java_import(gateway.jvm, "org.apache.spark.mllib.api.python.*")
            java_import(gateway.jvm, "org.apache.spark.sql.*")
            java_import(gateway.jvm, "org.apache.spark.sql.hive.*")
            java_import(gateway.jvm, "scala.Tuple2")
            java_import(gateway.jvm, "scala.collection.immutable.List")
            print("DEBUG: Java imports completed", file=sys.stderr)
        except Py4JError as e:
            log_error('Error while initializing java gateway: {}'.format(e))
            gateway.close()
            return None

        log_debug('Java Gateway initialized {}'.format(gateway))
        return gateway


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gateway-address', action='store')
    args = parser.parse_args()

    gateway_address = args.gateway_address.split(':')
    gateway_address = (gateway_address[0], int(gateway_address[1]))

    log_debug('Initializing PyExecutor at {}'.format(gateway_address))
    print(f"DEBUG: Starting PyExecutor with gateway address: {gateway_address}", file=sys.stderr)
    
    py_executor = PyExecutor(gateway_address=gateway_address)
    py_executor.run()
    log_debug('PyExecutor ended!')


if __name__ == '__main__':
    main()
