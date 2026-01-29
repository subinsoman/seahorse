# Seahorse Workflow Executor

The Seahorse Workflow Executor is the backend engine responsible for executing data processing workflows designed in the Seahorse visual editor. It leverages Apache Spark to run scalable data pipelines.

## Repository Details
| Product Group | Module Name | Name | Description |
|---------------|-------------|------------------|-------------|
| magik | ae | ae-seahorse-svc | Seahorse Workflow Execution Service |

## Release Notes

### Version 3.0.0.2 (Recommended)
This release introduces critical stability and security fixes:

#### 1. Dependency Fixes
- **Guice & JClouds Compatibility**: 
  - Upgraded `jclouds` from `1.9.0` to `2.1.0`.
  - This resolves the `java.lang.NoClassDefFoundError: com/google/inject/internal/util/$Preconditions` crash caused by a conflict with Guice 4.0.
- **RabbitMQ**: Removed duplicate dependency entries in `workflowexecutor`.

#### 2. Security Improvements
- **Log4j Upgrade**: 
  - All components now use **Log4j 2.17.2** (migrated from vulnerable Log4j 1.x configurations).
  - Added secure `log4j2.xml` configuration files for all services.

#### 3. Runtime Environment
- **Java 11 Support**:
  - Validated build compatibility with OpenJDK 11.
  - Updated Dockerfiles (e.g., `spark-standalone-cluster`) to use `openjdk-11-jdk` / `openjdk-11-jre`.

## Build Instructions

### Prerequisites
- **Java Development Kit (JDK) 11**: Ensure `JAVA_HOME` points to a JDK 11 installation.
- **SBT**: Scala Build Tool.

### Compilation
To compile the project:
```bash
sbt compile
```

### Testing
To run unit tests for the workflow manager:
```bash
sbt workflowmanager/test
```