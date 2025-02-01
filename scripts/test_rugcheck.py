#!/usr/bin/env python3
"""
Script to test RugCheck API functionality.
Tests token risk assessment and validation.
"""

import sys
import os
import logging
import json
from typing import Optional, Dict, Any
from dataclasses import dataclass

# Add the app directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.rugcheck_service import RugcheckService

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class TestResult:
    """Represents the result of a test case."""
    name: str
    passed: bool
    error: Optional[str] = None
    debug_info: Optional[Dict[str, Any]] = None

def run_test(name: str, test_func) -> TestResult:
    """Run a test and return its result."""
    try:
        debug_info = test_func()
        return TestResult(name=name, passed=True, debug_info=debug_info)
    except Exception as e:
        return TestResult(name=name, passed=False, error=str(e))

def test_rugcheck_assessment(rugcheck: RugcheckService, token_address: str) -> Dict[str, Any]:
    """Test token risk assessment for a specific token."""
    logger.info(f"\nTesting RugCheck assessment for token:")
    logger.info(f"Token Address: {token_address}")
    
    assessment = rugcheck.assess_token_risk(token_address)
    
    result = {
        "token_address": token_address,
        "is_safe": assessment.is_safe,
        "score": assessment.score,
        "risks": assessment.risks,
        "token_program": assessment.token_program,
        "token_type": assessment.token_type
    }
    
    logger.info("\nRugCheck Assessment Results:")
    logger.info(f"Safety Status: {'✅ SAFE' if assessment.is_safe else '❌ UNSAFE'}")
    logger.info(f"Risk Score: {assessment.score}")
    if assessment.risks:
        logger.info("\nIdentified Risks:")
        for risk in assessment.risks:
            logger.info(f"- {risk}")
    logger.info(f"Token Program: {assessment.token_program}")
    logger.info(f"Token Type: {assessment.token_type}")
    
    return result

def main():
    """Run RugCheck API tests."""
    logger.info("Starting RugCheck API Tests")
    
    # Load configuration
    config_path = os.path.join("configs", "config.json")
    try:
        with open(config_path) as f:
            config = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)
    
    # Initialize RugCheck client
    rugcheck_cfg = config.get("rugcheck", {})
    max_risk_score = rugcheck_cfg.get("max_risk_score", 1000)
    
    rugcheck = RugcheckService(max_risk_score=max_risk_score)
    logger.info(f"Initialized RugCheck service with max risk score: {max_risk_score}")
    
    # Test tokens
    test_tokens = [
        "2iU5qDuGoBzegJhHrkTL19t6RfR2pSWq3KEuxGKvpump",  # Known token from RugCheck
        "3mn4TrUGUwxB4LPo8arBTx7sPMptBZ8n8Gdugu46us6c",  # Another token to test
    ]
    
    # Run tests and collect results
    results = []
    for token_address in test_tokens:
        test_name = f"RugCheck Assessment - {token_address}"
        test_func = lambda: test_rugcheck_assessment(rugcheck, token_address)
        result = run_test(test_name, test_func)
        results.append(result)
        
        if result.passed:
            logger.info(f"✅ {test_name}: PASSED")
            if result.debug_info:
                logger.info(f"Debug Info: {json.dumps(result.debug_info, indent=2)}")
        else:
            logger.error(f"❌ {test_name}: FAILED - {result.error}")
    
    # Print summary
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    
    logger.info("\nTest Summary:")
    logger.info(f"Total Tests: {total}")
    logger.info(f"Passed: {passed}")
    logger.info(f"Failed: {failed}")
    
    # Print failed tests if any
    if failed > 0:
        logger.info("\nFailed Tests:")
        for result in results:
            if not result.passed:
                logger.info(f"- {result.name}: {result.error}")
        sys.exit(1)
    
    logger.info("\n✨ All tests passed successfully!")

if __name__ == "__main__":
    main() 