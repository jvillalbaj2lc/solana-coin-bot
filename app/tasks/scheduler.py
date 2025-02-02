# app/tasks/scheduler.py

import time
import logging
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dataclasses import dataclass
from app.tasks.fetch_and_store import fetch_and_store_tokens
from app.services.analysis import analyze_pumped_tokens
from app.database.base import SessionLocal
from app.services.telegram_notifier import TelegramNotifier, NotifierConfig
import threading

logger = logging.getLogger(__name__)

@dataclass
class SchedulerHealth:
    """Track scheduler health metrics."""
    last_successful_run: Optional[datetime] = None
    consecutive_failures: int = 0
    total_failures: int = 0
    last_error: Optional[str] = None
    is_running: bool = False
    start_time: Optional[datetime] = None
    
    def record_success(self) -> None:
        """Record a successful run."""
        self.last_successful_run = datetime.now()
        self.consecutive_failures = 0
    
    def record_failure(self, error: str) -> None:
        """Record a failed run."""
        self.consecutive_failures += 1
        self.total_failures += 1
        self.last_error = error
    
    @property
    def uptime(self) -> Optional[timedelta]:
        """Get scheduler uptime."""
        if self.start_time:
            return datetime.now() - self.start_time
        return None

class SchedulerError(Exception):
    """Base exception for scheduler errors."""
    pass

