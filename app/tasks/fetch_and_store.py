# app/tasks/fetch_and_store.py

import logging
from typing import Dict, Any, List

from app.database.base import SessionLocal
from app.database.models import TokenSnapshot
from app.services.dexscreener_client import DexscreenerClient
from app.services.rugcheck_service import RugcheckService
from app.services.volume_verifier import build_volume_verifier_from_config

logger = logging.getLogger(__name__)

def fetch_and_store_tokens(config: Dict[str, Any]) -> None:
    """
    Fetch token profiles from DexScreener, filter them, perform volume & rug checks,
    and store valid snapshots into the database.
    """

    # ---------------------------
    # 1. Instantiate Required Services
    # ---------------------------
    dexscreener_client = DexscreenerClient()

    # Build volume verifier from config (handles internal + Pocket Universe checks)
    volume_verifier = build_volume_verifier_from_config(config)

    # If RugCheck is enabled and has an API token, build the service
    rugcheck_cfg = config.get("rugcheck", {})
    rugcheck_service = None
    if rugcheck_cfg.get("api_url") and rugcheck_cfg.get("api_token"):
        rugcheck_service = RugcheckService(
            api_url=rugcheck_cfg.get("api_url"),
            api_token=rugcheck_cfg.get("api_token"),
            required_status=rugcheck_cfg.get("required_status", "Good")
        )

    # Blacklists and filters from config
    coin_blacklist: List[str] = config.get("coin_blacklist", [])
    dev_blacklist: List[str] = config.get("dev_blacklist", [])
    filters = config.get("filters", {})
    min_price_usd = filters.get("min_price_usd", 0.0)
    max_price_usd = filters.get("max_price_usd", float('inf'))
    min_liquidity_usd = filters.get("min_liquidity_usd", 0.0)

    # ---------------------------
    # 2. Fetch Token Profiles
    # ---------------------------
    try:
        token_profiles = dexscreener_client.get_latest_token_profiles()
        # The API docs show a single JSON object example. If it actually returns multiple,
        # you may need to handle a list. We'll handle both possibilities below.

        # Convert single dict → list of dicts for uniform handling
        if isinstance(token_profiles, dict):
            token_profiles = [token_profiles]

    except Exception as e:
        logger.error(f"Error fetching latest token profiles: {e}")
        return

    if not token_profiles:
        logger.info("No token profiles received from DexScreener.")
        return

    # ---------------------------
    # 3. Filter & Validate Tokens
    # ---------------------------
    with SessionLocal() as session:
        tokens_stored = 0

        for profile in token_profiles:
            token_address = profile.get("tokenAddress")
            chain_id = profile.get("chainId", "")
            icon = profile.get("icon")
            description = profile.get("description")
            links = profile.get("links")
            # DexScreener "url" or "header" might be relevant, but optional here.

            # Developer info might not be provided here, so we set None or handle it differently:
            developer = None

            # If the dev blacklisting is critical, but there's no dev info:
            # dev = token_data.get('developer')
            # if dev and (dev.lower() in [d.lower() for d in dev_blacklist]):
            #     logger.info(f"Skipping token by blacklisted developer: {dev}")
            #     continue

            # 3a. Check coin blacklist
            if token_address in coin_blacklist:
                logger.info(f"Skipping blacklisted coin: {token_address}")
                continue

            # 3b. Retrieve volume/liquidity if needed
            #     Since /token-profiles/latest/v1 doesn’t provide volume or liquidity,
            #     you might call an additional endpoint (e.g., get_pairs) to enrich data:
            #
            #     pairs_data = dexscreener_client.get_pairs(chain_id, <pair_address_here>)
            #     volume_usd = <extract from pairs_data>
            #     liquidity = <extract from pairs_data>
            #
            # For now, we’ll set them to 0 or None if not available:
            volume_usd = 0.0
            liquidity = 0.0
            price_usd = 0.0

            # 3c. Filter by min/max price if known
            if price_usd < min_price_usd or price_usd > max_price_usd:
                logger.debug(f"Skipping token {token_address}, price {price_usd} outside range.")
                continue

            # 3d. Filter by min liquidity
            if liquidity < min_liquidity_usd:
                logger.debug(f"Skipping token {token_address}, liquidity={liquidity} < {min_liquidity_usd}")
                continue

            # 3e. Volume Verification
            token_data_for_volume_check = {
                "tokenAddress": token_address,
                "volumeUsd": volume_usd
            }
            if not volume_verifier.verify_volume(token_data_for_volume_check):
                logger.info(f"Skipping token {token_address}, volume verification failed.")
                continue

            # 3f. RugCheck
            if rugcheck_service:
                is_safe = rugcheck_service.verify_token(token_address)
                if not is_safe:
                    logger.info(f"Skipping token {token_address}, rugcheck failed.")
                    continue

            # ---------------------------
            # 4. Store valid snapshot in DB
            # ---------------------------
            snapshot = TokenSnapshot(
                token_address=token_address,
                chain_id=chain_id,
                icon=icon,
                description=description,
                links=links,
                price_usd=price_usd,
                liquidity=liquidity,
                volume_usd=volume_usd,
                developer=developer
            )
            session.add(snapshot)
            tokens_stored += 1

        session.commit()
        logger.info(f"Stored {tokens_stored} token snapshots successfully.")
