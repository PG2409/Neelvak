import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from runtime.scheduler import RuntimeScheduler
from contracts.workflow import WorkflowPlan, WorkflowNode, TaskControlBlock, CapabilityProfile, EvaluationReport

@pytest.fixture
def mock_config():
    with patch("runtime.scheduler.config") as mock_conf:
        mock_conf.MAX_CONCURRENT_RUNTIMES = 2
        yield mock_conf

@pytest.fixture
def scheduler(mock_config):
    # This initializes RuntimeScheduler with MAX_CONCURRENT_RUNTIMES = 2
    return RuntimeScheduler()

@pytest.mark.asyncio
async def test_dynamic_concurrency_cap(scheduler):
    """Verify that exactly MAX_CONCURRENT_RUNTIMES tasks acquire the semaphore simultaneously."""
    
    # We will mock the _instantiate_runtime to return a mock runtime that hangs until we release it
    hanging_event = asyncio.Event()
    active_executions = 0
    max_active = 0
    
    class MockHangingRuntime:
        async def validate(self, tcb): return True
        async def initialize(self, payload): pass
        async def execute(self):
            nonlocal active_executions, max_active
            active_executions += 1
            max_active = max(max_active, active_executions)
            await hanging_event.wait()
            active_executions -= 1
            return EvaluationReport(winner="MOCK", confidence=0.99, reason="test")
        async def cleanup(self): pass
        async def terminate(self): pass
        
    scheduler._instantiate_runtime = MagicMock(return_value=MockHangingRuntime())
    
    # Create 10 independent nodes for layer 1
    nodes = {}
    for i in range(10):
        tcb = TaskControlBlock(
            workflow_id="wf-test-cap",
            assigned_runtime="STANDARD",
            primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW")
        )
        nodes[f"node_{i}"] = WorkflowNode(node_id=f"node_{i}", tcb=tcb)
        
    plan = WorkflowPlan(workflow_id="wf-test-cap", nodes=nodes)
    layer = [[f"node_{i}" for i in range(10)]]
    
    # Start scheduler task
    scheduler_task = asyncio.create_task(scheduler.schedule_workflow(plan, layer))
    
    # Give it time to hit the concurrency limit
    await asyncio.sleep(0.1)
    
    # Exactly 2 should be executing
    assert active_executions == 2
    assert max_active == 2
    
    # Release the hang and let it finish
    hanging_event.set()
    await scheduler_task
    
    # Ensure it never exceeded 2 active concurrently
    assert max_active == 2

@pytest.mark.asyncio
async def test_contract_life_verification(scheduler):
    """Verify finally block executes cleanups despite a fatal runtime exception."""
    
    cleanup_called = False
    
    class MockCrashingRuntime:
        async def validate(self, tcb): return True
        async def initialize(self, payload): pass
        async def execute(self):
            raise RuntimeError("Fatal internal crash")
        async def cleanup(self):
            nonlocal cleanup_called
            cleanup_called = True
        async def terminate(self): pass
        
    scheduler._instantiate_runtime = MagicMock(return_value=MockCrashingRuntime())
    scheduler._factory.recycle_container = MagicMock()
    
    tcb = TaskControlBlock(
        workflow_id="wf-crash",
        assigned_runtime="COMPETITIVE",
        primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW")
    )
    node = WorkflowNode(node_id="node_crash", tcb=tcb)
    plan = WorkflowPlan(workflow_id="wf-crash", nodes={"node_crash": node})
    
    with pytest.raises(RuntimeError, match="Fatal internal crash"):
        await scheduler.schedule_workflow(plan, [["node_crash"]])
        
    # Assert cleanup was called from finally block
    assert cleanup_called is True
    scheduler._factory.recycle_container.assert_called_once_with("wf-crash")

@pytest.mark.asyncio
async def test_clean_type_matching(scheduler):
    """Verify invalid assigned_runtime is caught instantly during validation."""
    
    tcb = TaskControlBlock(
        workflow_id="wf-invalid",
        assigned_runtime="INVALID_TYPE",
        primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW")
    )
    node = WorkflowNode(node_id="node_inv", tcb=tcb)
    plan = WorkflowPlan(workflow_id="wf-invalid", nodes={"node_inv": node})
    
    # Should raise ValueError for unknown runtime assignment
    with pytest.raises(ValueError, match="Unknown runtime assignment 'INVALID_TYPE'"):
        await scheduler.schedule_workflow(plan, [["node_inv"]])
        
    # Check that lifecycle manager logged it as FAILED (via get internal logic or simply that exception threw correctly)
    # The scheduler transitions to FAILED upon catching ValueError
