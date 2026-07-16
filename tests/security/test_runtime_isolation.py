"""Runtime Isolation Security Validation Suite.

Validates:
- Invalid Runtime Assignment (via type checking)
- Invalid Capability Profiles (via type checking)
- Invalid Workflow Plans (PolicyEngine risk checks)
- Unauthorized Runtime Access
- Cross Runtime Memory Access
- Shared Workspace Mutation
"""

import pytest
import os
from runtime.factory import EnvironmentFactory
from memory.manager import MemoryManager
from pydantic import ValidationError
from contracts.workflow import WorkflowPlan, WorkflowNode, TaskControlBlock, CapabilityProfile

@pytest.fixture
def factory():
    return EnvironmentFactory()

def test_invalid_runtime_assignment():
    # Passing incorrect type (e.g. integer) to assigned_runtime
    with pytest.raises(ValidationError):
        TaskControlBlock(
            workflow_id="1",
            dependencies=[],
            assigned_runtime=[], # Invalid type (list instead of str)
            primary_capability=CapabilityProfile(
                minimum_reasoning_tier="STANDARD",
                needs_vision=False,
                needs_code_sandbox=False,
                context_window_minimum_k=8,
                cost_ceiling_usd=0.01
            ),
            timeout_ms=1000,
            payload={}
        )

def test_invalid_capability_profiles():
    # Passing incorrect type (e.g. list) to context_window_minimum_k
    with pytest.raises(ValidationError):
        CapabilityProfile(
            minimum_reasoning_tier="STANDARD",
            needs_vision=False,
            needs_code_sandbox=False,
            context_window_minimum_k="not_an_int", # Invalid type
            cost_ceiling_usd=0.02
        )

def test_invalid_workflow_plans():
    # Plan risk score exceeds limit in PolicyEngine
    from compiler.policy import PolicyEngine
    pe = PolicyEngine()
    plan = WorkflowPlan(
        workflow_id="bad_wf",
        nodes={},
        risk_score=99.0, # High risk score
        policy_flag="OK"
    )
    passed, msg = pe.validate_plan(plan, "test")
    assert not passed
    assert "Policy Violation" in msg

def test_unauthorized_runtime_access(factory):
    # Workflow A should not access directory for Workflow B
    wf_a = factory.provision_container("wf_a")
    wf_b = factory.provision_container("wf_b")
    
    assert wf_a["root"] != wf_b["root"]
    
    factory.deprovision_container("wf_a")
    factory.deprovision_container("wf_b")

def test_cross_runtime_memory_access():
    mgr = MemoryManager()
    mgr.store_cache("secret_data_wf_1", "flag{wf_1_secret}", scope="L1")
    
    hit, val, css = mgr.check_cache_hit("secret_data_wf_2", "STANDARD")
    assert not hit
    assert val is None

def test_shared_workspace_mutation(factory):
    wf_a = factory.provision_container("wf_a")
    wf_b = factory.provision_container("wf_b")
    
    file_a = os.path.join(wf_a["root"], "temp", "secret.txt")
    os.makedirs(os.path.dirname(file_a), exist_ok=True)
    with open(file_a, "w") as f:
        f.write("A_secret")
        
    file_b = os.path.join(wf_b["root"], "temp", "secret.txt")
    assert not os.path.exists(file_b)
    
    factory.deprovision_container("wf_a")
    factory.deprovision_container("wf_b")
