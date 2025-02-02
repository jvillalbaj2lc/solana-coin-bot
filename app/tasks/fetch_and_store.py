# app/tasks/fetch_and_store.py

import logging
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.database.base import SessionLocal
from app.database.models import TokenSnapshot
from app.services.dexscreener_client import DexscreenerClient
from app.services.rugcheck_service import RugcheckService

logger = logging.getLogger(__name__)

@dataclass
class TokenMetrics:
    """Represents validated token metrics."""
    price_usd: Optional[float] = None
    liquidity_usd: Optional[float] = None
    volume_usd: Optional[float] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TokenMetrics':
        """Create TokenMetrics from dictionary with validation."""
        return cls(
            price_usd=safe_float(data.get('priceUsd')),
            liquidity_usd=safe_float(data.get('liquidityUsd')),
            volume_usd=safe_float(data.get('volumeUsd'))
        )

def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """
    Safely convert a value to float while preserving precision.
    
    :param value: Value to convert
    :param default: Default value if conversion fails
    :return: Converted float value or default
    """
    if value is None:
        return default
        
    try:
        if isinstance(value, str):
            # Handle string numbers with common suffixes
            value = value.strip().lower()
            if value.endswith('k'):
                return float(Decimal(value[:-1]) * 1000)
            if value.endswith('m'):
                return float(Decimal(value[:-1]) * 1000000)
            if value.endswith('b'):
                return float(Decimal(value[:-1]) * 1000000000)
        
        # Use Decimal for precise conversion
        return float(Decimal(str(value)))
    except (ValueError, InvalidOperation, TypeError):
        return default

