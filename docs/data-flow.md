# Data Flow

```mermaid
sequenceDiagram
    participant User
    participant Backend as Backend (Phase 3)
    participant Kafka as Kafka Plugin (Phase 4)
    participant Spark as Spark Job (Phase 5)
    participant HDFS as HDFS Client (Phase 6)

    User->>Backend: Upload CSV Data
    Backend->>Backend: Validate Data
    Backend->>Kafka: Publish records
    Kafka-->>Backend: Ack
    Spark->>Kafka: Consume records
    Spark->>Spark: Transform Data
    Spark->>HDFS: Write processed data (Parquet)
    HDFS-->>Spark: Ack
```

This sequence covers the primary path of a data record through the system. Refer to the respective phase code (e.g., CsvSourcePlugin, Spark jobs, WebHDFS client) for implementation details.
