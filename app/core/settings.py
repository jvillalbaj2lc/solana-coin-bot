# app/core/settings.py

import os
import logging

# -------------------------------------------------------------------------
# App Metadata
# -------------------------------------------------------------------------
APP_NAME = "Solana Coin Bot"
APP_VERSION = "0.1.0"

# -------------------------------------------------------------------------
# Logging Defaults
# -------------------------------------------------------------------------
# You can define a default log level (overridden by config or environment).
DEFAULT_LOG_LEVEL = logging.INFO

# -------------------------------------------------------------------------
# Scheduling Defaults
# -------------------------------------------------------------------------
# If you want a default fetch interval that can be overridden in config.json,
# you could define it here.
DEFAULT_FETCH_INTERVAL_SEC = 600  # 10 minutes

# -------------------------------------------------------------------------
# Environment Handling
# -------------------------------------------------------------------------
# You might have logic that checks if we're in development or production.
ENV = os.getenv("BOT_ENV", "development").lower()
IS_PRODUCTION = ENV == "production"

# You might decide that in production you want a higher log level:
if IS_PRODUCTION:
    DEFAULT_LOG_LEVEL = logging.WARNING

# -------------------------------------------------------------------------
# Other Global Constants
# -------------------------------------------------------------------------
# For instance, if you have a maximum number of tokens to fetch or maximum concurrency:
MAX_TOKENS_FETCH = 100
MAX_RETRIES = 3

# -------------------------------------------------------------------------
# Optional Helper Functions
# -------------------------------------------------------------------------
def log_current_settings():
    """
    Log a brief summary of important settings for debugging purposes.
    """
    logging.info(f"{APP_NAME} v{APP_VERSION}, ENV={ENV}, Production={IS_PRODUCTION}")
    logging.info(f"Default fetch interval: {DEFAULT_FETCH_INTERVAL_SEC}s")
    logging.info(f"Max tokens fetch: {MAX_TOKENS_FETCH}, Max retries: {MAX_RETRIES}")
