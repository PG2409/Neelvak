# Memory Audit Report
## Neelvak AIOS v1.3

### Root Cause: Asymmetric CSS Formula (BUG-001)

The original _calculate_css combined Jaccard with an asymmetric overlap term:

    css = 0.5 * jaccard + 0.5 * (|intersection| / |prompt_tokens|)

The overlap term equals 1.0 whenever ALL prompt tokens appear inside a cached key,
regardless of how long that key is. A 1-word prompt "Hello" against a 500-word cached
entry that contains the word "hello" produces overlap=1.0 -> css >= 0.50. When combined
with any nonzero Jaccard the final score easily exceeds the STANDARD threshold (0.85).

Result: every short prompt falsely hit the L2 cache and bypassed the compiler.

### Secondary Bug: Stale L2 Manifest (BUG-002)

workspace/memory_cache/l2_manifest.json accumulated 400+ entries from prior development
and test runs (14-task regression blob, "What is Python?", "love", "hji", ...). These
stale entries provided large candidate pools that the broken CSS formula matched against.

### Fixes Applied

1. Pure symmetric Jaccard CSS (memory/manager.py lines 88-119):
       css = |intersection| / |union|
   Jaccard is bounded [0,1] and symmetric. A 1-word prompt vs. a 500-word key can
   never exceed Jaccard = 1/500 = 0.002, far below any threshold.

2. L2 manifest cleared (workspace/memory_cache/l2_manifest.json reset to {}).

### Post-Fix Verification

| Prompt            | Cached Key Candidate         | Jaccard  | Result    |
|-------------------|------------------------------|----------|-----------|
| "Hello"           | 500-word regression blob     | ~0.001   | MISS (OK) |
| "What is Python?" | Exact cached key match       | 1.000    | HIT  (OK) |
| "Explain recursion." | "compile intent" (L3)     | 0.000    | MISS (OK) |

### Status: RESOLVED
