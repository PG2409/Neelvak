import pytest
from compiler.planner import ExecutionPlanner, CostOptimizer
from contracts.workflow import WorkflowPlan, WorkflowNode, TaskControlBlock, CapabilityProfile

def test_math_cost_truncation_downgrade():
    """Verify CostOptimizer mathematically truncates to DIRECT/zero-overhead when wallet is depleted."""
    opt = CostOptimizer()
    
    tcb = TaskControlBlock(
        workflow_id="wf-1",
        assigned_runtime="COMPETITIVE",
        primary_capability=CapabilityProfile(
            minimum_reasoning_tier="HIGH",
            cost_ceiling_usd=0.05
        )
    )
    plan = WorkflowPlan(
        workflow_id="wf-1",
        nodes={"ST_01": WorkflowNode(node_id="ST_01", tcb=tcb)}
    )
    
    # Simulate a depleted wallet
    remaining_budget = 0.0
    new_plan = opt.optimize_plan_budgets(plan, remaining_budget)
    
    new_tcb = new_plan.nodes["ST_01"].tcb
    assert new_tcb.assigned_runtime == "DIRECT"
    assert new_tcb.primary_capability.minimum_reasoning_tier == "LOW"
    assert new_tcb.primary_capability.cost_ceiling_usd == 0.0

def test_parallel_sequencing_validity():
    """Verify ExecutionPlanner accurately structures parallel=True and parallel=False layers."""
    planner = ExecutionPlanner()
    
    # Create DAG: ST_01, ST_02 -> ST_03 -> ST_04, ST_05
    plan = WorkflowPlan(
        workflow_id="wf-seq",
        nodes={
            "ST_01": WorkflowNode(node_id="ST_01", dependencies=[], tcb=TaskControlBlock(workflow_id="wf-seq", assigned_runtime="STANDARD", primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW"))),
            "ST_02": WorkflowNode(node_id="ST_02", dependencies=[], tcb=TaskControlBlock(workflow_id="wf-seq", assigned_runtime="STANDARD", primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW"))),
            "ST_03": WorkflowNode(node_id="ST_03", dependencies=["ST_01", "ST_02"], tcb=TaskControlBlock(workflow_id="wf-seq", assigned_runtime="STANDARD", primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW"))),
            "ST_04": WorkflowNode(node_id="ST_04", dependencies=["ST_03"], tcb=TaskControlBlock(workflow_id="wf-seq", assigned_runtime="STANDARD", primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW"))),
            "ST_05": WorkflowNode(node_id="ST_05", dependencies=["ST_03"], tcb=TaskControlBlock(workflow_id="wf-seq", assigned_runtime="STANDARD", primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW")))
        }
    )
    
    layers = planner.plan_execution_layers(plan)
    
    assert len(layers) == 3
    
    # Layer 0: ST_01 and ST_02 (parallel=True)
    layer0 = layers[0]
    assert set(layer0["nodes"]) == {"ST_01", "ST_02"}
    assert layer0["parallel"] is True
    
    # Layer 1: ST_03 (parallel=False)
    layer1 = layers[1]
    assert set(layer1["nodes"]) == {"ST_03"}
    assert layer1["parallel"] is False
    
    # Layer 2: ST_04 and ST_05 (parallel=True)
    layer2 = layers[2]
    assert set(layer2["nodes"]) == {"ST_04", "ST_05"}
    assert layer2["parallel"] is True
