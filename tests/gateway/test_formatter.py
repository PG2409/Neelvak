import pytest
from gateway.formatter import ResponseFormatter
from contracts.workflow import RuntimeResult

def test_formatter_strips_metadata():
    rf = ResponseFormatter()
    raw = "Here is the response. [Kernel] PCB_1A2B executed successfully. [System] PCB_9F executed."
    clean = rf.clean_output(raw)
    assert "PCB_1A2B" not in clean
    assert "PCB_9F" not in clean
    assert "[Kernel]" not in clean
    assert "Here is the response. executed successfully. executed." in clean or "Here is the response." in clean

def test_formatter_strips_json_tags():
    rf = ResponseFormatter()
    raw = "Output text. <json>{'a': 1}</json> More text."
    clean = rf.clean_output(raw)
    assert "<json>" not in clean
    assert "{'a': 1}" not in clean

def test_formatter_packages_metadata():
    rf = ResponseFormatter()
    result = RuntimeResult(
        workflow_id="test",
        winner="Local",
        output="Result [Kernel]",
        token_usage={"prompt_tokens": 0, "completion_tokens": 0},
        estimated_cost_usd=0.001,
        latency_ms=10.0,
        provider="groq",
        model="llama3",
        confidence=1.0,
        reason="Test",
        runtime_type="STANDARD"
    )
    formatted = rf.format_runtime_result(result)
    assert formatted["output"] == "Result"
    assert formatted["metadata"]["estimated_cost_usd"] == 0.001
    assert formatted["metadata"]["latency_ms"] == 10.0
    assert formatted["metadata"]["provider"] == "groq"
    assert formatted["metadata"]["model"] == "llama3"
