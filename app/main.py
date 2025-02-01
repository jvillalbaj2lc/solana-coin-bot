import logging
import sys
import argparse
from app.config.loader import load_config, ConfigError
from app.database.base import init_db
from app.tasks.scheduler import run_scheduler

def setup_logging(debug: bool = False) -> logging.Logger:
    """Configure logging for the application."""
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    )
    return logging.getLogger(__name__)

def main():
    """
    Main entry point for the DexScreener Bot application.
    """
    # 1. Parse Command-Line Arguments
    parser = argparse.ArgumentParser(description="Start the DexScreener Bot.")
    parser.add_argument(
        "--config",
        default="configs/config.json",
        help="Path to the JSON configuration file (default: configs/config.json)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "--no-auto-config",
        action="store_true",
        help="Disable automatic config file creation from sample"
    )
    args = parser.parse_args()

    # 2. Configure Logging
    logger = setup_logging(args.debug)
    logger.info("Starting DexScreener Bot...")

    try:
        # 3. Load Configuration
        config = load_config(
            config_path=args.config,
            auto_create=not args.no_auto_config
        )
        
        # 4. Initialize Database
        init_db()
        
        # 5. Run Scheduler
        interval_sec = config.get("scheduler", {}).get("interval_sec", 600)
        logger.info(f"Starting scheduler loop, interval={interval_sec} seconds...")
        run_scheduler(config, interval_sec=interval_sec)
        
    except ConfigError as e:
        logger.error("Configuration Error:")
        logger.error(str(e))
        print("\nConfiguration Error:", file=sys.stderr)
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.exception("Unexpected error occurred:")
        print("\nUnexpected Error:", file=sys.stderr)
        print(f"{e.__class__.__name__}: {str(e)}", file=sys.stderr)
        if args.debug:
            raise  # Re-raise in debug mode for full traceback
        sys.exit(1)

if __name__ == "__main__":
    main()
