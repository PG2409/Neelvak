# AIOS System Performance Report
This report details the detailed performance profile of the Neelvak AIOS core subsystems under concurrent stress.

## Subsystem Latency Profile

### AI Compiler
  - P50: 0.2214 ms
  - P90: 0.2680 ms
  - P95: 0.3631 ms
  - P99: 0.4120 ms
  - Average: 0.2366 ms
  - Min: 0.2052 ms
  - Max: 0.4120 ms

### Policy Engine
  - P50: 0.0325 ms
  - P90: 0.0340 ms
  - P95: 0.0353 ms
  - P99: 0.0423 ms
  - Average: 0.0325 ms
  - Min: 0.0305 ms
  - Max: 0.0423 ms

### MemoryManager Cache Hits
  - P50: 0.2250 ms
  - P90: 0.3758 ms
  - P95: 0.3898 ms
  - P99: 0.4928 ms
  - Average: 0.2228 ms
  - Min: 0.0205 ms
  - Max: 0.4928 ms

### ModelRouter Resolution
  - P50: 0.0151 ms
  - P90: 0.0168 ms
  - P95: 0.0170 ms
  - P99: 0.0383 ms
  - Average: 0.0159 ms
  - Min: 0.0148 ms
  - Max: 0.0383 ms

### EventBus Message Publishing
  - P50: 0.0052 ms
  - P90: 0.0093 ms
  - P95: 0.0098 ms
  - P99: 0.0148 ms
  - Average: 0.0068 ms
  - Min: 0.0000 ms
  - Max: 27.5946 ms

### CheckpointManager Save & Load
  - P50: 12.8918 ms
  - P90: 16.4532 ms
  - P95: 16.6268 ms
  - P99: 24.0796 ms
  - Average: 13.1923 ms
  - Min: 7.2264 ms
  - Max: 24.0796 ms


## Execution Runtimes Latency (A-E)
- **Competitive (Runtime A)**: P50 326.72 ms | Avg 326.72 ms
- **Standard (Runtime B)**: P50 264.54 ms | Avg 264.46 ms
- **Micro (Runtime C)**: P50 15.51 ms | Avg 15.55 ms
- **Direct (Runtime D)**: P50 108.74 ms | Avg 108.78 ms
- **Retrieval (Runtime E)**: P50 0.1030 ms | Avg 0.1257 ms

## Resource Allocation
- **Environment Provisioning**: Average 0.81 ms
- **Environment Deprovisioning**: Average 0.77 ms
