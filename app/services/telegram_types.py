from dataclasses import dataclass

@dataclass
class NotifierConfig:
    """Configuration for the Telegram notifier."""
    bot_token: str 
    chat_id: str 
    timeout: int = 10
    max_retries: int = 3 