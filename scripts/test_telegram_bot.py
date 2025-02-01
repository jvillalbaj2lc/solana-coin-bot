#!/usr/bin/env python3
"""
Script to test Telegram bot functionality.
Tests connection, message sending, and error handling.
"""

import sys
import os
import logging
import json
from typing import Optional, Dict, Any
from dataclasses import dataclass

# Add the app directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.telegram_notifier import TelegramNotifier, NotifierConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
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

def test_bot_connection(notifier: TelegramNotifier) -> Dict[str, Any]:
    """Test basic bot connection and credentials."""
    notifier._validate_credentials()
    return {
        "bot_token": f"{notifier.config.bot_token[:6]}...{notifier.config.bot_token[-6:]}",
        "chat_id": notifier.config.chat_id
    }

def test_send_plain_message(notifier: TelegramNotifier) -> Dict[str, Any]:
    """Test sending a plain text message."""
    message = (
        "🤖 Test Message: Hello from the Solana Coin Bot!\n"
        "This is a test of the notification system."
    )
    try:
        response = notifier.session.post(
            f"https://api.telegram.org/bot{notifier.config.bot_token}/sendMessage",
            json={
                "chat_id": notifier.config.chat_id,
                "text": message
            },
            timeout=notifier.config.timeout
        )
        response_data = response.json()
        
        if not response.ok:
            raise Exception(f"API Error: {json.dumps(response_data, indent=2)}")
            
        return {
            "message_length": len(message),
            "response": response_data
        }
    except Exception as e:
        raise Exception(f"Failed to send plain text message: {str(e)}")

def test_send_html_message(notifier: TelegramNotifier) -> Dict[str, Any]:
    """Test sending a message with HTML formatting."""
    message = (
        "<b>🚀 Token Alert Test</b>\n\n"
        "<i>Testing HTML Formatting:</i>\n"
        "• <b>Bold Text</b>\n"
        "• <i>Italic Text</i>\n"
        "• <code>Monospace Text</code>\n"
        "• <a href='https://dexscreener.com'>Link Test</a>"
    )
    try:
        response = notifier.session.post(
            f"https://api.telegram.org/bot{notifier.config.bot_token}/sendMessage",
            json={
                "chat_id": notifier.config.chat_id,
                "text": message,
                "parse_mode": "HTML"
            },
            timeout=notifier.config.timeout
        )
        response_data = response.json()
        
        if not response.ok:
            raise Exception(f"API Error: {json.dumps(response_data, indent=2)}")
            
        return {
            "message_length": len(message),
            "response": response_data
        }
    except Exception as e:
        raise Exception(f"Failed to send HTML message: {str(e)}")

def test_send_token_alert(notifier: TelegramNotifier) -> Dict[str, Any]:
    """Test sending a formatted token alert message."""
    message = (
        "<b>🔥 New Token Alert (TEST)</b>\n\n"
        "<b>Token:</b> <code>TEST123...abc</code>\n"
        "<b>Chain:</b> Solana\n"
        "<b>Price:</b> $0.12345\n"
        "<b>24h Change:</b> +15.67%\n"
        "<b>Liquidity:</b> $100,000\n"
        "<b>Volume:</b> $50,000\n\n"
        "<b>Risk Score:</b> LOW (250)\n"
        "<b>DexScreener:</b> <a href='https://dexscreener.com/test'>View Chart</a>"
    )
    try:
        response = notifier.session.post(
            f"https://api.telegram.org/bot{notifier.config.bot_token}/sendMessage",
            json={
                "chat_id": notifier.config.chat_id,
                "text": message,
                "parse_mode": "HTML"
            },
            timeout=notifier.config.timeout
        )
        response_data = response.json()
        
        if not response.ok:
            raise Exception(f"API Error: {json.dumps(response_data, indent=2)}")
            
        return {
            "message_length": len(message),
            "response": response_data
        }
    except Exception as e:
        raise Exception(f"Failed to send token alert message: {str(e)}")

def main():
    """Run all Telegram bot tests."""
    logger.info("Starting Telegram Bot Tests")
    
    # Initialize notifier with test config
    config = NotifierConfig()
    notifier = TelegramNotifier(config)
    
    # Define test cases
    tests = [
        ("Bot Connection", lambda: test_bot_connection(notifier)),
        ("Plain Message", lambda: test_send_plain_message(notifier)),
        ("HTML Message", lambda: test_send_html_message(notifier)),
        ("Token Alert", lambda: test_send_token_alert(notifier))
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
        else:
            logger.error(f"❌ {name}: FAILED - {result.error}")
    
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