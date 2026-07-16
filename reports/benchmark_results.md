# AIOS Subsystem Benchmark Results
Collected on: July 3, 2026

## Modular Subsystem Performance Matrix
| Subsystem | Count | P50 (ms) | P90 (ms) | P95 (ms) | P99 (ms) | Max (ms) |
|---|---|---|---|---|---|---|
| Compiler | 50 | 0.221 | 0.268 | 0.363 | 0.412 | 0.412 |
| Policy Engine | 100 | 0.032 | 0.034 | 0.035 | 0.042 | 0.042 |
| Memory Check | 100 | 0.225 | 0.376 | 0.390 | 0.493 | 0.493 |
| Model Router | 100 | 0.015 | 0.017 | 0.017 | 0.038 | 0.038 |
| Checkpoint Mgr | 50 | 12.892 | 16.453 | 16.627 | 24.080 | 24.080 |
| Gateway Request | 50 | 1.424 | 607.757 | 608.559 | 609.396 | 609.396 |
| Tool Manager | 100 | 0.134 | 0.162 | 0.186 | 0.580 | 0.580 |
