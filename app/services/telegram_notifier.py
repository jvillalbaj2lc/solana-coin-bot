# app/services/volume_verifier.py

import logging
from typing import Dict, Any, Optional
import requests
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class NotifierConfig:
    """Configuration for the Telegram notifier."""
    bot_token: str 
    chat_id: str 
    timeout: int = 10
    max_retries: int = 3

class TelegramNotifier:
    """Service for sending notifications via Telegram."""
    
    def __init__(self, config: NotifierConfig):
        """
        Initialize the Telegram notifier.
        
        :param config: NotifierConfig instance with required settings
        """
        self.config = config
        self.session = requests.Session()
        self._consecutive_failures = 0
        self._total_requests = 0
        self._failed_requests = 0
        
        # Validate credentials on init
        self._validate_credentials()
        
    def _validate_credentials(self) -> None:
        """
        Validate the bot token and chat ID by making a test API call.
        
        :raises ValueError: If credentials are invalid
        """
        if not self.config.bot_token or not self.config.chat_id:
            raise ValueError("Missing bot token or chat ID")
            
        try:
            response = self.session.get(
                f"https://api.telegram.org/bot{self.config.bot_token}/getMe",
                timeout=self.config.timeout
            )
            response.raise_for_status()
            logger.info("Telegram credentials validated successfully")
        except Exception as e:
            raise ValueError(f"Invalid Telegram credentials: {str(e)}")

    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        Send a message via Telegram.
        
        :param message: The message to send
        :param parse_mode: Message parse mode (HTML/Markdown)
        :return: True if sent successfully, False otherwise
        """
        if not message:
            logger.warning("Attempted to send empty message")
            return False
            
        url = f"https://api.telegram.org/bot{self.config.bot_token}/sendMessage"
        data = {
            "chat_id": self.config.chat_id,
            "text": message,
            "parse_mode": parse_mode
        }
        
        for attempt in range(self.config.max_retries):
            try:
                response = self.session.post(
                    url,
                    json=data,
                    timeout=self.config.timeout
                )
                response.raise_for_status()
                
                self._consecutive_failures = 0
                self._total_requests += 1
                return True
                
            except Exception as e:
                self._consecutive_failures += 1
                self._failed_requests += 1
                
                if attempt == self.config.max_retries - 1:
                    logger.error(
                        f"Failed to send Telegram message after {self.config.max_retries} "
                        f"attempts: {str(e)}"
                    )
                    return False
                    
                logger.warning(
                    f"Telegram send attempt {attempt + 1} failed: {str(e)}. "
                    "Retrying..."
                )
        
        return False

    @property
    def is_healthy(self) -> bool:
        """Check if the notifier service is healthy."""
        return (
            self._consecutive_failures < 5 and
            (self._total_requests == 0 or
             self._failed_requests / self._total_requests < 0.25)
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        return {
            "total_requests": self._total_requests,
            "failed_requests": self._failed_requests,
            "consecutive_failures": self._consecutive_failures,
            "error_rate": (
                self._failed_requests / self._total_requests
                if self._total_requests > 0 else 0
            ),
            "is_healthy": self.is_healthy
        }

def build_notifier_from_config(config: Dict[str, Any]) -> Optional[TelegramNotifier]:
    """
    Build a TelegramNotifier instance from configuration.
    
    :param config: Configuration dictionary
    :return: TelegramNotifier instance or None if disabled/invalid
    """
    telegram_cfg = config.get("telegram", {})
    if not telegram_cfg:
        logger.info("Telegram notifications disabled (no config)")
        return None
        
    try:
        notifier_config = NotifierConfig(
            bot_token=telegram_cfg["bot_token"],
            chat_id=telegram_cfg["chat_id"],
            timeout=telegram_cfg.get("timeout", 10),
            max_retries=telegram_cfg.get("max_retries", 3)
        )
        
        return TelegramNotifier(notifier_config)
        
    except Exception as e:
        logger.error(f"Failed to initialize Telegram notifier: {str(e)}")
        return None
