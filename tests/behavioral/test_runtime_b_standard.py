import pytest
from tests.behavioral.engine import BehavioralEngine

@pytest.fixture
def engine():
    return BehavioralEngine()

@pytest.mark.asyncio
async def test_reflection_agent_improves(engine):
    result, logs = await engine.execute_simulated_runtime("STANDARD", {"_sim_reflection_improves": True})
    assert "[Improved by Reflection]" in result.output
    log_text = "\n".join(logs)
    assert "Reflection Agent improved the result." in log_text

@pytest.mark.asyncio
async def test_reflection_agent_makes_worse(engine):
    result, logs = await engine.execute_simulated_runtime("STANDARD", {"_sim_reflection_worse": True})
    assert "[Degraded by Reflection]" in result.output
    log_text = "\n".join(logs)
    assert "Reflection Agent made the result worse." in log_text

@pytest.mark.asyncio
async def test_surveillance_detects_hallucination(engine):
    result, logs = await engine.execute_simulated_runtime("STANDARD", {"_sim_worker_hallucinate": True})
    log_text = "\n".join(logs)
    assert "Refusal phrase matching detected: 'i cannot fulfill'" in log_text
    assert "Surveillance Agent warning: Refusal phrase matching detected" in log_text
    # Ensure Surveillance doesn't mutate output directly
    assert "[Improved by Reflection]" not in result.output
    assert "[Degraded by Reflection]" not in result.output
    assert result.winner == "Worker Agent" # It reports the warning out-of-band

@pytest.mark.asyncio
async def test_surveillance_detects_infinite_loops(engine):
    result, logs = await engine.execute_simulated_runtime("STANDARD", {"_sim_worker_infinite_loop": True})
    log_text = "\n".join(logs)
    assert "Infinite loop detected by Surveillance." in log_text
    assert "Surveillance Agent warning" in log_text

@pytest.mark.asyncio
async def test_surveillance_detects_retries(engine):
    result, logs = await engine.execute_simulated_runtime("STANDARD", {"_sim_worker_retries": True})
    log_text = "\n".join(logs)
    assert "Excessive retries detected by Surveillance." in log_text
    assert "Surveillance Agent warning" in log_text

@pytest.mark.asyncio
async def test_master_conflict_resolution(engine):
    result, logs = await engine.execute_simulated_runtime("STANDARD", {"_sim_master_conflict": True})
    log_text = "\n".join(logs)
    assert "Master: Received conflicting reports between Worker and Reflection/Surveillance." in log_text
    assert "Master: Resolving conflict independently without executing work." in log_text
    # Master correctly produces final RuntimeResult
    assert result.runtime_type == "STANDARD"

@pytest.mark.asyncio
async def test_surveillance_never_modifies_outputs(engine):
    result, logs = await engine.execute_simulated_runtime("STANDARD", {"_sim_worker_hallucinate": True})
    # Despite hallucination alerts, output from worker remains unmodified by Surveillance directly.
    # Verify no reflection mutation tags were injected — output is exactly what _run_worker returned.
    assert "[Improved by Reflection]" not in result.output
    assert "[Degraded by Reflection]" not in result.output
    assert result.winner == "Worker Agent"
    # The hallucination sim produces chunks joined with spaces
    assert "I cannot fulfill this request as an AI" in result.output

@pytest.mark.asyncio
async def test_master_never_executes_work(engine):
    result, logs = await engine.execute_simulated_runtime("STANDARD", {"_sim_master_conflict": True})
    log_text = "\n".join(logs)
    assert "Resolving conflict independently without executing work." in log_text
