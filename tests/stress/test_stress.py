"""Infrastructure Stress Qualification Framework test suites."""

import pytest
import asyncio
import time
import os
import shutil
import uuid
from typing import Dict, Any

from tests.stress.metrics import tracker

from kernel.bus import EventBus
from kernel.registry import AgentRegistry
from kernel.lifecycle import LifecycleManager
from storage.checkpoints import CheckpointManager
from contracts.message import EventMessage
from runtime.factory import EnvironmentFactory
from runtime.tool_manager import ToolManager
from runtime.scheduler import RuntimeScheduler
from contracts.workflow import WorkflowPlan, WorkflowNode, TaskControlBlock, CapabilityProfile
from compiler.compiler import AICompiler
from memory.manager import MemoryManager
from models.router import ModelRouter
from models.health import ProviderHealthManager

pytestmark = pytest.mark.asyncio

@pytest.fixture(autouse=True)
def setup_metrics():
    tracker.start_memory_tracking()
    yield
    tracker.stop_memory_tracking()

class TestEventBusStress:
    """Section 1: EventBus Stress Qualification"""
    
    @pytest.mark.parametrize("num_publishers, num_subscribers, num_messages", [
        (100, 100, 10000),
        (500, 500, 50000),
        (1000, 1000, 100000)
    ])
    async def test_eventbus_throughput(self, num_publishers, num_subscribers, num_messages):
        bus = EventBus()
        await bus.start()
        
        received_messages = []
        
        async def subscriber_callback(msg: EventMessage):
            # simulate light processing delay for realistic backpressure
            received_messages.append(msg.message_id)
        
        for i in range(num_subscribers):
            bus.subscribe(f"CHANNEL_{i % 10}", subscriber_callback)
            
        async def publisher_task(pub_id: int):
            for i in range(num_messages // num_publishers):
                msg = EventMessage(
                    sender_id=f"PUB_{pub_id}",
                    receiver_id=f"CHANNEL_{pub_id % 10}",
                    workflow_id="W_STRESS",
                    msg_type="EVENT",
                    event_name="STRESS_PING",
                    payload={"id": i}
                )
                start = time.time()
                await bus.publish(msg)
                tracker.record_latency("eventbus_publish", time.time() - start)
        
        start_time = time.time()
        tracker.snapshot_memory(f"before_eventbus_publish_{num_messages}")
        
        tasks = [asyncio.create_task(publisher_task(i)) for i in range(num_publishers)]
        await asyncio.gather(*tasks)
        
        # Wait for queue to drain
        while not bus._queue.empty():
            await asyncio.sleep(0.1)
            
        end_time = time.time()
        tracker.snapshot_memory(f"after_eventbus_publish_{num_messages}")
        
        # Cleanup
        await bus.stop()
        
        expected_received = num_messages * (num_subscribers // 10)
        assert len(received_messages) == expected_received
        tracker.increment("eventbus_total_messages", num_messages)
        tracker.record_latency("eventbus_total_duration", end_time - start_time)

class TestRegistryStress:
    """Section 3: Registry Stress Qualification"""
    
    @pytest.mark.parametrize("num_pcbs", [100, 1000, 5000])
    async def test_registry_lock_contention(self, num_pcbs):
        registry = AgentRegistry()
        
        async def insert_worker(i: int):
            start = time.time()
            await registry.register(f"PCB_{i}", {"state": "INIT", "data": "stress"})
            tracker.record_latency("registry_insert", time.time() - start)
            
        async def update_worker(i: int):
            start = time.time()
            await registry.update_state(f"PCB_{i}", "RUNNING")
            tracker.record_latency("registry_update", time.time() - start)
            
        async def remove_worker(i: int):
            start = time.time()
            await registry.remove(f"PCB_{i}")
            tracker.record_latency("registry_remove", time.time() - start)
            
        # Parallel Insert
        tasks = [asyncio.create_task(insert_worker(i)) for i in range(num_pcbs)]
        await asyncio.gather(*tasks)
        
        assert len(await registry.get_all()) == num_pcbs
        
        # Parallel Update
        tasks = [asyncio.create_task(update_worker(i)) for i in range(num_pcbs)]
        await asyncio.gather(*tasks)
        
        tracker.snapshot_memory(f"registry_peak_{num_pcbs}")
        
        # Parallel Remove
        tasks = [asyncio.create_task(remove_worker(i)) for i in range(num_pcbs)]
        await asyncio.gather(*tasks)
        
        assert len(await registry.get_all()) == 0

class TestSandboxStress:
    """Section 5 & 6: Environment and Tool Sandbox Stress"""
    
    @pytest.mark.parametrize("num_envs", [100, 500])
    async def test_environment_provisioning_cleanup(self, num_envs):
        factory = EnvironmentFactory(base_workspace="tests/stress_workspace")
        
        start_time = time.time()
        envs = []
        for i in range(num_envs):
            wid = f"stress_env_{i}_{uuid.uuid4().hex[:6]}"
            envs.append(wid)
            s = time.time()
            factory.provision_container(wid)
            tracker.record_latency("env_provision", time.time() - s)
            
        tracker.snapshot_memory(f"envs_provisioned_{num_envs}")
            
        # Deprovision
        for wid in envs:
            s = time.time()
            factory.deprovision_container(wid)
            tracker.record_latency("env_deprovision", time.time() - s)
            
        end_time = time.time()
        tracker.record_latency("env_total_duration", end_time - start_time)
        
        if os.path.exists("tests/stress_workspace"):
            assert len(os.listdir("tests/stress_workspace")) == 0
            shutil.rmtree("tests/stress_workspace", ignore_errors=True)

class TestSchedulerStress:
    """Section 2: Scheduler Stress Qualification"""
    
    @pytest.mark.parametrize("num_workflows", [100, 500])
    async def test_scheduler_fairness(self, num_workflows):
        bus = EventBus()
        await bus.start()
        
        health_manager = ProviderHealthManager()
        await health_manager.start()
        
        router = ModelRouter(health_manager)
        memory = MemoryManager()
        
        scheduler = RuntimeScheduler(router=router, event_bus=bus, memory_manager=memory)
        
        async def run_workflow(w_id: str):
            plan = WorkflowPlan(workflow_id=w_id, nodes={
                "NODE_1": WorkflowNode(
                    node_id="NODE_1",
                    tcb=TaskControlBlock(
                        workflow_id=w_id,
                        assigned_runtime="STANDARD", 
                        primary_capability=CapabilityProfile(minimum_reasoning_tier="STANDARD")
                    )
                )
            }, edges=[])
            
            start = time.time()
            await scheduler.schedule_workflow(plan, [["NODE_1"]])
            tracker.record_latency("scheduler_workflow_completion", time.time() - start)
            
        start_time = time.time()
        tasks = [asyncio.create_task(run_workflow(f"W_{i}")) for i in range(num_workflows)]
        
        await asyncio.gather(*tasks)
        end_time = time.time()
        
        tracker.record_latency("scheduler_total_duration", end_time - start_time)
        tracker.increment("scheduler_workflows_executed", num_workflows)
        tracker.snapshot_memory(f"scheduler_peak_{num_workflows}")
        
        await bus.stop()
        await health_manager.stop()

class TestResourceExhaustion:
    """Section 8: Resource Exhaustion"""
    
    async def test_scheduler_queue_exhaustion(self):
        """Simulates extreme load over queue capacity to test degradation."""
        bus = EventBus()
        await bus.start()
        
        # Bombard EventBus with unconsumed messages
        num_messages = 200000
        start = time.time()
        for i in range(num_messages):
            await bus.publish(EventMessage(
                sender_id="FLOOD",
                receiver_id="NOWHERE",
                workflow_id="W_EXHAUST",
                msg_type="EVENT",
                event_name="FLOOD"
            ))
        tracker.record_latency("exhaustion_flood_time", time.time() - start)
        
        tracker.snapshot_memory("exhaustion_peak")
        
        assert bus._queue.qsize() == num_messages
        await bus.stop()
        
        assert bus._queue.qsize() == num_messages
        bus._queue = asyncio.PriorityQueue()
        
        tracker.snapshot_memory("exhaustion_cleanup")

def pytest_sessionfinish(session, exitstatus):
    """Dump metrics at the end of the test session."""
    tracker.dump_metrics("tests/stress/reports/metrics.json")
