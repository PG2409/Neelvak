"""Orchestrator for Infrastructure Stress Qualification Framework."""

import os
import subprocess
import logging
import sys

from tests.stress.generator import generate_reports

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stress_runner")

def run_cmd(cmd: str, description: str):
    logger.info(f"--- Running {description} ---")
    logger.info(f"Command: {cmd}")
    result = subprocess.run(cmd, shell=True, text=True)
    if result.returncode != 0:
        logger.error(f"FAILURE during {description}")
        # Not exiting early so we can see all reports, but mark as failure.
        return False
    return True

def main():
    logger.info("Initializing Phase 17 Infrastructure Stress Qualification Framework")
    os.makedirs("tests/stress/reports", exist_ok=True)
    
    # 1. Run the extreme stress tests
    stress_success = run_cmd("python -m pytest tests/stress/test_stress.py -v", "Extreme Load Stress Simulation")
    
    # 2. Generate the 11 Reports + Verdict
    logger.info("Generating certification reports...")
    generate_reports("tests/stress/reports/metrics.json", "tests/stress/reports/")
    
    # 3. Regression Verification (Ensure no degradation post-stress)
    logger.info("Executing Post-Stress Regression Verification...")
    regression_success = run_cmd("python -m pytest tests/ --ignore=tests/stress/", "Full Regression Suite")
    
    if not stress_success or not regression_success:
        logger.error("STRESS QUALIFICATION FAILED")
        with open("tests/stress/reports/verdict.txt", "w") as f:
            f.write("Stress Qualification Failed\n")
        sys.exit(1)
        
    logger.info("Stress Qualification Passed with Minor Bottlenecks. Check tests/stress/reports/ for deliverables.")
    sys.exit(0)

if __name__ == "__main__":
    main()
