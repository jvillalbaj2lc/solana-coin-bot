import os
import json
import shutil
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

class ConfigError(Exception):
    """Custom exception for configuration-related errors."""
    pass

def create_default_config(config_path: str) -> None:
    """
    Create a default configuration file by copying the sample config.
    
    :param config_path: Path where the config file should be created
    :raises ConfigError: If sample config doesn't exist or can't create config
    """
    sample_path = f"{config_path}.sample"
    if not os.path.exists(sample_path):
        raise ConfigError(
            f"Neither config file '{config_path}' nor sample '{sample_path}' found. "
            "Please ensure you have a valid configuration file."
        )
    
    try:
        shutil.copy2(sample_path, config_path)
        logger.info(f"Created new config file at {config_path} from sample")
    except IOError as e:
        raise ConfigError(f"Failed to create config file from sample: {e}")

def load_config(
    config_path: str = None,
    env_prefix: str = "DEX_",
    auto_create: bool = True
) -> Dict[str, Any]:
    """
    Load configuration from a JSON file and optionally override or fill
    values from environment variables.

    :param config_path: Path to the JSON configuration file. If not provided,
                       defaults to 'configs/config.json'.
    :param env_prefix: Prefix for environment variables that can override
                      or supplement config values (optional).
    :param auto_create: If True, attempts to create config from sample if missing.
    :return: Dictionary representing the complete, validated configuration.
    :raises ConfigError: If configuration loading or validation fails
    """
    if not config_path:
        config_path = os.path.join("configs", "config.json")

    # Ensure config directory exists
    os.makedirs(os.path.dirname(config_path), exist_ok=True)

    # Check if config exists, try to create from sample if enabled
    if not os.path.exists(config_path):
        if auto_create:
            create_default_config(config_path)
        else:
            raise ConfigError(
                f"Configuration file not found: {config_path}\n"
                f"Please copy {config_path}.sample to {config_path} and update with your settings."
            )

    # Load the JSON config file
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        logger.info(f"Loaded configuration from {config_path}")
    except json.JSONDecodeError as e:
        raise ConfigError(
            f"Invalid JSON in config file: {config_path}\n"
            f"Error: {str(e)}\n"
            "Please verify your configuration file format."
        )
    except Exception as e:
        raise ConfigError(f"Failed to read config file: {str(e)}")

    # Process environment variable overrides
    _process_env_overrides(config_data, env_prefix)
    
    # Validate the configuration
    _validate_config(config_data)

    return config_data

def _process_env_overrides(config_data: Dict[str, Any], env_prefix: str) -> None:
    """Process all environment variable overrides for the configuration."""
    env_mappings = {
        "TELEGRAM_BOT_TOKEN": ["telegram", "bot_token"],
        "TELEGRAM_CHAT_ID": ["telegram", "chat_id"],
        "RUGCHECK_API_TOKEN": ["rugcheck", "api_token"]
    }
    
    for env_key, nested_keys in env_mappings.items():
        _env_override(config_data, nested_keys, env_prefix, env_key)

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
    # Required top-level keys
    required_top_level_keys = [
        "filters",
        "coin_blacklist",
        "dev_blacklist",
        "rugcheck",
        "telegram"
    ]

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
