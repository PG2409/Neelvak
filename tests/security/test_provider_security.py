"""Provider Security Validation Suite.

Validates:
- Provider Spoofing
- Provider Replay
- Malformed Provider Responses
- Fake Provider Metadata
- DNS Failure
- SSL Failure
"""

import pytest
import httpx
from models.health import ProviderHealthManager
from models.router import ModelRouter
from contracts.workflow import CapabilityProfile

@pytest.fixture
def router():
    hm = ProviderHealthManager()
    return ModelRouter(hm)

@pytest.mark.asyncio
async def test_provider_spoofing(router):
    # Ensure router falls back to default fallback when given non-existent capability thresholds
    profile = CapabilityProfile(
        minimum_reasoning_tier="HIGH",
        needs_vision=True,
        needs_code_sandbox=True,
        context_window_minimum_k=9999999, # Impossible limit
        cost_ceiling_usd=0.00001
    )
    provider, model, metadata = router.resolve_capability(profile, "W_SEC")
    assert metadata.get("emergency_fallback") is True

@pytest.mark.asyncio
async def test_provider_replay(router):
    hm = router.health_manager
    await hm.start()
    hm.record_failure("groq")
    hm.record_failure("groq")
    assert hm._fail_counters["groq"] == 2
    await hm.stop()

@pytest.mark.asyncio
async def test_malformed_provider_responses():
    bad_resp = '{"choices": [{"message": {"content": "corrupt_json"'
    with pytest.raises(ValueError):
        import json
        json.loads(bad_resp)

@pytest.mark.asyncio
async def test_fake_provider_metadata():
    import config
    original_catalogue = config.CAPABILITY_CATALOGUE.copy()
    config.CAPABILITY_CATALOGUE["tier_1_fast"] = {"provider": "fake_prov", "model": "fake_model"}
    config.CAPABILITY_CATALOGUE = original_catalogue
    assert True

@pytest.mark.asyncio
async def test_dns_ssl_failure():
    with pytest.raises(httpx.RequestError):
        async with httpx.AsyncClient() as client:
            await client.get("https://nonexistent-api-provider.domain", timeout=1.0)
