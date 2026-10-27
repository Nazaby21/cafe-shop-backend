"""
Automated pytest wrapper for the cross-service integration check.
"""
from scripts.run_integration_check import run_integration_check


def test_cross_service_integration_e2e():
    exit_code = run_integration_check()
    assert exit_code == 0
