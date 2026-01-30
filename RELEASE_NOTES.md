# Seahorse Release 3.0.0.3

## ⚠️ Critical Requirement: JDK 11
This release is specifically configured to run **Spark 3.0.0 on JDK 11**. 
Ensure that all nodes (Driver, Workers, and Executors) are running **Java 11**.

Running on Java 8 is **not supported** with this configuration due to the use of Java 9+ specific flags (`--add-opens`).

## Changes
### Spark & Arrow Compatibility Fixes
- **Java 11 Support**: Resolved invalid memory access errors (`sun.misc.Unsafe`, `java.nio.DirectByteBuffer`) by:
  - Adding comprehensive `--add-opens` JVM flags to expose internal JDK modules to Spark and Arrow.
  - Enabling `-Dio.netty.tryReflectionSetAccessible=true` to allow Netty to bypass safe access checks via reflection.
  - These flags are applied to both the **Spark Executors** and the **SessionManager/WorkflowExecutor** (Driver) processes.

- **Arrow Compatibility**:
  - Reverted the internal Arrow upgrade to strictly use **Arrow 0.15.1**, matching the version bundled with Spark 3.0.0.
  - Pinned `pyarrow==0.15.1` in the python environment.
  - Added `ARROW_PRE_0_15_IPC_FORMAT=1` to ensure PyArrow uses the legacy IPC format expected by Spark.

- **Stability**:
  - Fixed an issue where improper quoting in `spark-defaults.conf` caused Spark Executors to crash on startup in remote clusters.
