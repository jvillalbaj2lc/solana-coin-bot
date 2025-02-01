#!/usr/bin/env python3
"""
Script to test DexScreener API functionality.
Tests token profile fetching and pair data retrieval.
"""

import sys
import os
import logging
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict

# Add the app directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.dexscreener_client import DexscreenerClient, TokenLink, TokenProfile

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for maximum information
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def serialize_profile(profile: TokenProfile) -> Dict[str, Any]:
    """Convert a TokenProfile to a serializable dictionary."""
    data = {
        "url": profile.url,
        "chain_id": profile.chain_id,
        "token_address": profile.token_address,
        "icon": profile.icon,
        "header": profile.header,
        "open_graph": profile.open_graph,
        "description": profile.description,
        "links": [
            {
                "url": link.url,
                "type": link.type,
                "label": link.label
            }
            for link in (profile.links or [])
        ]
    }
    return data

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

def test_get_latest_profiles(client: DexscreenerClient) -> Dict[str, Any]:
    """Test fetching latest token profiles."""
    profiles = client.get_latest_token_profiles()
    
    logger.info(f"Retrieved {len(profiles)} token profiles")
    
    # Log details for each profile
    for idx, profile in enumerate(profiles):
        logger.info(f"\nProfile {idx + 1}:")
        logger.info(f"Token Address: {profile.token_address}")
        logger.info(f"Chain: {profile.chain_id}")
        logger.info(f"URL: {profile.url}")
        if profile.description:
            logger.info(f"Description: {profile.description[:100]}...")  # Truncate long descriptions
        if profile.links:
            logger.info("Links:")
            for link in profile.links:
                logger.info(f"  - {link.type or 'unknown'}: {link.url}")
    
    result = {
        "total_profiles": len(profiles),
        "sample_profile": serialize_profile(profiles[0]) if profiles else None,
        "sample_raw": str(vars(profiles[0])) if profiles else None
    }
    
    if not profiles:
        raise Exception("No profiles returned")
        
    return result

def test_get_token_pairs(client: DexscreenerClient, profile: Dict[str, Any]) -> Dict[str, Any]:
    """Test fetching token pairs for a specific token."""
    logger.info(f"\nTesting pairs for token:")
    logger.info(f"Chain ID: {profile['chain_id']}")
    logger.info(f"Token Address: {profile['token_address']}")
    logger.info(f"Token URL: {profile['url']}")
    
    pairs = client.get_token_pairs(profile["chain_id"], profile["token_address"])
    
    # Log the raw response for debugging
    logger.debug(f"Raw pairs response: {json.dumps(pairs, indent=2)}")
    
    # Extract token information from the first pair if available
    token_info = {}
    if pairs:
        base_token = pairs[0].get('baseToken', {})
        token_info = {
            "name": base_token.get('name', 'unknown'),
            "symbol": base_token.get('symbol', 'unknown')
        }
        logger.info(f"Token Details - Name: {token_info['name']}, Symbol: {token_info['symbol']}")
    
    result = {
        "token_address": profile["token_address"],
        "chain_id": profile["chain_id"],
        "token_info": token_info,
        "total_pairs": len(pairs),
        "sample_pair": pairs[0] if pairs else None,
        "raw_response": pairs
    }
    
    # Don't raise exception if no pairs, just log it
    if not pairs:
        logger.warning(f"No pairs found for token {profile['token_address']}")
    else:
        logger.info(f"\nFound {len(pairs)} pairs:")
        for idx, pair in enumerate(pairs):
            logger.info(f"\nPair {idx + 1} details:")
            logger.info(f"DEX: {pair.get('dexId', 'unknown')}")
            quote_token = pair.get('quoteToken', {})
            logger.info(f"Trading Pair: {token_info['symbol']}/{quote_token.get('symbol', 'unknown')}")
            logger.info(f"Price USD: ${pair.get('priceUsd', 'unknown')}")
            logger.info(f"24h Volume: ${pair.get('volume', {}).get('h24', 'unknown')}")
            logger.info(f"Liquidity USD: ${pair.get('liquidity', {}).get('usd', 'unknown')}")
    
    return result

def test_pair_data_extraction(pair: Dict[str, Any]) -> Dict[str, Any]:
    """Test extracting metrics from pair data."""
    if not pair:
        raise Exception("No pair data provided for testing")
    
    logger.info("\nExtracting data from pair:")
    logger.info(f"DEX: {pair.get('dexId', 'unknown')}")
    logger.info(f"Pair Address: {pair.get('pairAddress', 'unknown')}")
    
    # Extract metrics with detailed logging
    price_usd = pair.get('priceUsd')
    volume = pair.get('volume', {})
    liquidity = pair.get('liquidity', {})
    
    extracted = {
        "price_usd": price_usd,
        "volume_24h": volume.get('h24') if isinstance(volume, dict) else None,
        "liquidity_usd": liquidity.get('usd') if isinstance(liquidity, dict) else None
    }
    
    result = {
        "raw_pair": pair,
        "extracted_data": extracted
    }
    
    # Log the extracted values
    logger.info("\nExtracted metrics:")
    logger.info(f"Price USD: ${extracted['price_usd']}")
    logger.info(f"24h Volume: ${extracted['volume_24h']}")
    logger.info(f"Liquidity USD: ${extracted['liquidity_usd']}")
    
    return result

def main():
    """Run all DexScreener API tests."""
    logger.info("Starting DexScreener API Tests")
    
    # Initialize client
    client = DexscreenerClient()
    
    # Store test profile for reuse
    test_profile = None
    
    # Define test cases
    tests = [
        ("Get Latest Profiles", lambda: test_get_latest_profiles(client))
    ]
    
    # Run tests and collect results
    results = []
    for name, test_func in tests:
        logger.info(f"Running test: {name}")
        result = run_test(name, test_func)
        results.append(result)
        
        if result.passed:
            logger.info(f"✅ {name}: PASSED")
            if result.debug_info:
                logger.info(f"Debug Info: {json.dumps(result.debug_info, indent=2)}")
                
                # Store first profile for pair tests
                if name == "Get Latest Profiles" and result.debug_info.get("sample_profile"):
                    test_profile = result.debug_info["sample_profile"]
        else:
            logger.error(f"❌ {name}: FAILED - {result.error}")
    
    # Add pair tests if we have a test profile
    if test_profile:
        pair_test = ("Get Token Pairs", lambda: test_get_token_pairs(client, test_profile))
        result = run_test(*pair_test)
        results.append(result)
        
        if result.passed:
            logger.info("✅ Get Token Pairs: PASSED")
            if result.debug_info:
                logger.info(f"Debug Info: {json.dumps(result.debug_info, indent=2)}")
                
                # Test pair data extraction if we have pairs
                pairs = result.debug_info.get("raw_response", [])
                if pairs:
                    extraction_test = ("Parse Pair Data", lambda: test_pair_data_extraction(pairs[0]))
                    result = run_test(*extraction_test)
                    results.append(result)
                    
                    if result.passed:
                        logger.info("✅ Parse Pair Data: PASSED")
                        logger.info(f"Debug Info: {json.dumps(result.debug_info, indent=2)}")
                    else:
                        logger.error(f"❌ Parse Pair Data: FAILED - {result.error}")
                else:
                    logger.warning("Skipping pair data extraction test - no pairs found")
        else:
            logger.error(f"❌ Get Token Pairs: FAILED - {result.error}")
    
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