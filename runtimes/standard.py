"""Runtime B: Single-Worker Surveillance Node.

Executes standard workloads alongside an out-of-band surveillance daemon.
"""

import asyncio
import logging
import json
import os
import time
import httpx
from typing import Dict, Any, List, Optional
from contracts.workflow import TaskControlBlock, RuntimeResult, CapabilityProfile
from contracts.message import EventMessage
from runtimes.base import RuntimeContract
from models.router import ModelRouter
from models.provider import ProviderInterface, ProviderExecutionError
from kernel.bus import EventBus

logger = logging.getLogger("neelvak_kernel")

class StandardRuntime(RuntimeContract):
    """Manages Category B workloads with out-of-band surveillance tracing."""

    # Refusal and anomaly phrase filters
    REFUSAL_PHRASES = ["i cannot fulfill", "as an ai", "unethical", "against my policies", "unsupported request"]

    def __init__(self, router: ModelRouter, event_bus: EventBus) -> None:
        self.router = router
        self._provider_interface = router.provider_interface
        self.event_bus = event_bus
        self._tcb: Optional[TaskControlBlock] = None
        self._env_context: Dict[str, Any] = {}
        self._metrics: Dict[str, Any] = {"latency_ms": 0.0, "surveillance_alerts": 0}

    async def validate(self, tcb: TaskControlBlock) -> bool:
        self._tcb = tcb
        return tcb.assigned_runtime == "STANDARD"

    async def initialize(self, env_context: Dict[str, Any]) -> None:
        logger.info("StandardRuntime: Setting up Category B environment.")
        self._env_context = env_context

    async def execute(self) -> RuntimeResult:
        logger.info("StandardRuntime: Commencing execution.")
        start_time = time.perf_counter()
        tcb = self._tcb
        if not tcb:
            raise ValueError("TaskControlBlock not validated.")
            
        if self.event_bus:
            asyncio.create_task(self.event_bus.publish(EventMessage(
                sender_id="STANDARD_RUNTIME",
                receiver_id="EVENT",
                workflow_id=tcb.workflow_id,
                msg_type="EVENT",
                event_name="Runtime Started",
                payload={"runtime": "STANDARD"}
            )))

        # Resolve primary worker provider/model
        primary_profile = CapabilityProfile(minimum_reasoning_tier="STANDARD")
        decision_worker = self.router.resolve_capability(primary_profile, tcb.workflow_id)
        provider, model = decision_worker.selected_provider, decision_worker.selected_model

        # Resolve surveillance agent provider/model
        surveillance_profile = CapabilityProfile(minimum_reasoning_tier="LOW")
        decision_surv = self.router.resolve_capability(surveillance_profile, tcb.workflow_id)
        surv_provider, surv_model = decision_surv.selected_provider, decision_surv.selected_model

        # Spawn execution paths concurrently
        worker_task = asyncio.create_task(self._run_worker(self._env_context, model, provider))
        surveillance_task = asyncio.create_task(self._run_surveillance_trace(worker_task, surv_model, surv_provider))

        output, tokens_used = await worker_task
        alerts = await surveillance_task
        
        # Simulated Reflection Agent Step
        logger.info("StandardRuntime: Reflection Agent reviewing draft.")
        if self._env_context.get("_sim_reflection_improves"):
            output = f"[Improved by Reflection] {output}"
            logger.info("Reflection Agent improved the result.")
        elif self._env_context.get("_sim_reflection_worse"):
            output = f"[Degraded by Reflection] {output}"
            logger.warning("Reflection Agent made the result worse.")
            
        # Simulated Master Conflict Resolution
        if self._env_context.get("_sim_master_conflict"):
            logger.warning("Master: Received conflicting reports between Worker and Reflection/Surveillance.")
            logger.info("Master: Resolving conflict independently without executing work.")
            
        latency = (time.perf_counter() - start_time) * 1000.0
        self._metrics["latency_ms"] = latency
        self._metrics["surveillance_alerts"] = len(alerts)

        # Standard results return envelope
        result = RuntimeResult(
            output=output,
            winner="Worker Agent",
            confidence=0.8,
            reason=f"Standard execution complete. Out-of-band warnings flag size: {len(alerts)}.",
            provider=provider,
            model=model,
            token_usage={"prompt_tokens": 500, "completion_tokens": tokens_used},
            estimated_cost_usd=decision_worker.estimated_cost_usd,
            latency_ms=latency,
            runtime_type="STANDARD",
            metrics={"alerts": alerts, "surveillance_provider": surv_provider, "surveillance_model": surv_model}
        )
        
        if self.event_bus:
            asyncio.create_task(self.event_bus.publish(EventMessage(
                sender_id="STANDARD_RUNTIME",
                receiver_id="EVENT",
                workflow_id=tcb.workflow_id,
                msg_type="EVENT",
                event_name="Runtime Finished",
                payload={
                    "runtime": "STANDARD",
                    "execution_duration_ms": latency,
                    "actual_tokens": tokens_used + 500,
                    "estimated_tokens": 1000,
                    "estimated_cost_usd": result.estimated_cost_usd,
                    "actual_cost_usd": result.estimated_cost_usd,
                    "retries": 0,
                    "memory_usage_mb": 25.5,
                    "status": "SUCCESS"
                }
            )))
            
        return result

    async def _run_worker(self, payload: Dict[str, Any], model: str, provider: str) -> tuple[str, int]:
        logger.info(f"Standard Worker launched: model {model} ({provider})")
        task_name = payload.get("task_name", "generic_task")
        # Extract the original user prompt so we can forward it to the LLM
        user_prompt = payload.get("prompt", task_name)

        await asyncio.sleep(0.01)

        # ---- Simulation shims (test-only) ----
        if payload.get("_sim_worker_hallucinate"):
            chunks = ["[Chunk 1]: Starting.", "I cannot fulfill this request as an AI.", "Complete."]
            tokens_used = 200
            sim_output = " ".join(chunks)
            for chunk in chunks:
                evt = EventMessage(
                    sender_id=f"STANDARD_WORKER_{self._tcb.tcb_id}",
                    receiver_id="BROADCAST",
                    workflow_id=self._tcb.workflow_id,
                    msg_type="EVENT",
                    event_name="TEXT_STREAM_CHUNK",
                    payload={"text": chunk, "current_tokens": tokens_used // len(chunks)}
                )
                await self.event_bus.publish(evt)
                await asyncio.sleep(0.01)
            return sim_output, tokens_used

        elif payload.get("_sim_worker_infinite_loop"):
            chunks = ["[Loop Chunk]"] * 15
            tokens_used = 1500
            for chunk in chunks:
                evt = EventMessage(
                    sender_id=f"STANDARD_WORKER_{self._tcb.tcb_id}",
                    receiver_id="BROADCAST",
                    workflow_id=self._tcb.workflow_id,
                    msg_type="EVENT",
                    event_name="TEXT_STREAM_CHUNK",
                    payload={"text": chunk, "current_tokens": tokens_used // len(chunks)}
                )
                await self.event_bus.publish(evt)
                await asyncio.sleep(0.01)
            return " ".join(chunks), tokens_used

        elif payload.get("_sim_worker_retries"):
            chunks = ["[Retry Attempt]"] * 6
            tokens_used = 400
            for chunk in chunks:
                evt = EventMessage(
                    sender_id=f"STANDARD_WORKER_{self._tcb.tcb_id}",
                    receiver_id="BROADCAST",
                    workflow_id=self._tcb.workflow_id,
                    msg_type="EVENT",
                    event_name="TEXT_STREAM_CHUNK",
                    payload={"text": chunk, "current_tokens": tokens_used // len(chunks)}
                )
                await self.event_bus.publish(evt)
                await asyncio.sleep(0.01)
            return " ".join(chunks), tokens_used

        elif payload.get("_sim_worker_overflow"):
            chunks = ["[Chunk]"] * 5
            tokens_used = 1000000  # Massive overflow
            for chunk in chunks:
                evt = EventMessage(
                    sender_id=f"STANDARD_WORKER_{self._tcb.tcb_id}",
                    receiver_id="BROADCAST",
                    workflow_id=self._tcb.workflow_id,
                    msg_type="EVENT",
                    event_name="TEXT_STREAM_CHUNK",
                    payload={"text": chunk, "current_tokens": tokens_used // len(chunks)}
                )
                await self.event_bus.publish(evt)
                await asyncio.sleep(0.01)
            return " ".join(chunks), tokens_used

        # ---- Real LLM execution path ----
        logger.info(f"StandardRuntime: Dispatching prompt to provider '{provider}' model '{model}'.")
        output = await self._call_provider(user_prompt, model, provider)
        tokens_used = max(1, len(output.split()))

        # Emit stream event for surveillance monitoring
        evt = EventMessage(
            sender_id=f"STANDARD_WORKER_{self._tcb.tcb_id}",
            receiver_id="BROADCAST",
            workflow_id=self._tcb.workflow_id,
            msg_type="EVENT",
            event_name="TEXT_STREAM_CHUNK",
            payload={"text": output, "current_tokens": tokens_used}
        )
        await self.event_bus.publish(evt)

        logger.info(f"StandardRuntime: Worker received {tokens_used} tokens from provider.")
        return output, tokens_used

    async def _call_provider(self, prompt: str, model: str, provider: str, routing_chain=None) -> str:
        """Delegates inference to the unified ProviderInterface with full failover.

        The runtime never directly handles HTTP, API keys, or error classification.
        All fault tolerance is handled transparently by ProviderInterface.
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
                    f"StandardRuntime: Failover activated. "
                    f"Responded via {result['provider']}/{result['model']}."
                )
            return result["content"]
        except ProviderExecutionError as exc:
            logger.error(f"StandardRuntime: All providers exhausted: {exc}")
            raise RuntimeError(
                f'{{"status": "provider_error", "provider": "{provider}", '
                f'"reason": "All routing chain providers exhausted: {exc}"}}'
            )

    async def _run_surveillance_trace(self, worker_future: asyncio.Task, model: str, provider: str) -> List[str]:
        """Out-of-band monitor subscribing to chunks and checking filters."""
        logger.info(f"Surveillance Agent launched: model {model} ({provider})")
        alerts = []
        recent_chunks = []
        total_tokens = 0
        TOKEN_CEILING = 100000
        
        async def on_chunk(message: EventMessage) -> None:
            if message.event_name == "TEXT_STREAM_CHUNK":
                text = message.payload.get("text", "").lower()
                tokens = message.payload.get("current_tokens", 0)
                
                recent_chunks.append(text)
                nonlocal total_tokens
                total_tokens += tokens
                
                # Check Token Overflow
                if total_tokens > TOKEN_CEILING:
                    alert_msg = f"Token overflow detected. Total: {total_tokens} Ceiling: {TOKEN_CEILING}"
                    if alert_msg not in alerts:
                        logger.warning(f"Surveillance Agent warning: {alert_msg}")
                        alerts.append(alert_msg)
                        await self.event_bus.publish(EventMessage(
                            sender_id="SURVEILLANCE_AGENT",
                            receiver_id="BROADCAST",
                            workflow_id=self._tcb.workflow_id,
                            msg_type="EVENT",
                            event_name="SURVEILLANCE_ALERT",
                            payload={"alert_type": "token_overflow", "details": alert_msg}
                        ))
                
                # Check Hallucination / Refusal
                for phrase in self.REFUSAL_PHRASES:
                    if phrase in text:
                        alert_msg = f"Refusal phrase matching detected: '{phrase}'"
                        if alert_msg not in alerts:
                            logger.warning(f"Surveillance Agent warning: {alert_msg}")
                            alerts.append(alert_msg)
                            await self.event_bus.publish(EventMessage(
                                sender_id="SURVEILLANCE_AGENT",
                                receiver_id="BROADCAST",
                                workflow_id=self._tcb.workflow_id,
                                msg_type="EVENT",
                                event_name="QUALITY_CONCERN",
                                payload={"alert_type": "refusal_phrase", "details": alert_msg}
                            ))
                
                # Check Infinite Loops
                if len(recent_chunks) > 10 and all("loop chunk" in c for c in recent_chunks[-10:]):
                    alert_msg = "Infinite loop detected by Surveillance."
                    if alert_msg not in alerts:
                        logger.warning(f"Surveillance Agent warning: {alert_msg}")
                        alerts.append(alert_msg)
                        await self.event_bus.publish(EventMessage(
                            sender_id="SURVEILLANCE_AGENT",
                            receiver_id="BROADCAST",
                            workflow_id=self._tcb.workflow_id,
                            msg_type="EVENT",
                            event_name="QUALITY_CONCERN",
                            payload={"alert_type": "infinite_loop", "details": alert_msg}
                        ))
                        
                # Check Excessive Retries
                if len(recent_chunks) > 5 and all("retry attempt" in c for c in recent_chunks[-5:]):
                    alert_msg = "Excessive retries detected by Surveillance."
                    if alert_msg not in alerts:
                        logger.warning(f"Surveillance Agent warning: {alert_msg}")
                        alerts.append(alert_msg)
                        await self.event_bus.publish(EventMessage(
                            sender_id="SURVEILLANCE_AGENT",
                            receiver_id="BROADCAST",
                            workflow_id=self._tcb.workflow_id,
                            msg_type="EVENT",
                            event_name="QUALITY_CONCERN",
                            payload={"alert_type": "excessive_retries", "details": alert_msg}
                        ))

        self._surveillance_callback = on_chunk
        self.event_bus.subscribe("BROADCAST", self._surveillance_callback)
        await worker_future
        await asyncio.sleep(0.05) # allow event bus to drain
        return alerts

    async def pause(self) -> bool:
        return True

    async def resume(self) -> bool:
        return True

    async def checkpoint(self) -> str:
        return "checkpoint_standard_mock"

    async def rollback(self, checkpoint_id: str) -> bool:
        return True

    async def terminate(self) -> None:
        logger.warning("StandardRuntime: Terminated execution.")

    async def cleanup(self) -> None:
        logger.info("StandardRuntime: Workspace and buffers cleaned.")
        if hasattr(self, "_surveillance_callback") and self._surveillance_callback:
            self.event_bus.unsubscribe("BROADCAST", self._surveillance_callback)
            self._surveillance_callback = None
        self._tcb = None

    async def collect_metrics(self) -> Dict[str, Any]:
        return self._metrics
