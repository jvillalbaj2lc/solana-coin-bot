# Configuration Setup

## Initial Setup
1. Copy the template configuration:
   ```bash
   cp configs/config.template.json configs/config.json
   ```

2. Edit `configs/config.json` with your specific settings:
   - Add your Telegram bot token and chat ID
   - Add your RugCheck API credentials
   - Adjust filter parameters as needed

## Security Notes
- Never commit `config.json` or any files containing API keys to version control
- The `.gitignore` file is configured to exclude sensitive files
- Keep your API keys and tokens secure and never share them
- Use environment variables for additional security:
  ```bash
  export TELEGRAM_BOT_TOKEN="your_token_here"
  export TELEGRAM_CHAT_ID="your_chat_id_here"
  ```

## Configuration Parameters
- `filters`: Set minimum requirements for token tracking
  - `min_liquidity_usd`: Minimum liquidity in USD
  - `min_price_usd`: Minimum token price
  - `max_price_usd`: Maximum token price
- `volume_verification`: Configure volume analysis
  - `use_internal_algorithm`: Enable internal volume verification
  - `fake_volume_threshold`: Threshold for fake volume detection
- `rugcheck`: RugCheck service configuration
  - `required_status`: Required token status
  - `api_url`: RugCheck API endpoint
  - `api_token`: Your RugCheck API token
- `telegram`: Telegram notification settings
  - `bot_token`: Your Telegram bot token
  - `chat_id`: Target chat ID for notifications
