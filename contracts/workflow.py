"""Workflow structures, Task Control Blocks, and evaluation records.

Unified representations used across compilation and scheduling.
"""

import time
import uuid
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class CapabilityProfile(BaseModel):
    """Abstract capability configuration profile for runtime selection."""
    minimum_reasoning_tier: str  # "LOW" | "STANDARD" | "HIGH" | "DEEP_REASONING"
    needs_vision: bool = False
    needs_code_sandbox: bool = False
    context_window_minimum_k: int = 8
    cost_ceiling_usd: float = 0.02
    diversity_group_id: Optional[str] = None

class TaskControlBlock(BaseModel):
    """TCB capturing constraints and execution scopes for an individual node."""
    tcb_id: str = Field(default_factory=lambda: f"TCB_{str(uuid.uuid4())[:8].upper()}")
    workflow_id: str
    dependencies: List[str] = Field(default_factory=list)
    priority_weight: int = 100
    assigned_runtime: str       # "COMPETITIVE" | "STANDARD" | "MICRO" | "DIRECT" | "RETRIEVAL"
    primary_capability: CapabilityProfile
    adversarial_capability: Optional[CapabilityProfile] = None
    timeout_ms: int = 30000
    max_retries: int = 3
    checkpoint_policy: str = "ON_STAGE_COMPLETION"
    payload: Dict[str, Any] = Field(default_factory=dict)

class WorkflowNode(BaseModel):
    """Single step in an execution plan topology."""
    node_id: str
    dependencies: List[str] = Field(default_factory=list)
    tcb: TaskControlBlock

class WorkflowPlan(BaseModel):
    """Compiled immutable execution plan topology containing multiple nodes."""
    workflow_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version: str = "1.0.0"
    compiler_version: str = "1.2.0"
    policy_version: str = "1.2.0"
    runtime_version: str = "1.2.0"
    nodes: Dict[str, WorkflowNode] = Field(default_factory=dict)
    risk_score: float = 0.0
    policy_flag: str = "OK"
    compiled_at: float = Field(default_factory=time.time)

class RuntimeResult(BaseModel):
    """The complete metrics tracing record from a runtime execution."""
    output: str
    winner: str
    confidence: float
    reason: str
    provider: str
    model: str
    token_usage: Dict[str, int] = Field(default_factory=dict)
    estimated_cost_usd: float = 0.0
    latency_ms: float = 0.0
    checkpoint_id: Optional[str] = None
    runtime_type: str
    metrics: Dict[str, Any] = Field(default_factory=dict)

class EvaluationReport(BaseModel):
    """Structured evaluation report containing style, accuracy, and confidence metrics."""
    winner: str
    confidence: float
    reason: str
    metrics: Dict[str, Any] = Field(default_factory=dict)

class ProviderDecision(BaseModel):
    """Structured outcome of ModelRouter evaluations across 13 factors."""
    reasoning_tier: str
    context_window_k: int
    vision_support: bool
    tool_support: bool
    budget_usd: float
    estimated_latency_ms: float
    health_status: str
    quota_remaining: float
    historical_success_rate: float
    historical_latency_ms: float
    queue_depth: int
    estimated_cost_usd: float
    fallback_rules_applied: bool
    selected_provider: str
    selected_model: str
    routing_chain: List[Dict[str, Any]] = Field(default_factory=list)

class RuntimeDecision(BaseModel):
    """Structured outcome of RuntimeScheduler execution mapping."""
    candidate_runtimes: List[str]
    selected_runtime: str
    selection_score: float
    reason: str
    estimated_cost_usd: float
    estimated_latency_ms: float
    capability_match_score: float
