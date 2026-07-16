import pytest
import asyncio
from tests.chaos.injector import ChaosInjector
from runtime.scheduler import RuntimeScheduler
from contracts.workflow import WorkflowPlan, WorkflowNode, TaskControlBlock, CapabilityProfile
from models.health import ProviderHealthManager
from models.router import ModelRouter
from kernel.bus import EventBus

@pytest.fixture
def scheduler():
    health = ProviderHealthManager()
    router = ModelRouter(health)
    bus = EventBus()
    return RuntimeScheduler(router=router, event_bus=bus)

async def run_plan(scheduler, runtime_type):
    tcb = TaskControlBlock(
        workflow_id="chaos_plan",
        assigned_runtime=runtime_type,
        primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW")
    )
    node = WorkflowNode(node_id="test_node", dependencies=[], tcb=tcb)
    plan = WorkflowPlan(workflow_id="chaos_plan", nodes={"test_node": node})
    
    return await scheduler.schedule_workflow(plan, [["test_node"]])

@pytest.mark.asyncio
async def test_worker_crash_recovery(scheduler):
    with ChaosInjector({"chaos_worker_crash": True}):
        with pytest.raises(RuntimeError, match="Chaos: Worker crashed"):
            await run_plan(scheduler, "COMPETITIVE")

@pytest.mark.asyncio
async def test_looper_crash_recovery(scheduler):
    with ChaosInjector({"chaos_looper_crash": True}):
        with pytest.raises(RuntimeError, match="Chaos: Looper crashed"):
            await run_plan(scheduler, "COMPETITIVE")

@pytest.mark.asyncio
async def test_watcher_crash_recovery(scheduler):
    with ChaosInjector({"chaos_watcher_crash": True}):
        with pytest.raises(RuntimeError, match="Chaos: Watcher crashed"):
            await run_plan(scheduler, "COMPETITIVE")

@pytest.mark.asyncio
async def test_surveillance_crash_recovery(scheduler):
    with ChaosInjector({"chaos_surveillance_crash": True}):
        with pytest.raises(RuntimeError, match="Chaos: Surveillance crashed"):
            await run_plan(scheduler, "STANDARD")

@pytest.mark.asyncio
async def test_cancelled_asyncio_task(scheduler):
    with ChaosInjector({"chaos_sys_cancelled_task": True}):
        # MICRO runtime calls asyncio.sleep during retry loops.
        with pytest.raises(asyncio.CancelledError):
            await run_plan(scheduler, "MICRO")
