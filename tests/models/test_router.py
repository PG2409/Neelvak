import pytest
from contracts.workflow import CapabilityProfile
from models.health import ProviderHealthManager, ProviderState
from models.router import ModelRouter

@pytest.mark.asyncio
async def test_flapping_mitigation():
    """Verify that a single network timeout shifts state to DEGRADED, not OFFLINE."""
    health_mgr = ProviderHealthManager()
    # Force state to HEALTHY initially
    health_mgr.set_status_for_testing("groq", ProviderState.HEALTHY)
    
    # Simulate 1 network failure
    health_mgr.record_failure("groq")
    
    assert health_mgr.get_status("groq") == ProviderState.DEGRADED

@pytest.mark.asyncio
async def test_model_diversity_enforcement():
    """Verify consecutive requests with the same diversity_group_id route to distinct provider families."""
    health_mgr = ProviderHealthManager()
    # Ensure both are healthy
    health_mgr.set_status_for_testing("groq", ProviderState.HEALTHY)
    health_mgr.set_status_for_testing("openrouter", ProviderState.HEALTHY)
    
    router = ModelRouter(health_mgr)
    
    profile = CapabilityProfile(minimum_reasoning_tier="LOW", diversity_group_id="div-1")
    workflow_id = "test-wf-div"
    
    # First request
    provider1, model1, meta1 = router.resolve_capability(profile, workflow_id)
    assert "reduced_diversity" not in meta1
    
    # Second request
    provider2, model2, meta2 = router.resolve_capability(profile, workflow_id)
    assert "reduced_diversity" not in meta2
    
    # Assert they are distinct providers (groq vs openrouter)
    assert provider1 != provider2

@pytest.mark.asyncio
async def test_degradation_resiliency_verification():
    """Verify that if diversity is mathematically impossible, it degrades to the remaining healthy path gracefully."""
    health_mgr = ProviderHealthManager()
    
    # Simulate Groq is OFFLINE
    health_mgr.set_status_for_testing("groq", ProviderState.OFFLINE)
    health_mgr.set_status_for_testing("openrouter", ProviderState.HEALTHY)
    
    router = ModelRouter(health_mgr)
    profile = CapabilityProfile(minimum_reasoning_tier="LOW", diversity_group_id="div-2")
    workflow_id = "test-wf-deg"
    
    # First request -> Should route to openrouter
    provider1, model1, meta1 = router.resolve_capability(profile, workflow_id)
    assert provider1 == "openrouter"
    assert "reduced_diversity" not in meta1
    
    # Second request -> Diversity requires groq, but it's offline. Must fallback to openrouter.
    provider2, model2, meta2 = router.resolve_capability(profile, workflow_id)
    assert provider2 == "openrouter"
    
    # Should flag the reduction in diversity
    assert meta2.get("reduced_diversity") is True
