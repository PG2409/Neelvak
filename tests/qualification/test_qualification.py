import pytest
import asyncio
import os
import json
from typing import Dict, Any, List

from runtime.scheduler import RuntimeScheduler
from contracts.workflow import WorkflowPlan, WorkflowNode, TaskControlBlock, CapabilityProfile
from contracts.message import EventMessage
from models.health import ProviderHealthManager
from models.router import ModelRouter
from kernel.bus import EventBus
from memory.manager import MemoryManager
from runtime.tool_manager import ToolManager
from tests.chaos.injector import ChaosInjector

async def _init_system_core():
    health = ProviderHealthManager()
    router = ModelRouter(health)
    bus = EventBus()
    memory = MemoryManager(cache_dir="workspace/qualification_cache")
    scheduler = RuntimeScheduler(router=router, event_bus=bus, memory_manager=memory)
    
    await bus.start()
    await health.start()
    return {
        "health": health,
        "router": router,
        "bus": bus,
        "memory": memory,
        "scheduler": scheduler
    }

async def _shutdown_system_core(core):
    await core["bus"].stop()
    await core["health"].stop()

class TestQualificationSuite:
    """Production Qualification Test Suite targeting end-to-end capabilities."""

    @pytest.mark.asyncio
    async def test_qualification_e2e_workflow(self):
        """End-to-End Operating System Validation with simulated workloads."""
        core = await _init_system_core()
        scheduler = core["scheduler"]
        
        # Workflow containing sequential dependency: N1 -> N2
        tcb_1 = TaskControlBlock(
            workflow_id="qual-e2e-1",
            assigned_runtime="STANDARD",
            primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW")
        )
        tcb_2 = TaskControlBlock(
            workflow_id="qual-e2e-1",
            assigned_runtime="DIRECT",
            primary_capability=CapabilityProfile(minimum_reasoning_tier="STANDARD")
        )
        node_1 = WorkflowNode(node_id="N1", dependencies=[], tcb=tcb_1)
        node_2 = WorkflowNode(node_id="N2", dependencies=["N1"], tcb=tcb_2)
        plan = WorkflowPlan(workflow_id="qual-e2e-1", nodes={"N1": node_1, "N2": node_2})
        
        sim_flags = {"chaos_network_latency": True, "latency_ms": 1}
        try:
            with ChaosInjector(sim_flags):
                results = await scheduler.schedule_workflow(plan, [["N1"], ["N2"]])
            assert "N1" in results
            assert "N2" in results
            assert results["N1"].winner == "Worker Agent"
        finally:
            await _shutdown_system_core(core)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("rt_type", ["STANDARD", "COMPETITIVE", "MICRO", "DIRECT", "RETRIEVAL"])
    async def test_runtimes_qualification(self, rt_type):
        """Qualifies Runtimes A through E individually under standard executions."""
        core = await _init_system_core()
        scheduler = core["scheduler"]
        
        tcb = TaskControlBlock(
            workflow_id=f"qual-rt-{rt_type}",
            assigned_runtime=rt_type,
            primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW")
        )
        node = WorkflowNode(node_id="N1", dependencies=[], tcb=tcb)
        plan = WorkflowPlan(workflow_id=f"qual-rt-{rt_type}", nodes={"N1": node})
        
        sim_flags = {"chaos_network_latency": True, "latency_ms": 1}
        try:
            with ChaosInjector(sim_flags):
                results = await scheduler.schedule_workflow(plan, [["N1"]])
            assert "N1" in results
        finally:
            await _shutdown_system_core(core)

    @pytest.mark.asyncio
    async def test_event_bus_qualification(self):
        """EventBus Communication Validation under volumetric priority publish calls."""
        core = await _init_system_core()
        bus = core["bus"]
        received = []
        
        async def cb(msg: EventMessage):
            received.append(msg)
            
        bus.subscribe("QUAL_BUS", cb)
        
        try:
            for i in range(10):
                msg = EventMessage(
                    sender_id="S1",
                    receiver_id="QUAL_BUS",
                    workflow_id="wf-1",
                    msg_type="EVENT",
                    event_name="TEST_QUAL",
                    priority=i % 3,  # mixed priorities
                    payload={"idx": i}
                )
                await bus.publish(msg)
                
            # Allow ample time for processing
            await asyncio.sleep(0.3)
            assert len(received) == 10
            bus.unsubscribe("QUAL_BUS", cb)
        finally:
            await _shutdown_system_core(core)

    @pytest.mark.asyncio
    async def test_deadlock_and_queue_starvation(self):
        """Validates scheduler semaphore fairness under concurrent spike loads."""
        core = await _init_system_core()
        scheduler = core["scheduler"]
        
        # Generate 50 concurrent tasks to verify queue locks & deadlocks
        tasks = []
        for i in range(50):
            tcb = TaskControlBlock(
                workflow_id=f"deadlock-wf-{i}",
                assigned_runtime="DIRECT",
                primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW")
            )
            node = WorkflowNode(node_id="N1", dependencies=[], tcb=tcb)
            plan = WorkflowPlan(workflow_id=f"deadlock-wf-{i}", nodes={"N1": node})
            tasks.append(plan)
            
        async def run_one(p):
            sim_flags = {"chaos_network_latency": True, "latency_ms": 1}
            with ChaosInjector(sim_flags):
                return await scheduler.schedule_workflow(p, [["N1"]])
                
        try:
            running_tasks = [asyncio.create_task(run_one(p)) for p in tasks]
            results = await asyncio.gather(*running_tasks)
            assert len(results) == 50
            assert all("N1" in r for r in results)
        finally:
            await _shutdown_system_core(core)

    @pytest.mark.asyncio
    async def test_tool_sandbox_security_qualification(self):
        """Tool Sandbox Security Validation for directory traversal attacks."""
        bus = EventBus()
        await bus.start()
        tool_mgr = ToolManager(event_bus=bus, workspace_root="workspace/sandbox_qual")
        tool_mgr.start()
        
        responses: List[EventMessage] = []
        async def response_listener(msg: EventMessage):
            responses.append(msg)
            
        bus.subscribe("TEST_CLIENT", response_listener)
        
        try:
            # 1. Test unauthorized tool blocking
            msg_unauth = EventMessage(
                sender_id="TEST_CLIENT",
                receiver_id="TOOL_MANAGER",
                workflow_id="wf-security",
                msg_type="COMMAND",
                event_name="EXECUTE_TOOL",
                payload={"tool": "unauthorized_tool", "params": {}, "tcb_id": "TCB-1"}
            )
            await bus.publish(msg_unauth)
            await asyncio.sleep(0.1)
            
            assert len(responses) == 1
            assert responses[0].event_name == "TOOL_FAILED"
            assert "not in the system permissions ring" in responses[0].payload["error"]
            
            # 2. Test directory traversal blocking
            msg_traversal = EventMessage(
                sender_id="TEST_CLIENT",
                receiver_id="TOOL_MANAGER",
                workflow_id="wf-security",
                msg_type="COMMAND",
                event_name="EXECUTE_TOOL",
                payload={"tool": "write_file", "params": {"filename": "../escaped.txt", "content": "hack"}, "tcb_id": "TCB-1"}
            )
            await bus.publish(msg_traversal)
            await asyncio.sleep(0.1)
            
            assert len(responses) == 2
            assert responses[1].event_name == "TOOL_FAILED"
            assert "Security Violation: Path traversal detected" in responses[1].payload["error"]
            
        finally:
            bus.unsubscribe("TEST_CLIENT", response_listener)
            await bus.stop()