class TaskRunner:
    """Handles individual task execution with error handling."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.notifier = self._setup_notifier()
        self._should_stop = False
        self._message_thread = None
    
    def _setup_notifier(self) -> Optional[TelegramNotifier]:
        """Setup Telegram notifier if configured."""
        try:
            tconf = self.config.get("telegram", {})
            if tconf.get("bot_token") and tconf.get("chat_id"):
                config = NotifierConfig(
                    bot_token=tconf["bot_token"],
                    chat_id=tconf["chat_id"],
                    timeout=tconf.get("timeout", 10),
                    max_retries=tconf.get("max_retries", 3)
                )
                return TelegramNotifier(config)
        except Exception as e:
            logger.error(f"Failed to setup notifier: {e}")
        return None

    def start_message_handler(self) -> None:
        """Start the message handling thread."""
        if self.notifier:
            self._message_thread = threading.Thread(
                target=self._message_loop,
                daemon=True
            )
            self._message_thread.start()
    
    def stop_message_handler(self) -> None:
        """Stop the message handling thread."""
        self._should_stop = True
        if self._message_thread:
            self._message_thread.join(timeout=5.0)
    
    def _message_loop(self) -> None:
        """Background thread to handle incoming messages."""
        if not self.notifier:
            return
            
        last_update_id = 0
        while not self._should_stop:
            try:
                # Get updates from Telegram
                response = self.notifier.session.get(
                    f"https://api.telegram.org/bot{self.notifier.config.bot_token}/getUpdates",
                    params={
                        "offset": last_update_id + 1,
                        "timeout": 30
                    }
                )
                
                if response.ok:
                    updates = response.json()
                    if updates.get("ok") and updates.get("result"):
                        for update in updates["result"]:
                            # Process the update
                            if "message" in update:
                                self.notifier.handle_message(update["message"])
                            last_update_id = update["update_id"]
                
                time.sleep(1)  # Small delay to prevent hammering the API
                
            except Exception as e:
                logger.error(f"Error in message loop: {e}")
                time.sleep(5)  # Longer delay on error
    
    def run_fetch_and_store(self) -> None:
        """Run the fetch and store task with error handling."""
        try:
            logger.info("Starting fetch_and_store_tokens cycle...")
            fetch_and_store_tokens(self.config)
        except Exception as e:
            error_msg = f"Error in fetch_and_store_tokens: {str(e)}"
            logger.exception(error_msg)
            self.notify_error(error_msg)
            raise SchedulerError(error_msg)

    def run_analysis(self) -> None:
        """Run the analysis task with error handling."""
        try:
            logger.info("Starting analysis cycle...")
            with SessionLocal() as session:
                flagged_tokens = analyze_pumped_tokens(
                    session,
                    lookback_minutes=360,  # 6 hours
                    min_price_increase_percent=50.0,
                    min_volume_usd=1000.0
                )
                
                if flagged_tokens:
                    for token in flagged_tokens:
                        message = (
                            f"🚀 <b>Token Alert</b>\n\n"
                            f"<b>Token:</b> <code>{token['token_address']}</code>\n"
                            f"<b>Price Change:</b> +{token['price_change_percent']:.2f}%\n"
                            f"<b>Current Price:</b> ${token['current_price']:.8f}\n"
                            f"<b>Volume:</b> ${token['volume_usd']:,.0f}\n"
                            f"<b>Liquidity:</b> ${token.get('liquidity_usd', 0):,.0f}\n"
                            f"<b>Risk Level:</b> {token.get('risk_level', 'Unknown')}\n"
                            f"<b>Chart:</b> <a href='{token['dexscreener_url']}'>View on DexScreener</a>"
                        )
                        self.send_notification(message)
        except Exception as e:
            error_msg = f"Error in analysis cycle: {str(e)}"
            logger.exception(error_msg)
            self.notify_error(error_msg)
            raise SchedulerError(error_msg)

    def send_notification(self, message: str) -> None:
        """Send a notification message."""
        logger.info(f"NOTIFICATION => {message}")
        if self.notifier:
            try:
                self.notifier.send_message(message)
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")

    def notify_error(self, error_msg: str) -> None:
        """Send error notification."""
        message = f"⚠️ Bot Error: {error_msg}"
        self.send_notification(message)

class Scheduler:
    """Enhanced scheduler with health monitoring and recovery."""
    
    def __init__(
        self,
        config: Dict[str, Any],
        interval_sec: int = 600,
        max_consecutive_failures: int = 3,
        error_cooldown_sec: int = 30
    ):
        self.config = config
        self.interval_sec = interval_sec
        self.max_consecutive_failures = max_consecutive_failures
        self.error_cooldown_sec = error_cooldown_sec
        self.health = SchedulerHealth()
        self.task_runner = TaskRunner(config)
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self) -> None:
        """Setup handlers for system signals."""
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
    
    def _handle_shutdown(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals gracefully."""
        logger.info("Received shutdown signal, stopping scheduler...")
        self.health.is_running = False
        # Notify about shutdown
        self.task_runner.send_notification("🔄 Bot is shutting down...")
    
    def run(self) -> None:
        """Run the scheduler with enhanced error handling and recovery."""
        self.health.is_running = True
        self.health.start_time = datetime.now()
        self.task_runner.send_notification("🟢 Bot started successfully!")
        
        try:
            # Start message handler
            self.task_runner.start_message_handler()
            
            while self.health.is_running:
                try:
                    self._run_cycle()
                    self.health.record_success()
                    
                except SchedulerError as e:
                    self.health.record_failure(str(e))
                    
                    if self.health.consecutive_failures >= self.max_consecutive_failures:
                        error_msg = (
                            f"⛔ Critical: {self.max_consecutive_failures} consecutive failures. "
                            f"Last error: {self.health.last_error}"
                        )
                        logger.error(error_msg)
                        self.task_runner.notify_error(error_msg)
                        # Add exponential backoff for recovery
                        cooldown = self.error_cooldown_sec * (2 ** (self.health.consecutive_failures - 1))
                        logger.info(f"Backing off for {cooldown} seconds before retry...")
                        time.sleep(cooldown)
                    
                except Exception as e:
                    error_msg = f"Unexpected error in scheduler: {str(e)}"
                    logger.exception(error_msg)
                    self.health.record_failure(error_msg)
                    self.task_runner.notify_error(error_msg)
                
                # Sleep until next cycle
                logger.info(f"Scheduler sleeping for {self.interval_sec} seconds.")
                time.sleep(self.interval_sec)
            
        except KeyboardInterrupt:
            logger.info("Shutting down scheduler...")
        finally:
            self.task_runner.stop_message_handler()
        
        logger.info("Scheduler stopped.")
    
    def _run_cycle(self) -> None:
        """Run a single scheduler cycle."""
        self.task_runner.run_fetch_and_store()
        self.task_runner.run_analysis()

def run_scheduler(config: Dict[str, Any], interval_sec: int = 600) -> None:
    """
    Run the enhanced scheduler with proper error handling and recovery.
    
    :param config: Application configuration dict
    :param interval_sec: Interval between cycles in seconds (default: 10 minutes)
    """
    scheduler = Scheduler(
        config=config,
        interval_sec=interval_sec,
        max_consecutive_failures=3,
        error_cooldown_sec=30
    )
    scheduler.run()
