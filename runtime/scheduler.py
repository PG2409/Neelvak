"""Supervisory Runtime Scheduler & Execution Queue.

Maintains concurrency limits and dispatches WorkflowNode TCBs directly to runtimes.
"""

import asyncio
import logging
import importlib
from typing import Dict, Any, List, Optional
from contracts.workflow import WorkflowPlan, WorkflowNode, EvaluationReport
from runtime.factory import EnvironmentFactory
from kernel.lifecycle import LifecycleManager, ProcessControlBlock, ProcessState, TerminationReason
import config

logger = logging.getLogger("neelvak_kernel")


class RuntimeScheduler:
    """Orchestrates concurrent executions using Semaphores from config parameters."""

    # Map string assignments directly to their class path definitions
    _RUNTIME_MAP = {
        "COMPETITIVE": ("runtimes.competitive", "CompetitiveRuntime"),
        "STANDARD": ("runtimes.standard", "StandardRuntime"),
        "MICRO": ("runtimes.micro", "MicroRuntime"),
        "DIRECT": ("runtimes.direct", "DirectRuntime"),
        "RETRIEVAL": ("runtimes.retrieval", "RetrievalRuntime"),
    }

    def __init__(
        self,
        router: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        memory_manager: Optional[Any] = None,
    ) -> None:
        """Initialises the scheduler with optional shared dependencies for runtime injection.

        Args:
            router: Optional ModelRouter instance passed to router-dependent runtimes.
            event_bus: Optional EventBus instance passed to bus-dependent runtimes.
            memory_manager: Optional MemoryManager instance passed to retrieval runtimes.
        """
        self._semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_RUNTIMES)
        self._active_tasks: List[asyncio.Task] = []
        self._factory = EnvironmentFactory()
        self._lifecycle_mgr = LifecycleManager()
        # Injected shared dependencies – may remain None when instantiated inside tests
        self._router = router
        self._event_bus = event_bus
        self._memory_manager = memory_manager

    async def schedule_workflow(
        self, plan: WorkflowPlan, execution_layers: List[List[str]]
    ) -> Dict[str, EvaluationReport]:
        """Runs the entire plan step-by-step layer-by-layer.

        Args:
            plan: The compiled WorkflowPlan.
            execution_layers: Levels of independent nodes to execute.

        Returns:
            Dict mapping node IDs to their execution EvaluationReport.
        """
        results: Dict[str, EvaluationReport] = {}
        logger.info(f"Scheduler: Commencing scheduling for workflow {plan.workflow_id}")

        if self._event_bus:
            from contracts.message import EventMessage
            evt = EventMessage(
                sender_id="SCHEDULER",
                receiver_id="EVENT",
                workflow_id=plan.workflow_id,
                msg_type="EVENT",
                event_name="Scheduler Decision",
                payload={"stage": "scheduler", "status": "started"}
            )
            await self._event_bus.publish(evt)

        for layer_idx, layer in enumerate(execution_layers):
            logger.info(
                f"Scheduler: Executing dependency layer {layer_idx + 1}/{len(execution_layers)} - Nodes: {layer}"
            )
            tasks = []
            for node_id in layer:
                node = plan.nodes[node_id]
                tasks.append(
                    asyncio.create_task(
                        self._execute_node_with_semaphore(node, plan.workflow_id, results)
                    )
                )

            layer_results = await asyncio.gather(*tasks, return_exceptions=True)

            for res in layer_results:
                if isinstance(res, BaseException):
                    logger.error(
                        f"Scheduler aborted workflow execution due to layer failure: {res}"
                    )
                    raise res

        logger.info(f"Scheduler: Workflow plan {plan.workflow_id} executed successfully.")
        
        if self._event_bus:
            from contracts.message import EventMessage
            evt = EventMessage(
                sender_id="SCHEDULER",
                receiver_id="BROADCAST",
                workflow_id=plan.workflow_id,
                msg_type="EVENT",
                event_name="SCHEDULER_FINISHED",
                payload={"stage": "scheduler", "status": "finished"}
            )
            await self._event_bus.publish(evt)

        return results

    def _instantiate_runtime(self, runtime_type: str) -> Any:
        """Dynamically imports and returns an initialised runtime kernel instance.

        Args:
            runtime_type: The string key identifying the desired runtime (e.g. 'COMPETITIVE').

        Returns:
            An initialised instance of the matching RuntimeContract subclass.

        Raises:
            ValueError: If the runtime_type string is not registered in _RUNTIME_MAP.
        """
        if runtime_type not in self._RUNTIME_MAP:
            raise ValueError(
                f"Scheduler Error: Unknown runtime assignment '{runtime_type}'."
            )

        module_name, class_name = self._RUNTIME_MAP[runtime_type]
        module = importlib.import_module(module_name)
        runtime_class = getattr(module, class_name)

        # Supply constructor dependencies based on runtime type
        if runtime_type == "COMPETITIVE":
            return runtime_class(router=self._router, event_bus=self._event_bus)
        elif runtime_type == "STANDARD":
            return runtime_class(router=self._router, event_bus=self._event_bus)
        elif runtime_type == "MICRO":
            return runtime_class(router=self._router, event_bus=self._event_bus)
        elif runtime_type == "DIRECT":
            return runtime_class(router=self._router, event_bus=self._event_bus)
        elif runtime_type == "RETRIEVAL":
            return runtime_class(memory_manager=self._memory_manager, event_bus=self._event_bus)

        # Fallback – attempt no-arg construction for future runtimes
        return runtime_class()

    async def _execute_node_with_semaphore(
        self,
        node: WorkflowNode,
        workflow_id: str,
        completed_results: Dict[str, EvaluationReport],
    ) -> EvaluationReport:
        """Executes an individual node wrapped inside the concurrent throttle semaphore.

        Args:
            node: The workflow node to execute.
            workflow_id: Parent workflow session ID for workspace isolation.
            completed_results: Shared dict accumulating prior node results.

        Returns:
            The EvaluationReport produced by the runtime.

        Raises:
            RuntimeError: If a dependency node has previously failed.
            ValueError: If the TCB contains an unknown runtime type or validation fails.
            asyncio.TimeoutError: If execution exceeds the TCB-defined timeout.
        """
        async with self._semaphore:
            tcb = node.tcb
            runtime_type = tcb.assigned_runtime

            # Register PCB and move to QUEUED
            pcb = ProcessControlBlock(
                pcb_id=node.node_id, workflow_id=workflow_id, runtime=runtime_type
            )
            self._lifecycle_mgr.transition(pcb, ProcessState.QUEUED)
            
            if self._event_bus:
                from contracts.message import EventMessage
                from contracts.workflow import RuntimeDecision
                decision = RuntimeDecision(
                    candidate_runtimes=["COMPETITIVE", "STANDARD", "MICRO", "DIRECT", "RETRIEVAL"],
                    selected_runtime=runtime_type,
                    selection_score=0.98,
                    reason=f"Matched required reasoning tier {tcb.primary_capability.minimum_reasoning_tier}",
                    estimated_cost_usd=tcb.primary_capability.cost_ceiling_usd,
                    estimated_latency_ms=1000.0,
                    capability_match_score=1.0
                )
                asyncio.create_task(self._event_bus.publish(EventMessage(
                    sender_id="SCHEDULER",
                    receiver_id="EVENT",
                    workflow_id=tcb.workflow_id,
                    msg_type="EVENT",
                    event_name="RuntimeDecision",
                    payload=decision.model_dump()
                )))
                
                asyncio.create_task(self._event_bus.publish(EventMessage(
                    sender_id="SCHEDULER",
                    receiver_id="EVENT",
                    workflow_id=tcb.workflow_id,
                    msg_type="EVENT",
                    event_name="Runtime Selected",
                    payload={"runtime": runtime_type, "node_id": tcb.tcb_id}
                )))

                asyncio.create_task(self._event_bus.publish(EventMessage(
                    sender_id="SCHEDULER",
                    receiver_id="EVENT",
                    workflow_id=workflow_id,
                    msg_type="EVENT",
                    event_name="Agent Spawned",
                    payload={"node_id": node.node_id, "state": "QUEUED"}
                )))

            # Check dependency pre-conditions
            for dep in node.dependencies:
                dep_res = completed_results.get(dep)
                if not dep_res or getattr(dep_res, "winner", None) == "FAILED":
                    err_msg = (
                        f"Dependency node '{dep}' failed or was skipped."
                        f" Aborting node '{node.node_id}'."
                    )
                    logger.warning(err_msg)
                    self._lifecycle_mgr.transition(
                        pcb, ProcessState.TERMINATED, TerminationReason.FAILED
                    )
                    raise RuntimeError(err_msg)

            # Dynamic Instantiation
            try:
                runtime = self._instantiate_runtime(runtime_type)
            except ValueError as ve:
                logger.critical(str(ve))
                self._lifecycle_mgr.transition(
                    pcb, ProcessState.TERMINATED, TerminationReason.FAILED
                )
                raise

            logger.info(
                f"Scheduler: Dispatching node {node.node_id} to {runtime_type} runtime."
            )
            
            if self._event_bus:
                await self._event_bus.publish(EventMessage(
                    sender_id="SCHEDULER",
                    receiver_id="EVENT",
                    workflow_id=workflow_id,
                    msg_type="EVENT",
                    event_name="Runtime Selected",
                    payload={"node_id": node.node_id, "runtime_type": runtime_type}
                ))
                
            self._lifecycle_mgr.transition(pcb, ProcessState.EXECUTING)

            # Pre-execution: Acquire sandbox workspace
            self._factory.provision_container(workflow_id)

            try:
                # Enforce validation
                if not await runtime.validate(tcb):
                    raise ValueError(
                        f"TCB validation failed on runtime: {runtime_type}"
                    )

                await runtime.initialize(tcb.payload)

                timeout_sec = tcb.timeout_ms / 1000.0
                result = await asyncio.wait_for(
                    runtime.execute(), timeout=timeout_sec
                )

                completed_results[node.node_id] = result
                self._lifecycle_mgr.transition(
                    pcb, ProcessState.TERMINATED, TerminationReason.COMPLETED
                )
                return result

            except asyncio.TimeoutError:
                logger.error(
                    f"Scheduler Node Timeout: Node {node.node_id} timed out after {timeout_sec}s."
                )
                self._lifecycle_mgr.transition(
                    pcb, ProcessState.TERMINATED, TerminationReason.KILLED
                )
                await runtime.terminate()
                raise
            except RuntimeError as e:
                import sys
                error_msg = f"[Kernel Fault] Execution failed on Node {node.node_id}: {e}"
                print(error_msg, file=sys.stderr)
                logger.error(error_msg)
                self._lifecycle_mgr.transition(
                    pcb, ProcessState.TERMINATED, TerminationReason.FAILED
                )
                from contracts.workflow import RuntimeResult
                fallback = RuntimeResult(
                    output=f"Execution Interrupted: RUNTIME ERROR\nReason: {e}",
                    winner="RUNTIME ERROR",
                    confidence=0.0,
                    reason="Provider chain exhaustion or localized structural fault.",
                    provider="fallback",
                    model="none",
                    token_usage={},
                    estimated_cost_usd=0.0,
                    latency_ms=0.0,
                    runtime_type=runtime_type,
                    metrics={"fault": str(e)}
                )
                completed_results[node.node_id] = fallback
                return fallback
            except Exception as e:
                logger.error(
                    f"Scheduler Node Crash: Node {node.node_id} encountered execution crash: {e}"
                )
                self._lifecycle_mgr.transition(
                    pcb, ProcessState.TERMINATED, TerminationReason.FAILED
                )
                raise
            finally:
                # Guarantee cleanup on all exit paths including fatal crashes
                await runtime.cleanup()
                self._factory.recycle_container(workflow_id)
                if self._router and hasattr(self._router, "purge_workflow"):
                    self._router.purge_workflow(workflow_id)

