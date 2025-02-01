import logging
import argparse
from app.config.loader import load_config, ConfigError
from app.database.base import init_db
from app.tasks.scheduler import run_scheduler

def main():
    """
    Main entry point for the DexScreener Bot application.
    """
    # 1. Parse Command-Line Arguments for config file path
    parser = argparse.ArgumentParser(description="Start the DexScreener Bot.")
    parser.add_argument(
        "--config",
        default="configs/config.json",
        help="Path to the JSON configuration file (default: configs/config.json)."
    )
    args = parser.parse_args()

    # 2. Configure Logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    )
    logger = logging.getLogger(__name__)
    logger.info("Starting DexScreener Bot...")

    # 3. Load Configuration
    try:
        config = load_config(config_path=args.config)
    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        return  # Exit if config cannot be loaded

    # 4. Initialize Database
    init_db()

    # 5. Run Scheduler
    #    Default interval is 600s = 10min. You can override in your config under "scheduler.interval_sec".
    interval_sec = 600
    if "scheduler" in config and "interval_sec" in config["scheduler"]:
        interval_sec = config["scheduler"]["interval_sec"]

    logger.info(f"Starting scheduler loop, interval={interval_sec} seconds...")
    run_scheduler(config, interval_sec=interval_sec)

if __name__ == "__main__":
    main()
