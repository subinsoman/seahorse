# Troubleshooting and Optimizing Python Transformation Jobs

This document addresses common issues causing Python transformation jobs to execute continuously or fail silently, and details the fixes and best practices to resolve them.

## 1. Common Issues

### A. Infinite Loops in User Code
The system currently does not enforce a strict timeout on Python code execution. If the user's `transform` function (or global script scope) contains an infinite loop, the execution will hang indefinitely.

*   **Symptom**: Job state remains "Running" for hours.
*   **Cause**: `while True` or non-terminating recursion in user code.
*   **System Behavior**: The Scala backend uses `Duration.Inf` (infinite timeout) when waiting for the Python execution to complete, so it will not automatically intervene.

### B. Process Crash & Zombie State (Critical)
The `PythonExecutionCaretaker` is designed to automatically restart the Python process if it crashes (e.g., due to an **Out Of Memory (OOM)** error).

*   **The Problem**: The workflow execution logic in `ContextualCustomCodeExecutor` waits for a specific callback (`executionCompleted` or `executionFailed`) from the Python process.
*   **Scenario**:
    1.  Python process runs user code.
    2.  Process hits OOM and crashes *before* sending a callback.
    3.  `PythonExecutionCaretaker` restarts the Python process.
    4.  The *new* Python process has no knowledge of the previous job state.
    5.  The Scala backend continues waiting for a callback that will never come.
*   **Result**: The system hangs in a "zombie" wait state.

### C. Inefficient Data Conversion (Pandas & `to_json`)
A major cause of OOM crashes is inefficient data conversion between Spark and Pandas.

*   **Legacy Behavior**: Previous implementations or inefficient user code might rely on converting Spark DataFrames to Pandas by serializing the entire dataset to a JSON string (using `to_json` or similar intermediate formats) and loading it into memory.
*   **Impact**:
    *   Loading the entire dataset into memory as a JSON string is extremely memory-intensive.
    *   This causes frequent OOM errors, triggering the "Zombie State" scenario described above.
    *   Processing times become extremely slow due to serialization overhead.

## 2. Fixes and Optimizations

To address the **Inefficient Data Conversion** and associated OOM crashes, the following fixes have been implemented in the `CodeExecutor`:

### A. Enabling Arrow Optimization
We have explicitly enabled Apache Arrow optimization for PySpark. This significantly improves performance and reduces memory footprint when converting between Spark and Pandas DataFrames.

**Implementation**:
```python
# In code_executor.py
new_spark_session.conf.set("spark.sql.execution.arrow.pyspark.enabled", "true")
```

### B. Leveraging Spark Defaults over `to_json`
We have moved away from manual or JSON-based serialization methods. The system now utilizes Spark's native `createDataFrame` method, which interacts more efficiently with Pandas (especially when Arrow is enabled).

**Optimized Logic**:
```python
# code_executor.py
if self.is_pandas_available and isinstance(data, pandas.DataFrame):
    print("DEBUG: Converting pandas DataFrame to Spark DataFrame using native createDataFrame", file=sys.stderr)
    return spark_session.createDataFrame(data)
```
This avoids the overhead of intermediate JSON string generation.

### C. Avoiding RDD Round-trips
The implementation now attempts to use temporary views or direct DataFrame creation `_wrapped` context to avoid expensive RDD serialization round-trips where possible.

## 3. Recommendations for Users

1.  **Check Backend Logs**: Look for messages like `"PyExecutor exited with code..."` followed by a restart. This confirms your job is crashing (likely OOM) and entering the zombie state.
2.  **Optimize User Code**:
    *   Avoid converting massive DataFrames to Pandas (`toPandas()`) if the dataset exceeds available memory.
    *   Use Spark's native transformations (`pyspark.sql.functions`) whenever possible.
3.  **Monitor Memory**: Ensure the executor memory is sufficient for the volume of data being converted to Pandas.

## 4. Future Improvements
*   **Timeouts**: Implement a configurable timeout for Python execution in the Scala backend to prevent infinite waits.
*   **Crash Detection**: Enhance the backend to detect Python process restarts and fail the pending job immediately instead of waiting indefinitely.
