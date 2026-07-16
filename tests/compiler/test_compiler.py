import pytest
import asyncio
from unittest.mock import patch
from compiler.compiler import AICompiler
from contracts.workflow import WorkflowPlan

@pytest.mark.asyncio
async def test_compiler_immutability():
    """Verify that inputs are not mutated during passes."""
    compiler = AICompiler(api_key_groq="mock-key")
    
    # Run the full pipeline
    plan = await compiler.compile("Run an evaluation on the dataset.")
    
    # Verify that plan has been compiled correctly
    assert isinstance(plan, WorkflowPlan)
    assert plan.policy_flag == "OK"
    assert len(plan.nodes) > 0
    
    # Internally check immutability in _pass_4_workflow_optimization
    ir_v2 = {
        "semantic_subtasks": [
            {"step_id": "ST_01", "task": "a", "dependencies": []}
        ]
    }
    deps = {"ST_01": []}
    optimized = compiler._pass_4_workflow_optimization(ir_v2, deps)
    
    # The output shouldn't be the same object references
    assert id(optimized[0]) != id(ir_v2["semantic_subtasks"][0])
    
@pytest.mark.asyncio
async def test_routing_precision():
    """Verify that profiles properly map to runtimes and capabilities."""
    compiler = AICompiler(api_key_groq="mock-key")
    
    # Directly test pass 8 logic
    graph = [
        {"step_id": "T1", "profile": "heavy"},
        {"step_id": "T2", "profile": "retrieval"},
        {"step_id": "T3", "profile": "fast"}
    ]
    budgets = {"T1": 0.05, "T2": 0.001, "T3": 0.01}
    runtimes = compiler._pass_8_runtime_selection(graph, budgets)
    
    assert runtimes["T1"] == "COMPETITIVE"
    assert runtimes["T2"] == "RETRIEVAL"
    assert runtimes["T3"] == "STANDARD"

@pytest.mark.asyncio
async def test_error_resiliency():
    """Verify that LLM network errors fallback gracefully."""
    compiler = AICompiler(api_key_groq="valid-key-but-will-fail")
    
    with patch("httpx.AsyncClient.post", side_effect=Exception("Network Error")):
        plan = await compiler.compile("Do something.")
        
        # Should gracefully return a fallback plan
        assert plan.policy_flag == "OK"
        # Since it fell back, it should have the fallback task 'fallback_task' mapped to ST_01
        assert "ST_01" in plan.nodes
        assert plan.nodes["ST_01"].tcb.assigned_runtime == "STANDARD"
