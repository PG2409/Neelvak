import pytest
from gateway.request_manager import RequestManager

def test_request_manager_initialization():
    rm = RequestManager(max_requests_per_min=10)
    assert rm.max_requests_per_min == 10

def test_request_manager_valid_payload():
    rm = RequestManager()
    payload = {"prompt": "hello", "dirty_key": "drop_me"}
    allowed, detail, sanitized = rm.validate_request(payload, "session_1")
    assert allowed is True
    assert "dirty_key" not in sanitized
    assert sanitized["prompt"] == "hello"

def test_request_manager_invalid_payload_type():
    rm = RequestManager()
    allowed, detail, sanitized = rm.validate_request("just a string", "session_2")
    assert allowed is False
    assert "Invalid Payload Structure" in detail

def test_request_manager_rate_limiting():
    rm = RequestManager(max_requests_per_min=2)
    payload = {"prompt": "test"}
    # 1
    allowed, _, _ = rm.validate_request(payload, "session_3")
    assert allowed is True
    # 2
    allowed, _, _ = rm.validate_request(payload, "session_3")
    assert allowed is True
    # 3 - Should fail
    allowed, detail, _ = rm.validate_request(payload, "session_3")
    assert allowed is False
    assert "Rate Limit Exceeded" in detail
