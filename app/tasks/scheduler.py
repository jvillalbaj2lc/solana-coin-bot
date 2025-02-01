# app/tasks/scheduler.py

import time
import logging
from typing import Dict, Any
from app.tasks.fetch_and_store import fetch_and_store_tokens
from app.services.analysis import analyze_token_trends
from app.database.base import SessionLocal

logger = logging.getLogger(__name__)

def run_scheduler(config: Dict[str, Any], interval_sec: int = 600) -> None:
    """
    A simple scheduler that repeatedly:
      1) Fetches and stores tokens.
      2) (Optionally) runs analysis to detect pumped tokens.
      3) Waits 'interval_sec' seconds.
    
    :param config: Application configuration dict.
    :param interval_sec: Interval (in seconds) at which to run the cycle (default: 10 minutes).
    """
    while True:
        try:
            logger.info("Starting fetch_and_store_tokens cycle...")
            fetch_and_store_tokens(config)
        except Exception as e:
            logger.error(f"Error in fetch_and_store_tokens: {e}")

        try:
            logger.info("Starting analysis cycle...")
            with SessionLocal() as session:
                # Example: Detect tokens pumped over the last 6 hours with >= 50% increase
                flagged_tokens = analyze_token_trends(
                    session,
                    config,
                    lookback_hours=6,
                    price_increase_threshold=50.0
                )
                
                # If tokens are flagged, you could notify via Telegram or other channels
                if flagged_tokens:
                    for token_addr, pct_change in flagged_tokens:
                        message = (f"BUY SIGNAL: Token {token_addr} pumped "
                                   f"{pct_change:.2f}% in the last 6 hours!")
                        _send_buy_signal(message, config)
        except Exception as e:
            logger.error(f"Error in analysis cycle: {e}")

        logger.info("Scheduler sleeping for %d seconds.", interval_sec)
        time.sleep(interval_sec)


def _send_buy_signal(message: str, config: Dict[str, Any]) -> None:
    """
    Helper to send a buy signal or notification if needed.
    Here, we'll just log it. In a real scenario, you might use
    the telegram_notifier to send to your group/channel.
    """
    # If you have a telegram_notifier module, you can do:
    # from app.services.telegram_notifier import TelegramNotifier
    # tconf = config.get("telegram", {})
    # notifier = TelegramNotifier(tconf["bot_token"], tconf["chat_id"])
    # notifier.send_message(message)
    
    logger.info(f"BUY SIGNAL => {message}")
