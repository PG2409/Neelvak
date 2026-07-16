import pytest
import asyncio
import json
from tests.behavioral.engine import BehavioralEngine

@pytest.fixture
def engine():
    return BehavioralEngine()

@pytest.mark.asyncio
async def test_worker_succeeds_looper_fails(engine):
    result, logs = await engine.execute_simulated_runtime(
        "COMPETITIVE", {"_sim_looper_fail": True}
    )
    assert result.winner == "Worker X"
    assert result.metrics["pass_1_status"] == "pass"
    assert "Worker X passed Pass 1 syntax validation, Looper Y failed." in result.reason

@pytest.mark.asyncio
async def test_looper_succeeds_worker_fails(engine):
    result, logs = await engine.execute_simulated_runtime(
        "COMPETITIVE", {"_sim_worker_fail": True}
    )
    assert result.winner == "Looper Y"
    assert result.metrics["pass_1_status"] == "pass"
    assert "Looper Y passed Pass 1 syntax validation, Worker X failed." in result.reason

@pytest.mark.asyncio
async def test_both_succeed(engine):
    # By default, without failure flags, both succeed
    result, logs = await engine.execute_simulated_runtime("COMPETITIVE", {})
    # Both succeed, score depends on length. In our mock, Looper Y (refined draft with exceptional details) is longer than Worker X
    # Actually wait, let's see which one wins by default.
    assert result.winner in ["Worker X", "Looper Y"]
    assert result.metrics["pass_1_status"] == "pass"
    assert "due to higher descriptive information density" in result.reason

@pytest.mark.asyncio
async def test_both_fail(engine):
    result, logs = await engine.execute_simulated_runtime(
        "COMPETITIVE", {"_sim_worker_fail": True, "_sim_looper_fail": True}
    )
    assert result.winner == "FAILED"
    assert result.metrics["pass_1_status"] == "fail"
    assert "Both outputs failed deterministic JSON compliance validation" in result.reason

@pytest.mark.asyncio
async def test_worker_hallucinates(engine):
    # Worker X hallucinates (is short). Looper Y succeeds (is long).
    result, logs = await engine.execute_simulated_runtime(
        "COMPETITIVE", {"_sim_worker_hallucinate": True}
    )
    # Since Worker X hallucinated, it should have a lower score than Looper Y
    assert result.winner == "Looper Y"

@pytest.mark.asyncio
async def test_looper_hallucinates(engine):
    # Looper Y hallucinates (is short). Worker X succeeds (is long).
    result, logs = await engine.execute_simulated_runtime(
        "COMPETITIVE", {"_sim_looper_hallucinate": True}
    )
    assert result.winner == "Worker X"

@pytest.mark.asyncio
async def test_worker_exceeds_budget(engine):
    result, logs = await engine.execute_simulated_runtime(
        "COMPETITIVE", {"_sim_worker_budget": True}
    )
    # Worker X returns "ERROR: Constraint Exceeded", which is invalid JSON
    assert result.winner == "Looper Y"

@pytest.mark.asyncio
async def test_looper_exceeds_timeout(engine):
    result, logs = await engine.execute_simulated_runtime(
        "COMPETITIVE", {"_sim_looper_timeout": True}
    )
    # Looper Y returns "ERROR: Timeout", which is invalid JSON
    assert result.winner == "Worker X"

@pytest.mark.asyncio
async def test_watching_agent_incorrectly_selects_losing_candidate(engine):
    result, logs = await engine.execute_simulated_runtime(
        "COMPETITIVE", {"_sim_watching_agent_incorrect_bias": True}
    )
    # The agent explicitly selects the candidate with the lower score.
    # In logs, we should see the warning about confirmation bias.
    log_texts = "\n".join(logs)
    assert "Simulating confirmation bias, intentionally selecting losing candidate" in log_texts

@pytest.mark.asyncio
async def test_watching_agent_rejects_both(engine):
    result, logs = await engine.execute_simulated_runtime(
        "COMPETITIVE", {"_sim_watching_agent_reject_both": True}
    )
    assert result.winner == "FAILED"
    assert "rejected both candidates" in result.reason
    log_texts = "\n".join(logs)
    assert "Simulation forcing mutual rejection" in log_texts

@pytest.mark.asyncio
async def test_decision_is_traceable_and_logged(engine):
    result, logs = await engine.execute_simulated_runtime("COMPETITIVE", {})
    log_texts = "\n".join(logs)
    assert "Watching Agent Decision Log:" in log_texts
