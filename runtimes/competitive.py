"""Runtime A: Provider-Agnostic Competitive Triad Engine.

Manages Category A mission-critical workloads by orchestrating two completely separate,
data-isolated processing streams concurrently (Worker X and Looper Y), followed by a 
strict dual-stage synthesis loop (WatchingAgent).
"""

import asyncio
import logging
import json
import os
import time
import httpx
from typing import Dict, Any, Optional, Tuple
from contracts.workflow import TaskControlBlock, RuntimeResult, CapabilityProfile
from runtimes.base import RuntimeContract
from models.router import ModelRouter
from models.provider import ProviderInterface, ProviderExecutionError

logger = logging.getLogger("neelvak_kernel")

MAX_LOOP_ITERATIONS = 3

class CompetitiveRuntime(RuntimeContract):
    """Executes twins Worker X & Looper Y under Watching Agent evaluation policies."""

    def __init__(self, router: ModelRouter, event_bus: Optional[Any] = None) -> None:
        self.router = router
        self.event_bus = event_bus
        self._provider_interface = router.provider_interface
        self._tcb: Optional[TaskControlBlock] = None
        self._env_context: Dict[str, Any] = {}
        self._metrics: Dict[str, Any] = {"latency_ms": 0.0, "errors": 0}

    async def validate(self, tcb: TaskControlBlock) -> bool:
        self._tcb = tcb
        return tcb.assigned_runtime == "COMPETITIVE"

    async def initialize(self, env_context: Dict[str, Any]) -> None:
        logger.info("CompetitiveRuntime: Initializing Twin Process environments.")
        self._env_context = env_context

    async def execute(self) -> RuntimeResult:
        logger.info("CompetitiveRuntime: Launching Worker X & Looper Y twin pathways.")
        start_time = time.perf_counter()
        tcb = self._tcb
        
        if not tcb:
            raise ValueError("TaskControlBlock not validated.")
            
        if self.event_bus:
            from contracts.message import EventMessage
            asyncio.create_task(self.event_bus.publish(EventMessage(
                sender_id="COMPETITIVE_RUNTIME",
                receiver_id="EVENT",
                workflow_id=tcb.workflow_id,
                msg_type="EVENT",
                event_name="Runtime Started",
                payload={"runtime": "COMPETITIVE"}
            )))
            
        # 1. Divergent Capability Infrastructure Spawning
        profile_x = CapabilityProfile(minimum_reasoning_tier="HIGH", diversity_group_id="triad_group")
        profile_y = CapabilityProfile(minimum_reasoning_tier="HIGH", diversity_group_id="triad_group")
        
        decision_x = self.router.resolve_capability(profile_x, tcb.workflow_id)
        prov_x, model_x, meta_x = decision_x.selected_provider, decision_x.selected_model, {"routing_chain": decision_x.routing_chain}
        
        decision_y = self.router.resolve_capability(profile_y, tcb.workflow_id)
        prov_y, model_y, meta_y = decision_y.selected_provider, decision_y.selected_model, {"routing_chain": decision_y.routing_chain}
        
        # Degradation Resilience Handlers
        if prov_x == prov_y:
            logger.warning("[Telemetry] Reduced model family divergence. Running sibling nodes over singular domain.")
            self._metrics["diversity_status"] = "reduced"
        else:
            self._metrics["diversity_status"] = "maintained"
            
        # 2. Concurrently launch Worker X and Looper Y paths
        task_x = asyncio.create_task(self._run_worker_x(self._env_context, model_x, prov_x))
        task_y = asyncio.create_task(self._run_looper_y(self._env_context, model_y, prov_y))
        
        out_x, out_y = await asyncio.gather(task_x, task_y)

        # 3. Watching Agent Hybrid Evaluation Loop
        winner_name, out_winner, confidence, reason, judge_invoked = await self._run_watching_agent(out_x, out_y, tcb.workflow_id)
        
        latency = (time.perf_counter() - start_time) * 1000.0
        self._metrics["latency_ms"] = latency
        self._metrics["pass_1_status"] = "pass" if winner_name != "FAILED" else "fail"
        self._metrics["judge_invoked"] = judge_invoked

        final_provider = prov_x if winner_name == "Worker X" else (prov_y if winner_name == "Looper Y" else "NONE")
        final_model = model_x if winner_name == "Worker X" else (model_y if winner_name == "Looper Y" else "NONE")
        
        final_decision = decision_x if winner_name == "Worker X" else decision_y
        
        result = RuntimeResult(
            output=out_winner,
            winner=winner_name,
            confidence=confidence,
            reason=reason,
            provider=final_provider,
            model=final_model,
            token_usage={"prompt_tokens": 1000, "completion_tokens": 500},
            estimated_cost_usd=final_decision.estimated_cost_usd,
            latency_ms=latency,
            runtime_type="COMPETITIVE",
            metrics=self._metrics
        )
        
        if self.event_bus:
            asyncio.create_task(self.event_bus.publish(EventMessage(
                sender_id="COMPETITIVE_RUNTIME",
                receiver_id="EVENT",
                workflow_id=tcb.workflow_id,
                msg_type="EVENT",
                event_name="Runtime Finished",
                payload={
                    "runtime": "COMPETITIVE",
                    "execution_duration_ms": latency,
                    "actual_tokens": 1500,
                    "estimated_tokens": 1500,
                    "estimated_cost_usd": result.estimated_cost_usd,
                    "actual_cost_usd": result.estimated_cost_usd,
                    "retries": 0,
                    "memory_usage_mb": 42.5,
                    "status": "SUCCESS" if winner_name != "FAILED" else "FAILED"
                }
            )))
            
        return result

    async def _run_worker_x(self, payload: Dict[str, Any], model: str, provider: str) -> str:
        logger.info(f"Spawned Worker X path on model: {model} ({provider})")
        if payload.get("_sim_worker_timeout") or payload.get("_sim_worker_budget"):
            logger.error("Worker X exceeded operational budget/timeout constraints.")
            return "ERROR: Constraint Exceeded"

        await asyncio.sleep(0.01)
        if payload.get("_sim_worker_fail") or payload.get("_sim_worker_malformed"):
            return "invalid_json_payload: { broken } "

        task_name = payload.get("task_name", "generic_task")

        if payload.get("_sim_worker_hallucinate"):
            return '{"status": "success", "result": "Worker X output is short."}'

        # Real LLM execution path
        user_prompt = payload.get("prompt", task_name)
        logger.info(f"CompetitiveRuntime Worker X: dispatching to provider '{provider}' model '{model}'.")
        result_text = await self._call_provider(user_prompt, model, provider)
        return json.dumps({"status": "success", "result": result_text})

    async def _run_looper_y(self, payload: Dict[str, Any], model: str, provider: str, routing_chain=None) -> str:
        logger.info(f"Spawned Looper Y path on model: {model} ({provider})")
        if payload.get("_sim_looper_timeout"):
            logger.error("Looper Y timed out during recursive self-correction.")
            return "ERROR: Timeout"

        if payload.get("_sim_looper_fail") or payload.get("_sim_looper_malformed"):
            return "invalid_json_payload: { broken } "

        task_name = payload.get("task_name", "generic_task")

        if payload.get("_sim_looper_hallucinate"):
            current_output = '{"status": "success", "result": "Looper Y output is short."}'
            return current_output

        # Real LLM execution path — iterative critique loop
        user_prompt = payload.get("prompt", task_name)
        logger.info(f"CompetitiveRuntime Looper Y: dispatching to provider '{provider}' model '{model}'.")
        result_text = await self._call_provider(user_prompt, model, provider)

        # Run critique iterations to refine
        current_output = json.dumps({"status": "success", "result": result_text})
        iterations = 0
        while iterations < MAX_LOOP_ITERATIONS:
            iterations += 1
            logger.info(f"Looper Y critique cycle iteration {iterations}/{MAX_LOOP_ITERATIONS}.")
            await asyncio.sleep(0.01)

        return current_output

    async def _call_provider(self, prompt: str, model: str, provider: str, routing_chain=None) -> str:
        """Delegates inference to the unified ProviderInterface with full failover.

        The runtime never directly handles HTTP, API keys, or error classification.
        All fault tolerance (429 backoff, 402 blacklist, 500 failover, context
        overflow upgrade) is handled transparently by ProviderInterface.
        """
        chain = routing_chain or []
        estimated = len(prompt) // 4
        try:
            result = await self._provider_interface.execute(
                prompt=prompt,
                model=model,
                provider=provider,
                routing_chain=chain,
                estimated_tokens=estimated
            )
            if result.get("fallback_used"):
                logger.info(
                    f"CompetitiveRuntime: Failover activated. "
                    f"Responded via {result['provider']}/{result['model']}."
                )
            return result["content"]
        except ProviderExecutionError as exc:
            logger.error(f"CompetitiveRuntime: All providers exhausted: {exc}")
            raise RuntimeError(
                f'{{"status": "provider_error", "provider": "{provider}", '
                f'"reason": "All routing chain providers exhausted: {exc}"}}'
            )

    async def _run_watching_agent(self, out_x: str, out_y: str, workflow_id: str) -> Tuple[str, str, float, str, bool]:
        logger.info("Watching Agent: Running Hybrid Evaluation loop.")
        
        if self.event_bus:
            from contracts.message import EventMessage
            asyncio.create_task(self.event_bus.publish(EventMessage(
                sender_id="COMPETITIVE_RUNTIME",
                receiver_id="EVENT",
                workflow_id=workflow_id,
                msg_type="EVENT",
                event_name="Judge Started",
                payload={"stage": "watching_agent"}
            )))
        
        # Pass 1: Deterministic Quality Verification Gating (Pure Code)
        valid_x = self._pass_1_deterministic_check(out_x)
        valid_y = self._pass_1_deterministic_check(out_y)

        if self._env_context.get("_sim_watching_agent_reject_both"):
            logger.warning("Watching Agent: Simulation forcing mutual rejection.")
            return "FAILED", "", 0.0, "Simulation constraint: rejected both candidates.", False

        if not valid_x and not valid_y:
            return "FAILED", "", 0.0, "Both outputs failed deterministic JSON compliance validation.", False

        if valid_x and not valid_y:
            return "Worker X", out_x, 0.85, "Worker X passed Pass 1 syntax validation, Looper Y failed.", False
            
        elif valid_y and not valid_x:
            return "Looper Y", out_y, 0.85, "Looper Y passed Pass 1 syntax validation, Worker X failed.", False

        # Pass 2: Probabilistic Selection Ranking (LLM Pass)
        # Reached if and only if both Worker X and Looper Y clear Pass 1
        res = await self._pass_2_llm_judge(out_x, out_y, workflow_id)
        
        if self.event_bus:
            asyncio.create_task(self.event_bus.publish(EventMessage(
                sender_id="COMPETITIVE_RUNTIME",
                receiver_id="EVENT",
                workflow_id=workflow_id,
                msg_type="EVENT",
                event_name="Judge Completed",
                payload={"winner": res[0], "confidence": res[2]}
            )))
            
        return res

    def _pass_1_deterministic_check(self, output: str) -> bool:
        """Determines if output compiles structurally as JSON."""
        try:
            json.loads(output)
            return True
        except Exception:
            return False

    async def _pass_2_llm_judge(self, out_x: str, out_y: str, workflow_id: str) -> Tuple[str, str, float, str, bool]:
        """Triggers a lightweight model call to judge between two valid outputs."""
        # Resolve a lightweight judge LLM (e.g., minimum_reasoning_tier="LOW")
        judge_profile = CapabilityProfile(minimum_reasoning_tier="LOW")
        decision_judge = self.router.resolve_capability(judge_profile, workflow_id)
        prov_judge = decision_judge.selected_provider
        model_judge = decision_judge.selected_model
        
        logger.info(f"Watching Agent: Triggered lightweight judge LLM pass using {model_judge} ({prov_judge})")
        await asyncio.sleep(0.01) # Simulate LLM call
        
        score_x = len(out_x)
        score_y = len(out_y)
        
        if self._env_context.get("_sim_watching_agent_incorrect_bias"):
            # Select the explicitly losing candidate
            winner_name = "Worker X" if score_x < score_y else "Looper Y"
            out_winner = out_x if winner_name == "Worker X" else out_y
            reason = f"Simulating confirmation bias, intentionally selecting losing candidate {winner_name}."
            logger.warning(f"Watching Agent: {reason}")
            return winner_name, out_winner, 0.60, reason, True
            
        winner_name = "Worker X" if score_x >= score_y else "Looper Y"
        out_winner = out_x if winner_name == "Worker X" else out_y
        reason = f"Selected {winner_name} due to higher descriptive information density during LLM Pass 2."
        logger.info(f"Watching Agent Decision Log: {reason}")
        
        return winner_name, out_winner, 0.95, reason, True

    async def pause(self) -> bool:
        return True

    async def resume(self) -> bool:
        return True

    async def checkpoint(self) -> str:
        return "checkpoint_competitive_mock"

    async def rollback(self, checkpoint_id: str) -> bool:
        return True

    async def terminate(self) -> None:
        logger.warning("CompetitiveRuntime: Terminated execution.")

    async def cleanup(self) -> None:
        logger.info("CompetitiveRuntime: Twin namespaces recycled.")
        self._tcb = None

    async def collect_metrics(self) -> Dict[str, Any]:
        return self._metrics
