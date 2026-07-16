# Execution Repair Report
## Neelvak AIOS v1.3

### Summary of All Bugs Found and Fixed

---

## BUG-001: False Cache Hits (CRITICAL — Root Cause of Pipeline Short-Circuit)

File: memory/manager.py
Method: _calculate_css
Lines: 88-119

Problem:
  css = 0.5 * jaccard + 0.5 * overlap
  where overlap = |intersection| / |prompt_tokens|

  This asymmetric overlap term causes short prompts to match any long cached key
  that happens to contain one of their tokens. Result: css >= 0.85 for almost
  every short prompt, triggering a false cache hit that bypasses the entire
  compiler/scheduler/runtime pipeline.

Fix:
  css = |intersection| / |union|   (pure Jaccard)

Impact: Restored compiler execution for all fresh prompts.

---

## BUG-002: Stale L2 Manifest Cache Pollution (HIGH)

File: workspace/memory_cache/l2_manifest.json

Problem: 400+ stale entries from development/test runs provided false hit candidates.

Fix: Cleared manifest to {}.

Impact: Eliminated false positive cache hits from prior sessions.

---

## BUG-003: User Prompt Not Forwarded to Runtimes (HIGH)

File: compiler/compiler.py
Method: _pass_10_workflowplan_compilation
Line: 298

Problem:
  payload={"task_name": task.get("task", "")}
  
  Runtimes used payload.get("prompt", task_name). Without a "prompt" key,
  they forwarded the internal task label (e.g., "perform_cognitive_reasoning")
  to the LLM instead of the real user query.

Fix:
  payload={"task_name": task.get("task", ""), "prompt": user_intent}

Impact: LLMs now receive the actual user question.

---

## BUG-004: StandardRuntime Returns Hardcoded Stub (HIGH)

File: runtimes/standard.py
Method: _run_worker
Line: 133

Problem:
  return f"Standard worker completed: '{task_name}' successfully resolved.", tokens_used

  This stub was displayed in the UI because the verify_result_integrity task
  (ST_03, STANDARD runtime) sometimes got selected as the output node.

Fix:
  Replaced stub with _call_provider() httpx call. Preserved all simulation flags.

---

## BUG-005: CompetitiveRuntime Returns Hardcoded JSON Stub (HIGH)

File: runtimes/competitive.py
Methods: _run_worker_x, _run_looper_y

Problem:
  Both returned fabricated JSON strings instead of real provider responses.
  The Watching Agent evaluated these stubs, selecting one as the "winner."
  Output to the user was the internal stub text, not an LLM answer.

Fix:
  Added _call_provider() httpx method. Both worker paths now call the provider.
  Looper Y still runs its critique loop (now iterating after a real first inference).

---

## BUG-006: ResponseFormatter Does Not Unwrap JSON Envelope (MEDIUM)

File: gateway/formatter.py
Method: clean_output

Problem:
  CompetitiveRuntime output is wrapped: {"status":"success","result":"actual answer"}
  The formatter passed this raw JSON string to the frontend unchanged.

Fix:
  Attempt JSON parse; if result key exists, extract it before further scrubbing.

---

## BUG-007: Verification Node Occasionally Selected as Output (LOW — pre-fixed)

File: gateway/server.py
Lines: 211-224

Problem:
  Result node selection checked task_name for "verify" but not the node ID.
  ST_03 could still be selected if task_name was not exactly "verify_result_integrity".

Fix (prior session):
  Added check: "verify" not in n_id.lower()

---

## Files Modified

1. memory/manager.py           — BUG-001 fix
2. workspace/memory_cache/l2_manifest.json — BUG-002 fix
3. compiler/compiler.py        — BUG-003 fix
4. runtimes/standard.py        — BUG-004 fix
5. runtimes/competitive.py     — BUG-005 fix
6. gateway/formatter.py        — BUG-006 fix
7. gateway/server.py           — BUG-007 fix (prior session)

---

## Status: ALL BUGS RESOLVED
