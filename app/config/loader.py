import os
import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

class ConfigError(Exception):
    """Custom exception for configuration-related errors."""
    pass

def load_config(
    config_path: str = None,
    env_prefix: str = "DEX_"
) -> Dict[str, Any]:
    """
    Load configuration from a JSON file and optionally override or fill
    values from environment variables.

    :param config_path: Path to the JSON configuration file. If not provided,
                        defaults to 'configs/config.json'.
    :param env_prefix:  Prefix for environment variables that can override
                        or supplement config values (optional).
    :return: Dictionary representing the complete, validated configuration.
    """
    if not config_path:
        # Default location for your config
        config_path = os.path.join("configs", "config.json")

    # Load the JSON config file
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        logger.info(f"Loaded configuration from {config_path}")
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        raise ConfigError(f"Configuration file not found: {config_path}")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {config_path}, error: {e}")
        raise ConfigError(f"Invalid JSON in config file: {config_path}")

    # Example of environment-based overrides
    # Let’s say you want to allow overrides of the Telegram bot token
    # via DEX_TELEGRAM_BOT_TOKEN in your environment, or the Pocket Universe
    # API token via DEX_POCKET_UNIVERSE_API_TOKEN, etc.

    # We can define a helper function or do inline checks:
    # This approach is an example—customize as needed for your keys.
    _env_override(config_data, ["telegram", "bot_token"], env_prefix, "TELEGRAM_BOT_TOKEN")
    _env_override(config_data, ["telegram", "chat_id"], env_prefix, "TELEGRAM_CHAT_ID")
    _env_override(config_data, ["volume_verification", "pocket_universe", "api_token"], env_prefix, "POCKET_UNIVERSE_API_TOKEN")
    _env_override(config_data, ["rugcheck", "api_token"], env_prefix, "RUGCHECK_API_TOKEN")

    # Additional overrides or logic can be added below...
    
    # Validate required fields
    _validate_config(config_data)

    return config_data

def _env_override(
    config_data: Dict[str, Any],
    nested_keys: list,
    env_prefix: str,
    env_suffix: str
) -> None:
    """
    If an environment variable with prefix+suffix exists, override the
    nested config_data value.

    :param config_data: Loaded configuration dictionary.
    :param nested_keys: List representing the nested path of keys in config_data.
                        e.g. ["telegram", "bot_token"] -> config_data["telegram"]["bot_token"].
    :param env_prefix:  The prefix used for environment variables, e.g. 'DEX_'.
    :param env_suffix:  The suffix for a specific key, e.g. 'TELEGRAM_BOT_TOKEN'.
    :return: None (modifies config_data in-place).
    """
    env_var = env_prefix + env_suffix
    env_value = os.getenv(env_var)
    if env_value:
        _set_nested_value(config_data, nested_keys, env_value)
        logger.info(f"Overrode config[{'.'.join(nested_keys)}] from environment variable '{env_var}'")

def _set_nested_value(
    data: Dict[str, Any],
    nested_keys: list,
    value: Any
) -> None:
    """
    Traverse nested dictionaries by a list of keys and set the final key to 'value'.
    E.g. nested_keys = ["foo", "bar"] => data["foo"]["bar"] = value.

    :param data: Dictionary to modify.
    :param nested_keys: Keys in nested path.
    :param value: Value to set.
    """
    d = data
    for key in nested_keys[:-1]:
        d = d.setdefault(key, {})
    d[nested_keys[-1]] = value

def _validate_config(config_data: Dict[str, Any]) -> None:
    """
    Validate that the required structure/fields are present in config_data.
    Raise ConfigError if mandatory fields are missing or invalid.

    :param config_data: The final merged config dictionary.
    """
    # Example mandatory fields – adjust as needed:
    required_top_level_keys = ["filters", "coin_blacklist", "dev_blacklist", "volume_verification", "rugcheck", "telegram"]

    for key in required_top_level_keys:
        if key not in config_data:
            raise ConfigError(f"Missing mandatory config key: '{key}'")

    # Validate sub-keys if needed:
    if "bot_token" not in config_data["telegram"]:
        raise ConfigError("Missing 'telegram.bot_token' in configuration.")
    if "chat_id" not in config_data["telegram"]:
        raise ConfigError("Missing 'telegram.chat_id' in configuration.")

    # You can add more checks for your logic
    logger.debug("Configuration validation passed successfully.")
