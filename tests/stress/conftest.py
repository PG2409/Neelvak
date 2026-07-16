import pytest
from tests.stress.metrics import tracker

def pytest_sessionfinish(session, exitstatus):
    """Dump metrics at the end of the test session."""
    tracker.dump_metrics("tests/stress/reports/metrics.json")
