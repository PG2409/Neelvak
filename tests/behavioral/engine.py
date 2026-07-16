import asyncio
import logging
import io
import contextlib
from typing import Dict, Any, Tuple, List
from contracts.workflow import TaskControlBlock, CapabilityProfile
from runtimes.base import RuntimeContract
from runtimes.competitive import CompetitiveRuntime
from runtimes.standard import StandardRuntime
from runtimes.micro import MicroRuntime
from runtimes.direct import DirectRuntime
from runtimes.retrieval import RetrievalRuntime
from models.router import ModelRouter
from models.health import ProviderHealthManager
from kernel.bus import EventBus

# Create a capturing logger handler
class LogCaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.logs = []
        
    def emit(self, record):
        self.logs.append(self.format(record))


class MockMemoryManager:
    def __init__(self, force_hit=False):
        self.force_hit = force_hit
        
    def check_cache_hit(self, prompt, css_req):
        if self.force_hit:
            return True, f"Mocked cache content for {prompt}", 0.95
        return False, None, 0.0

class BehavioralEngine:
    """Executes a runtime with explicit simulated behavioral flags in env_context."""
    
    def __init__(self):
        self.health = ProviderHealthManager()
        self.router = ModelRouter(self.health)
        self.bus = EventBus()

    async def execute_simulated_runtime(
        self, 
        runtime_name: str, 
        sim_flags: Dict[str, Any],
        task_name: str = "behavioral_sim"
    ) -> Tuple[Any, List[str]]:
        """
        Instantiates the target runtime, injects sim_flags, and runs execution.
        Returns the (RuntimeResult, logs) tuple.
        """
        # Create a fresh capture for this run
        capture_handler = LogCaptureHandler()
        capture_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        logger = logging.getLogger("neelvak_kernel")
        logger.setLevel(logging.INFO)
        logger.addHandler(capture_handler)
        
        try:
            await self.bus.start()
            
            # 1. Instantiate the runtime
            if runtime_name == "COMPETITIVE":
                runtime = CompetitiveRuntime(self.router)
            elif runtime_name == "STANDARD":
                runtime = StandardRuntime(self.router, self.bus)
            elif runtime_name == "MICRO":
                runtime = MicroRuntime(self.router)
            elif runtime_name == "DIRECT":
                runtime = DirectRuntime(self.router)
            elif runtime_name == "RETRIEVAL":
                mm = MockMemoryManager(force_hit=sim_flags.get("_sim_retrieval_hit", False))
                runtime = RetrievalRuntime(mm)
            else:
                raise ValueError(f"Unknown runtime: {runtime_name}")

            # 2. Setup TCB
            tcb = TaskControlBlock(
                workflow_id="sim-wf",
                assigned_runtime=runtime_name,
                primary_capability=CapabilityProfile(minimum_reasoning_tier="LOW")
            )
            
            # 3. Validate
            await runtime.validate(tcb)
            
            # 4. Inject payload + sim flags
            env_context = {"task_name": task_name}
            env_context.update(sim_flags)
            await runtime.initialize(env_context)
            
            # 5. Execute
            result = await runtime.execute()
            
            return result, list(capture_handler.logs)
        finally:
            await self.bus.stop()
            logger.removeHandler(capture_handler)
