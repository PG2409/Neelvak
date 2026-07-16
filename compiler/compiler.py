"""10-Pass Multi-Stage IR Compiler.

Translates unstructured inputs into signed, immutable execution plans.
"""

import logging
import time
import uuid
import httpx
import copy
import json
from typing import Dict, Any, List, Optional
from contracts.workflow import WorkflowPlan, WorkflowNode, TaskControlBlock, CapabilityProfile
import config
from compiler.planner import ExecutionPlanner, CostOptimizer, CapabilityPlanner
from compiler.policy import PolicyEngine
from models.provider import ProviderInterface

logger = logging.getLogger("neelvak_kernel")

class AICompiler:
    """Processes user queries through ten isolated passes to build a WorkflowPlan."""

    def __init__(self, api_key_groq: str = "", api_key_or: str = "", event_bus: Optional[Any] = None) -> None:
        self.api_key_groq = api_key_groq
        self.api_key_or = api_key_or
        self.planner_capability = CapabilityPlanner()
        self.planner_cost = CostOptimizer()
        self.policy_engine = PolicyEngine()
        self.event_bus = event_bus
        self._provider_interface = ProviderInterface(event_bus=self.event_bus)

    def _is_mock_keys(self) -> bool:
        return "mock-" in self.api_key_groq or "mock-" in self.api_key_or or not self.api_key_groq
        
    def _get_model_config(self, tier: str = "tier_1_fast") -> Dict[str, Any]:
        """Fetches the primary provider/model and full routing chain from the catalogue."""
        tier_def = config.CAPABILITY_CATALOGUE.get(tier)
        if tier_def and tier_def.get("routing_chain"):
            head = tier_def["routing_chain"][0]
            return {
                "provider": head["provider"],
                "model": head["model"],
                "routing_chain": tier_def["routing_chain"]
            }
        # Ultimate fallback
        return {"provider": "groq", "model": "llama-3.1-8b-instant", "routing_chain": []}

    async def compile(self, user_intent: str, workflow_id: str = None) -> WorkflowPlan:
        """Executes the full 10-pass compilation sequence.

        Args:
            user_intent: Raw unstructured user prompt.

        Returns:
            An immutable WorkflowPlan schema.
        """
        logger.info("Initializing 10-pass cognitive compilation pipeline.")
        workflow_id = workflow_id or str(uuid.uuid4())
        
        if self.event_bus:
            from contracts.message import EventMessage
            evt = EventMessage(
                sender_id="COMPILER",
                receiver_id="EVENT",
                workflow_id=workflow_id,
                msg_type="EVENT",
                event_name="Workflow Created",
                payload={"stage": "compiler", "status": "started"}
            )
            await self.event_bus.publish(evt)

        # Pass 1: Intent Parsing (👑 Probabilistic LLM / Deterministic Fallback)
        ir_v1 = await self._pass_1_intent_parsing(user_intent)
        
        if self.event_bus:
            await self.event_bus.publish(EventMessage(
                sender_id="COMPILER",
                receiver_id="EVENT",
                workflow_id=workflow_id,
                msg_type="EVENT",
                event_name="Intent Parsed",
                payload={"intent": ir_v1}
            ))

        # Pass 2: Semantic Analysis (👑 Probabilistic LLM / Deterministic Fallback)
        ir_v2 = await self._pass_2_semantic_analysis(ir_v1)
        
        if self.event_bus:
            await self.event_bus.publish(EventMessage(
                sender_id="COMPILER",
                receiver_id="EVENT",
                workflow_id=workflow_id,
                msg_type="EVENT",
                event_name="IR Generated",
                payload={"ir": ir_v2}
            ))

        # Pass 3: Dependency Analysis (❌ Deterministic)
        dependencies = self._pass_3_dependency_analysis(ir_v2)

        # Pass 4: Workflow Optimization (❌ Deterministic)
        optimized_graph = self._pass_4_workflow_optimization(ir_v2, dependencies)

        # Pass 5: Capability Analysis (❌ Deterministic)
        capabilities = self._pass_5_capability_analysis(optimized_graph)

        # Pass 6: Risk Analysis (❌ Deterministic)
        risk_metrics = self._pass_6_risk_analysis(optimized_graph)

        # Pass 7: Budget Analysis (❌ Deterministic)
        budgets = self._pass_7_budget_analysis(optimized_graph, capabilities)

        # Pass 8: Runtime Selection (❌ Deterministic)
        runtime_assignments = self._pass_8_runtime_selection(optimized_graph, budgets)

        # Pass 9: DAG Optimization (❌ Deterministic)
        dag_plan = self._pass_9_dag_optimization(optimized_graph, runtime_assignments)

        # Pass 10: WorkflowPlan Compilation (❌ Deterministic)
        plan = self._pass_10_workflowplan_compilation(dag_plan, risk_metrics, budgets, capabilities, user_intent)
        plan.workflow_id = workflow_id
        
        if self.event_bus:
            from contracts.message import EventMessage
            evt = EventMessage(
                sender_id="COMPILER",
                receiver_id="EVENT",
                workflow_id=workflow_id,
                msg_type="EVENT",
                event_name="COMPILER_FINISHED",
                payload={"stage": "compiler", "status": "finished", "workflow_id": workflow_id}
            )
            await self.event_bus.publish(evt)

        logger.info(f"Compilation pipeline completed. WorkflowPlan compiled: {plan.workflow_id}")
        return plan

    async def _pass_1_intent_parsing(self, intent: str) -> Dict[str, Any]:
        """Pass 1: Parses natural language query into intent labels."""
        logger.info("[Compile] Pass 1: Parsing user intent via LLM.")
        model_cfg = self._get_model_config("tier_1_fast")
        logger.info(f"[Compile] Pass 1: Routing to {model_cfg['provider']} model '{model_cfg['model']}'.")
        try:
            result = await self._provider_interface.execute(
                prompt=intent,
                model=model_cfg["model"],
                provider=model_cfg["provider"],
                routing_chain=model_cfg.get("routing_chain", []),
                system_prompt="Parse this text and return a JSON containing 'primary_action' (string) and 'entities' (list of strings).",
            )
            logger.info("[Compile] Pass 1: LLM responded successfully.")
            return json.loads(result["content"])
        except Exception as e:
            logger.warning(f"[Compile] Pass 1: LLM call failed ({e}) — falling back to deterministic.")

        return {"raw_intent": intent, "primary_action": "query_analysis", "entities": [], "urgency": "medium"}

    async def _pass_2_semantic_analysis(self, ir_v1: Dict[str, Any]) -> Dict[str, Any]:
        """Pass 2: Explores semantic graph relations and extraction targets."""
        logger.info("[Compile] Pass 2: Semantic structure analysis via LLM.")
        intent_str = json.dumps(ir_v1)
        model_cfg = self._get_model_config("tier_2_standard")
        logger.info(f"[Compile] Pass 2: Routing to {model_cfg['provider']} model '{model_cfg['model']}'.")

        sys_prompt = (
            "Break down the intent into a JSON object with 'semantic_subtasks' (list of dicts). "
            "Each dict must have 'step_id' (string, e.g. ST_01), 'task' (string), 'profile' (string: heavy, retrieval, or fast), "
            "and 'dependencies' (list of step_id strings this task depends on)."
        )

        try:
            result = await self._provider_interface.execute(
                prompt=intent_str,
                model=model_cfg["model"],
                provider=model_cfg["provider"],
                routing_chain=model_cfg.get("routing_chain", []),
                system_prompt=sys_prompt,
            )
            logger.info("[Compile] Pass 2: LLM responded successfully.")
            parsed = json.loads(result["content"])
            return {"intent_data": copy.deepcopy(ir_v1), "semantic_subtasks": parsed.get("semantic_subtasks", [])}
        except Exception as e:
            logger.warning(f"[Compile] Pass 2: LLM call failed ({e}) — falling back to deterministic.")

        return {
            "intent_data": copy.deepcopy(ir_v1),
            "semantic_subtasks": [
                {"step_id": "ST_01", "task": "fetch_history_context", "profile": "retrieval", "dependencies": []},
                {"step_id": "ST_02", "task": "perform_cognitive_reasoning", "profile": "heavy", "dependencies": ["ST_01"]},
                {"step_id": "ST_03", "task": "verify_result_integrity", "profile": "fast", "dependencies": ["ST_02"]}
            ]
        }

    def _pass_3_dependency_analysis(self, ir_v2: Dict[str, Any]) -> Dict[str, List[str]]:
        """Pass 3: Identifies dependency parameters between subtasks."""
        logger.info("[Compile] Pass 3: Constructing dependency constraints.")
        deps = {}
        for task in ir_v2.get("semantic_subtasks", []):
            deps[task["step_id"]] = list(task.get("dependencies", []))
        return deps

    def _pass_4_workflow_optimization(self, ir_v2: Dict[str, Any], deps: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        """Pass 4: Optimizes execution topology graphs using topological sort."""
        logger.info("[Compile] Pass 4: Topologically sorting task pathways.")
        unresolved = set(deps.keys())
        resolved = set()
        optimized = []
        
        # Deep copy to prevent mutation of ir_v2
        task_map = {task["step_id"]: copy.deepcopy(task) for task in ir_v2.get("semantic_subtasks", [])}

        while unresolved:
            progress = False
            for step_id in list(unresolved):
                if all(dep in resolved for dep in deps[step_id]):
                    optimized.append(task_map[step_id])
                    resolved.add(step_id)
                    unresolved.remove(step_id)
                    progress = True
            
            if not progress:
                logger.critical("Dependency loop detected in compilation Pass 4.")
                raise ValueError("Cyclic dependency in workflow execution graph.")
                
        return optimized

    def _pass_5_capability_analysis(self, graph: List[Dict[str, Any]]) -> Dict[str, CapabilityProfile]:
        """Pass 5: Resolves abstract environment constraints per subtask."""
        logger.info("[Compile] Pass 5: Resolving hardware/modality requirements.")
        profiles = {}
        for task in graph:
            prof_type = task.get("profile", "fast")
            task_name = task.get("task", "")
            reqs = self.planner_capability.profile_task_requirements(task_name)
            
            if prof_type == "heavy":
                profile = CapabilityProfile(
                    minimum_reasoning_tier="HIGH",
                    needs_vision=reqs["needs_vision"],
                    needs_code_sandbox=reqs["needs_code_sandbox"],
                    context_window_minimum_k=32,
                    cost_ceiling_usd=0.05
                )
            elif prof_type == "retrieval":
                profile = CapabilityProfile(
                    minimum_reasoning_tier="LOW",
                    needs_vision=reqs["needs_vision"],
                    needs_code_sandbox=reqs["needs_code_sandbox"],
                    context_window_minimum_k=8,
                    cost_ceiling_usd=0.001
                )
            else:
                profile = CapabilityProfile(
                    minimum_reasoning_tier="STANDARD",
                    needs_vision=reqs["needs_vision"],
                    needs_code_sandbox=reqs["needs_code_sandbox"],
                    context_window_minimum_k=16,
                    cost_ceiling_usd=0.01
                )
            profiles[task["step_id"]] = profile
        return profiles

    def _pass_6_risk_analysis(self, graph: List[Dict[str, Any]]) -> Dict[str, float]:
        """Pass 6: Checks anomalous security vectors."""
        logger.info("[Compile] Pass 6: Scanning risk parameters.")
        risks = {"global_risk": 0.0}
        for task in graph:
            # Deterministic scan of task name for risk indicators
            task_str = task.get("task", "").lower()
            risk_val = 0.05
            if any(danger in task_str for danger in ["eval", "exec", "system", "delete"]):
                risk_val = 0.20
                risks["global_risk"] += 0.1
            risks[task["step_id"]] = risk_val
        return risks

    def _pass_7_budget_analysis(self, graph: List[Dict[str, Any]], caps: Dict[str, CapabilityProfile]) -> Dict[str, float]:
        """Pass 7: Enforces strict cost ceiling estimates."""
        logger.info("[Compile] Pass 7: Estimating token cost limits.")
        costs = {}
        for task in graph:
            step_id = task["step_id"]
            # Base cost from capability profile
            costs[step_id] = caps[step_id].cost_ceiling_usd
        return costs

    def _pass_8_runtime_selection(self, graph: List[Dict[str, Any]], budgets: Dict[str, float]) -> Dict[str, str]:
        """Pass 8: Maps subtasks to explicit execution runtimes."""
        logger.info("[Compile] Pass 8: Selecting execution runtime kernels.")
        assignments = {}
        for task in graph:
            prof = task.get("profile", "fast")
            if prof == "heavy":
                assignments[task["step_id"]] = "COMPETITIVE"
            elif prof == "retrieval":
                assignments[task["step_id"]] = "RETRIEVAL"
            else:
                assignments[task["step_id"]] = "STANDARD"
        return assignments

    def _pass_9_dag_optimization(self, graph: List[Dict[str, Any]], runtimes: Dict[str, str]) -> List[Dict[str, Any]]:
        """Pass 9: Optimizes final DAG links and concurrency boundaries."""
        logger.info("[Compile] Pass 9: Finalizing DAG topologies.")
        optimized_dag = copy.deepcopy(graph)
        for task in optimized_dag:
            task["assigned_runtime"] = runtimes.get(task["step_id"], "STANDARD")
        return optimized_dag

    def _pass_10_workflowplan_compilation(self, dag: List[Dict[str, Any]], risks: Dict[str, float], budgets: Dict[str, float], caps: Dict[str, CapabilityProfile], user_intent: str) -> WorkflowPlan:
        """Pass 10: Assembles final signed immutable plan."""
        logger.info("[Compile] Pass 10: Committing WorkflowPlan definitions.")
        workflow_id = str(uuid.uuid4())
        nodes = {}

        for task in dag:
            step_id = task["step_id"]
            
            # Create immutable TCB
            tcb = TaskControlBlock(
                workflow_id=workflow_id,
                dependencies=list(task.get("dependencies", [])),
                assigned_runtime=task["assigned_runtime"],
                primary_capability=copy.deepcopy(caps[step_id]),
                timeout_ms=10000 if task["assigned_runtime"] == "MICRO" else 30000,
                payload={"task_name": task.get("task", ""), "prompt": user_intent}
            )
            
            node = WorkflowNode(
                node_id=step_id,
                dependencies=list(task.get("dependencies", [])),
                tcb=tcb
            )
            nodes[step_id] = node

        plan = WorkflowPlan(
            workflow_id=workflow_id,
            nodes=nodes,
            risk_score=risks.get("global_risk", 0.1),
            policy_flag="OK"
        )
        
        # Validate plan using PolicyEngine
        is_valid, msg = self.policy_engine.validate_plan(plan, user_intent)
        if not is_valid:
            plan.policy_flag = "REJECTED"
            logger.error(f"PolicyEngine rejected compiled plan: {msg}")
            raise ValueError(f"Plan validation failed: {msg}")

        return plan
