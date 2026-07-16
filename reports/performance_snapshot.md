# Performance Baseline

| Subsystem | Average (ms) | P50 (ms) | P90 (ms) | P95 (ms) | P99 (ms) | Max (ms) |
|-----------|--------------|----------|----------|----------|----------|----------|
| Compiler  | 1.2          | 1.1      | 2.3      | 3.1      | 5.2      | 12.1     |
| Scheduler | 0.8          | 0.7      | 1.1      | 1.8      | 3.0      | 5.4      |
| Gateway   | 1.5          | 1.2      | 2.8      | 4.2      | 8.1      | 18.0     |
| Memory    | 0.4          | 0.3      | 0.9      | 1.2      | 2.5      | 4.1      |
| EventBus  | 0.2          | 0.1      | 0.4      | 0.7      | 1.1      | 2.8      |
| Checkpoint| 2.1          | 1.9      | 3.5      | 5.0      | 9.8      | 14.2     |

Overall Gateway latency remains strictly bound under 20ms maximum observed.
