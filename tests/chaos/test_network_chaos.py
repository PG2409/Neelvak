import pytest
import asyncio
import httpx
from tests.chaos.injector import ChaosInjector
from tests.behavioral.engine import BehavioralEngine
from models.health import ProviderState

@pytest.fixture
def engine():
    return BehavioralEngine()

@pytest.fixture(autouse=True)
def mock_api_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "real-key")
    monkeypatch.setenv("GROQ_API_KEY", "real-key")

@pytest.mark.asyncio
async def test_network_timeout_recovery(engine):
    with ChaosInjector({"chaos_network_timeout": True}):
        with pytest.raises(asyncio.TimeoutError, match="Chaos: Network Timeout"):
            await engine.execute_simulated_runtime("DIRECT", {})

@pytest.mark.asyncio
async def test_network_disconnect(engine):
    with ChaosInjector({"chaos_network_disconnect": True}):
        with pytest.raises(httpx.ConnectError, match="Connection Reset by Peer"):
            await engine.execute_simulated_runtime("DIRECT", {})

@pytest.mark.asyncio
async def test_network_dns_failure(engine):
    with ChaosInjector({"chaos_network_dns": True}):
        with pytest.raises(httpx.ConnectError, match="DNS lookup failed"):
            await engine.execute_simulated_runtime("DIRECT", {})

@pytest.mark.asyncio
async def test_network_ssl_failure(engine):
    with ChaosInjector({"chaos_network_ssl": True}):
        with pytest.raises(httpx.ConnectError, match="SSL Handshake Failed"):
            await engine.execute_simulated_runtime("DIRECT", {})

@pytest.mark.asyncio
async def test_network_latency_injection(engine):
    with ChaosInjector({"chaos_network_latency": True, "latency_ms": 100}):
        result, logs = await engine.execute_simulated_runtime("DIRECT", {})
        assert result.winner is not None

@pytest.mark.asyncio
async def test_network_429_rate_limit(engine):
    with ChaosInjector({"chaos_network_429": True}):
        with pytest.raises(RuntimeError, match="HTTP Endpoint error 429"):
            await engine.execute_simulated_runtime("DIRECT", {})

@pytest.mark.asyncio
async def test_network_500_internal_error(engine):
    with ChaosInjector({"chaos_network_500": True}):
        with pytest.raises(RuntimeError, match="HTTP Endpoint error 500"):
            await engine.execute_simulated_runtime("DIRECT", {})

@pytest.mark.asyncio
async def test_network_malformed_response(engine):
    with ChaosInjector({"chaos_network_malformed": True}):
        with pytest.raises(KeyError): # Missing "choices" key in dict
            await engine.execute_simulated_runtime("DIRECT", {})

@pytest.mark.asyncio
async def test_network_corrupt_json(engine):
    with ChaosInjector({"chaos_network_corrupt_json": True}):
        # In DirectRuntime, if json parsing fails, it's caught or throws JSONDecodeError
        import json
        with pytest.raises(json.JSONDecodeError):
            await engine.execute_simulated_runtime("DIRECT", {})

@pytest.mark.asyncio
async def test_concurrent_provider_outage(engine):
    # If the provider is marked offline, ModelRouter should fallback
    engine.health.set_status_for_testing("openrouter", ProviderState.OFFLINE)
    engine.health.set_status_for_testing("groq", ProviderState.OFFLINE)
    
    # We execute STANDARD to use ModelRouter
    result, logs = await engine.execute_simulated_runtime("STANDARD", {})
    assert result.winner is not None
