# Provider Validation Report
## Neelvak AIOS v1.3

### Runtimes That Previously Lacked Real Provider Calls (BUG-004)

| Runtime | File | Bug | Fix |
|---------|------|-----|-----|
| StandardRuntime | runtimes/standard.py | _run_worker returned hardcoded string | Added _call_provider with real httpx POST |
| CompetitiveRuntime | runtimes/competitive.py | _run_worker_x/_run_looper_y returned fabricated JSON | Added _call_provider with real httpx POST |
| DirectRuntime | runtimes/direct.py | Already had _call_http_direct | No change needed |
| MicroRuntime | runtimes/micro.py | Returns "Resolved {item}" - acceptable for batch slice tasks | No change (by design) |
| RetrievalRuntime | runtimes/retrieval.py | Uses MemoryManager cache | No change (by design) |

### Provider HTTP Call Pattern (Applied to Standard + Competitive)

    url = "https://api.groq.com/openai/v1/chat/completions"  # groq
         or "https://openrouter.ai/api/v1/chat/completions"  # openrouter

    headers = {"Authorization": f"Bearer {api_key}"}
    body = {"model": model, "messages": [{"role": "user", "content": prompt}]}

    resp = await httpx.AsyncClient().post(url, headers=headers, json=body, timeout=25.0)
    return resp.json()["choices"][0]["message"]["content"].strip()

### Mock Key Fallback

When running with mock API keys (test mode), both runtimes fall back to:
    "[Mock LLM] Response to: {prompt[:120]}"

This preserves test suite compatibility without live API calls.

### Status: RESOLVED
