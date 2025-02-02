import logging
import re
from typing import List, Optional, Any
from sqlalchemy import desc
from app.database.base import SessionLocal
from app.database.models import TokenSnapshot
from decimal import Decimal

logger = logging.getLogger(__name__)

def format_token_message(snapshot: TokenSnapshot) -> str:
    """Format a token snapshot into a Telegram message."""
    risk_level = "Unknown"
    risk_score = None
    if snapshot.risk_data:
        risk_score = snapshot.risk_data.get('score')
        if risk_score is not None:
            if risk_score < 500:
                risk_level = "LOW"
            elif risk_score < 750:
                risk_level = "MEDIUM"
            elif risk_score < 1000:
                risk_level = "HIGH"
            else:
                risk_level = "CRITICAL"

    # Format price with natural precision
    price_str = str(Decimal(str(snapshot.price_usd)))
    
    message = (
        f"<b>Token:</b> {snapshot.token_name} ({snapshot.token_symbol})\n"
        f"<b>Address:</b> <code>{snapshot.token_address}</code>\n"
        f"<b>Chain:</b> {snapshot.chain_id}\n"
        f"<b>Price:</b> ${price_str}\n"
        f"<b>Volume:</b> ${snapshot.volume_usd:,.2f}\n"
        f"<b>Liquidity:</b> ${snapshot.liquidity_usd:,.2f}\n"
        f"<b>Risk Level:</b> {risk_level}"
    )
    
    if risk_score is not None:
        message += f" ({risk_score})"
        
    if snapshot.dexscreener_url:
        message += f"\n\n<b>Chart:</b> <a href='{snapshot.dexscreener_url}'>View on DexScreener</a>"
    
    return message

def handle_last_n(notifier: Any, n: int = 5) -> None:
    """
    Handle the /lastN command to show the N most recent tokens.
    
    :param notifier: Any object with a send_message method
    :param n: Number of tokens to show
    """
    try:
        with SessionLocal() as session:
            # Get the last N tokens ordered by timestamp
            snapshots = (
                session.query(TokenSnapshot)
                .order_by(desc(TokenSnapshot.timestamp))
                .limit(n)
                .all()
            )
            
            if not snapshots:
                notifier.send_message("No tokens found in the database.")
                return
            
            # Send header message
            header = f"<b>🔍 Last {len(snapshots)} Tokens Found:</b>\n"
            notifier.send_message(header)
            
            # Send each token as a separate message to avoid message length limits
            for snapshot in snapshots:
                try:
                    message = format_token_message(snapshot)
                    notifier.send_message(message)
                except Exception as e:
                    logger.error(f"Error sending token message: {e}")
                    continue
                    
    except Exception as e:
        error_msg = f"Error fetching last {n} tokens: {str(e)}"
        logger.error(error_msg)
        notifier.send_message(f"⚠️ {error_msg}")

def handle_command(notifier: Any, text: str) -> None:
    """
    Handle bot commands.
    
    :param notifier: Any object with a send_message method
    :param text: Command text
    """
    # Command patterns
    command_patterns = {
        r'/last(\d+)': handle_last_n,  # Matches /last followed by numbers
    }
    
    # Check for command matches
    for pattern, handler in command_patterns.items():
        match = re.match(pattern, text)
        if match:
            try:
                n = int(match.group(1))
                if n <= 0 or n > 20:  # Limit to reasonable numbers
                    notifier.send_message("Please use a number between 1 and 20.")
                    return
                
                handler(notifier, n)
                
            except ValueError:
                notifier.send_message("Invalid number format. Use /lastN where N is a number (e.g., /last5)")
            except Exception as e:
                logger.error(f"Error handling command: {e}")
                notifier.send_message("An error occurred while processing your request.") 