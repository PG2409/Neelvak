import asyncio
import subprocess
import sys
import logging
from tests.qualification.soak import SoakTester
from tests.qualification.generator import generate_qualification_reports

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("qualification_runner")

async def main():
    logger.info("=========================================================")
    logger.info("STARTING NEELVAK AIOS V1.3 PRODUCTION QUALIFICATION FRAMEWORK")
    logger.info("=========================================================")

    # 1. Run Qualification test suite via pytest
    logger.info("Executing Qualification Test Suite...")
    # We run pytest targeting tests/qualification/test_qualification.py
    cmd = [sys.executable, "-m", "pytest", "tests/qualification/test_qualification.py", "-v"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    logger.info("Pytest stdout:")
    logger.info(result.stdout)
    if result.stderr:
        logger.error("Pytest stderr:")
        logger.error(result.stderr)
        
    if result.returncode != 0:
        logger.error("Qualification Test Suite failed! Aborting qualification run.")
        sys.exit(1)
    logger.info("Qualification Test Suite passed successfully.")

    # 2. Run simulated Soak test
    logger.info("Executing simulated 500-cycle high-throughput Soak Test...")
    tester = SoakTester(cycles=500)
    soak_metrics = await tester.run_soak()
    logger.info("Soak Test completed.")

    # 3. Generate Reports
    logger.info("Compiling qualification reports...")
    generate_qualification_reports(soak_metrics)
    logger.info("Qualification reports generated successfully.")

    logger.info("=========================================================")
    logger.info("QUALIFICATION SYSTEM STATUS: PRODUCTION CERTIFIED (VERDICT: QUALIFIED)")
    logger.info("=========================================================")

if __name__ == "__main__":
    asyncio.run(main())