def validate_token_data(
    profile: Dict[str, Any],
    metrics: TokenMetrics,
    filters: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Validate token data against filters.
    
    :param profile: Token profile data
    :param metrics: Validated token metrics
    :param filters: Filter configuration
    :return: Tuple of (is_valid, reason)
    """
    token_address = profile.get('tokenAddress', 'unknown')
    
    # Required fields check
    if not token_address or token_address == 'unknown':
        return False, "Missing token address"
        
    # Price validation
    min_price = filters.get('min_price_usd', 0.0)
    max_price = filters.get('max_price_usd', float('inf'))
    
    if metrics.price_usd is None:
        if filters.get('require_price', True):
            return False, f"Missing price data for {token_address}"
    else:
        if not min_price <= metrics.price_usd <= max_price:
            return False, (
                f"Price ${metrics.price_usd} outside range "
                f"${min_price}-${max_price} for {token_address}"
            )
    
    # Liquidity validation
    min_liquidity = filters.get('min_liquidity_usd', 0.0)
    if metrics.liquidity_usd is None:
        if filters.get('require_liquidity', True):
            return False, f"Missing liquidity data for {token_address}"
    else:
        if metrics.liquidity_usd < min_liquidity:
            return False, (
                f"Liquidity ${metrics.liquidity_usd} below minimum "
                f"${min_liquidity} for {token_address}"
            )
    
    return True, None

def fetch_and_store_tokens(config: Dict[str, Any]) -> None:
    """
    Fetch and store token profiles with enhanced validation and filtering.
    Updates existing tokens without sending notifications.
    
    :param config: Application configuration
    """
    # Initialize clients
    dexscreener = DexscreenerClient()
    rugcheck = setup_rugcheck_service(config)
    
    # Initialize Telegram notifier
    notifier = None
    if config.get("telegram"):
        try:
            from app.services.telegram_notifier import TelegramNotifier, NotifierConfig
            notifier_config = NotifierConfig(
                bot_token=config["telegram"]["bot_token"],
                chat_id=config["telegram"]["chat_id"]
            )
            notifier = TelegramNotifier(notifier_config)
        except Exception as e:
            logger.error(f"Failed to initialize Telegram notifier: {e}")
    
    try:
        # Fetch latest token profiles
        profiles = dexscreener.get_latest_token_profiles()
        logger.info(f"Fetched {len(profiles)} token profiles")
        
        # Process each profile
        tokens_processed = 0
        tokens_filtered = 0
        tokens_stored = 0
        tokens_updated = 0
        
        with SessionLocal() as session:
            for profile in profiles:
                try:
                    # Log profile data for debugging
                    logger.info(f"\nProcessing token profile:")
                    logger.info(f"Token Address: {profile.token_address}")
                    logger.info(f"Chain ID: {profile.chain_id}")
                    logger.info(f"Initial Name: {profile.name}")
                    logger.info(f"Initial Symbol: {profile.symbol}")
                    
                    tokens_processed += 1
                    
                    # Check if token exists by contract address
                    existing_token = (
                        session.query(TokenSnapshot)
                        .filter(
                            TokenSnapshot.token_address == profile.token_address,
                            TokenSnapshot.chain_id == profile.chain_id
                        )
                        .first()
                    )
                    
                    # Extract token data
                    token_address = profile.token_address
                    chain_id = profile.chain_id
                    
                    logger.debug(f"Fetching pairs for token {token_address} on chain {chain_id}")
                    # Get token pairs for volume/liquidity data
                    pairs = dexscreener.get_token_pairs(chain_id, token_address)
                    
                    if not pairs:
                        logger.info(f"❌ Token {token_address} skipped: No pairs found")
                        tokens_filtered += 1
                        continue
                    
                    # Find the pair with highest liquidity
                    best_pair = None
                    max_liquidity = 0
                    
                    for pair in pairs:
                        try:
                            liquidity = pair.get('liquidity', {})
                            if isinstance(liquidity, dict):
                                usd_value = float(liquidity.get('usd', 0) or 0)
                                if usd_value > max_liquidity:
                                    max_liquidity = usd_value
                                    best_pair = pair
                        except Exception as e:
                            logger.debug(f"Error processing pair: {e}")
                            continue
                    
                    if not best_pair:
                        logger.info(f"❌ Token {token_address} skipped: No valid pairs with liquidity")
                        tokens_filtered += 1
                        continue
                    
                    # Extract metrics with safe conversion
                    try:
                        # Extract token information from base token
                        base_token = best_pair.get('baseToken', {})
                        token_name = base_token.get('name')
                        token_symbol = base_token.get('symbol')
                        
                        # Update profile with token name and symbol if not already set
                        if not profile.name and token_name:
                            profile.name = token_name
                            logger.info(f"Updated token name to: {token_name}")
                        if not profile.symbol and token_symbol:
                            profile.symbol = token_symbol
                            logger.info(f"Updated token symbol to: {token_symbol}")
                        
                        # Get price directly from API response to preserve precision
                        price_str = best_pair.get('priceUsd', '0')
                        price_usd = safe_float(price_str, 0)
                        
                        volume = best_pair.get('volume', {})
                        volume_usd = float(volume.get('h24', 0) if isinstance(volume, dict) else 0)
                        liquidity = best_pair.get('liquidity', {})
                        liquidity_usd = float(liquidity.get('usd', 0) if isinstance(liquidity, dict) else 0)
                        
                        # Format price with its natural precision for logging
                        price_str = str(Decimal(str(price_usd)))
                        logger.info(
                            f"Token metrics:\n"
                            f"Name: {profile.name} ({profile.symbol})\n"
                            f"Price USD: ${price_str}\n"
                            f"Volume USD: ${volume_usd:,.2f}\n"
                            f"Liquidity USD: ${liquidity_usd:,.2f}"
                        )
                    except (ValueError, TypeError) as e:
                        logger.info(f"❌ Token {token_address} skipped: Error converting metrics: {e}")
                        tokens_filtered += 1
                        continue
                    
                    # Skip if missing required data
                    if not all([price_usd, volume_usd, liquidity_usd]):
                        logger.info(
                            f"❌ Token {token_address} skipped: Missing required metrics:\n"
                            f"price=${price_usd:.12f}, volume=${volume_usd:,.2f}, liquidity=${liquidity_usd:,.2f}"
                        )
                        tokens_filtered += 1
                        continue
                    
                    # Apply filters
                    if not passes_filters(price_usd, volume_usd, liquidity_usd, config):
                        logger.info(
                            f"❌ Token {token_address} skipped: Did not pass filters\n"
                            f"Current values: price=${price_usd:.12f}, volume=${volume_usd:,.2f}, liquidity=${liquidity_usd:,.2f}\n"
                            f"Filter config: {config.get('filters', {})}"
                        )
                        tokens_filtered += 1
                        continue
                    
                    # Perform rug check if configured
                    risk_data = None
                    if rugcheck:
                        try:
                            assessment = rugcheck.assess_token_risk(token_address)
                            if not assessment.is_safe:
                                logger.info(
                                    f"❌ Token {token_address} skipped: Failed rug check\n"
                                    f"Score: {assessment.score}"
                                )
                                tokens_filtered += 1
                                continue
                            risk_data = {
                                'score': assessment.score,
                                'risks': assessment.risks,
                                'token_program': assessment.token_program,
                                'token_type': assessment.token_type
                            }
                            logger.debug(f"Risk assessment data: {risk_data}")
                        except Exception as e:
                            logger.warning(f"Rug check failed for {token_address}: {e}")
                            # Skip tokens where rugcheck fails
                            logger.info(f"❌ Token {token_address} skipped: Unable to assess risk")
                            tokens_filtered += 1
                            continue
                    else:
                        # If rugcheck is not configured, skip the token
                        logger.info(f"❌ Token {token_address} skipped: Rugcheck service not configured")
                        tokens_filtered += 1
                        continue
                    
                    try:
                        if existing_token:
                            # Update existing token
                            existing_token.price_usd = price_usd
                            existing_token.volume_usd = volume_usd
                            existing_token.liquidity_usd = liquidity_usd
                            existing_token.risk_data = risk_data
                            existing_token.timestamp = datetime.now()
                            session.commit()
                            tokens_updated += 1
                            logger.info(
                                f"✅ Successfully updated token {profile.name} ({profile.symbol}):\n"
                                f"Token: {token_address}\n"
                                f"Price: ${price_usd:.12f}\n"
                                f"Volume: ${volume_usd:,.2f}\n"
                                f"Liquidity: ${liquidity_usd:,.2f}"
                            )
                        else:
                            # Create new token snapshot
                            snapshot = TokenSnapshot.from_token_profile(
                                profile=profile,
                                price_usd=price_usd,
                                volume_usd=volume_usd,
                                liquidity_usd=liquidity_usd,
                                risk_data=risk_data
                            )
                            
                            session.add(snapshot)
                            session.commit()
                            
                            tokens_stored += 1
                            logger.info(
                                f"✅ Successfully stored new token {profile.name} ({profile.symbol}):\n"
                                f"Token: {token_address}\n"
                                f"Price: ${price_usd:.12f}\n"
                                f"Volume: ${volume_usd:,.2f}\n"
                                f"Liquidity: ${liquidity_usd:,.2f}"
                            )

                            # Send Telegram notification only for new tokens
                            if notifier:
                                risk_level = "Unknown"
                                risk_score = None
                                if risk_data:
                                    risk_score = risk_data.get('score')
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
                                price_str = str(Decimal(str(price_usd)))
                                
                                message = (
                                    f"<b>🔥 New Token Alert</b>\n\n"
                                    f"<b>Token:</b> {profile.name} ({profile.symbol})\n"
                                    f"<b>Address:</b> <code>{token_address}</code>\n"
                                    f"<b>Chain:</b> {chain_id}\n"
                                    f"<b>Price:</b> ${price_str}\n"
                                    f"<b>Volume:</b> ${volume_usd:,.2f}\n"
                                    f"<b>Liquidity:</b> ${liquidity_usd:,.2f}\n"
                                    f"<b>Risk Level:</b> {risk_level}"
                                )
                                
                                if risk_score is not None:
                                    message += f" ({risk_score})"
                                    
                                if profile.url:
                                    message += f"\n\n<b>Chart:</b> <a href='{profile.url}'>View on DexScreener</a>"

                                try:
                                    notifier.send_message(message)
                                except Exception as e:
                                    logger.error(f"Failed to send Telegram notification: {e}")

                    except Exception as e:
                        logger.error(f"Failed to create or update token: {e}")
                        continue
                    
                except Exception as e:
                    logger.error(f"Failed to process token profile: {e}", exc_info=True)
                    continue
        
        # Log summary statistics
        logger.info(f"\nToken Processing Summary:")
        logger.info(f"Total Processed: {tokens_processed}")
        logger.info(f"Updated: {tokens_updated}")
        logger.info(f"Filtered Out: {tokens_filtered}")
        logger.info(f"New Tokens Stored: {tokens_stored}")
                    
    except Exception as e:
        logger.error(f"Failed to fetch and store tokens: {e}", exc_info=True)
        raise

def setup_rugcheck_service(config: Dict[str, Any]) -> Optional[RugcheckService]:
    """Setup RugCheck service if configured."""
    rugcheck_cfg = config.get("rugcheck", {})
    if rugcheck_cfg:
        return RugcheckService(
            max_risk_score=rugcheck_cfg.get("max_risk_score", 1000)
        )
    return None

def passes_filters(
    price_usd: float,
    volume_usd: float,
    liquidity_usd: float,
    config: Dict[str, Any]
) -> bool:
    """Check if token passes configured filters."""
    filters = config.get("filters", {})
    
    # Price filter
    min_price = filters.get("min_price_usd", 0)
    max_price = filters.get("max_price_usd", float('inf'))
    if not (min_price <= price_usd <= max_price):
        return False
    
    # Volume filter
    min_volume = filters.get("min_volume_usd", 0)
    if volume_usd < min_volume:
        return False
    
    # Liquidity filter
    min_liquidity = filters.get("min_liquidity_usd", 0)
    if liquidity_usd < min_liquidity:
        return False
    
    return True
