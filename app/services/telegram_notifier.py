# app/services/volume_verifier.py

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class VolumeVerifier:
    """
    Handles verification of token volume using:
    1) Internal threshold-based checks.
    2) Optional external verification via Pocket Universe.
    """

    def __init__(
        self,
        use_internal_algorithm: bool,
        fake_volume_threshold: float,
        use_pocket_universe: bool,
        pocket_universe_service: Optional[Any] = None
    ):
        """
        :param use_internal_algorithm: If True, apply the local threshold check on volume.
        :param fake_volume_threshold: Minimum volume to consider 'non-fake'.
        :param use_pocket_universe: If True, also call the external Pocket Universe check.
        :param pocket_universe_service: Instance of PocketUniverseService or None if not needed.
        """
        self.use_internal_algorithm = use_internal_algorithm
        self.fake_volume_threshold = fake_volume_threshold
        self.use_pocket_universe = use_pocket_universe
        self.pocket_universe_service = pocket_universe_service

    def verify_volume(self, token_data: Dict[str, Any]) -> bool:
        """
        Performs volume verification. Steps:
        1) If internal checks are enabled, ensure the token's volume is above fake_volume_threshold.
        2) If Pocket Universe check is enabled, call the external service to verify authenticity.

        :param token_data: A dictionary that includes 'volumeUsd', 'tokenAddress', etc.
        :return: True if volume passes all checks, False otherwise.
        """
        # 1) Parse current volume
        volume_key = 'volumeUsd'
        current_volume = 0.0
        try:
            current_volume = float(token_data.get(volume_key, 0.0))
        except (TypeError, ValueError):
            logger.warning(f"VolumeVerifier: Could not parse volume for token {token_data.get('tokenAddress')}.")
            return False

        # 2) Internal threshold check
        if self.use_internal_algorithm:
            if current_volume < self.fake_volume_threshold:
                logger.info(
                    f"VolumeVerifier: Token {token_data.get('tokenAddress')} volume "
                    f"{current_volume} < threshold {self.fake_volume_threshold}"
                )
                return False
            else:
                logger.debug(
                    f"VolumeVerifier: Internal volume check passed for token {token_data.get('tokenAddress')}, "
                    f"{current_volume} >= {self.fake_volume_threshold}"
                )

        # 3) External Pocket Universe check
        if self.use_pocket_universe and self.pocket_universe_service is not None:
            token_address = token_data.get("tokenAddress")
            if not self.pocket_universe_service.verify_volume_authenticity(token_address):
                logger.info(
                    f"VolumeVerifier: Pocket Universe flagged token {token_address} as suspicious volume."
                )
                return False

        # If it reaches here, all checks passed
        return True


def build_volume_verifier_from_config(config: Dict[str, Any]) -> VolumeVerifier:
    """
    Factory function to build a VolumeVerifier instance from the app's configuration dictionary.

    Expects something like:
    config["volume_verification"] = {
        "use_internal_algorithm": true,
        "fake_volume_threshold": 5.0,
        "use_pocket_universe": true,
        "pocket_universe": {
            "api_url": "https://api.pocketuniverse.com/verify",
            "api_token": "YOUR_POCKET_UNIVERSE_API_TOKEN"
        }
    }

    :param config: The entire app config, typically loaded by loader.py
    :return: A configured VolumeVerifier instance.
    """
    vol_ver_cfg = config.get("volume_verification", {})
    use_internal = vol_ver_cfg.get("use_internal_algorithm", True)
    threshold = vol_ver_cfg.get("fake_volume_threshold", 5.0)
    use_pu = vol_ver_cfg.get("use_pocket_universe", False)

    pocket_universe_service = None
    if use_pu:
        from app.services.pocket_universe_service import PocketUniverseService  # local import to avoid circular deps
        pu_cfg = vol_ver_cfg.get("pocket_universe", {})
        api_url = pu_cfg.get("api_url")
        api_token = pu_cfg.get("api_token")
        pocket_universe_service = PocketUniverseService(api_url, api_token)

    verifier = VolumeVerifier(
        use_internal_algorithm=use_internal,
        fake_volume_threshold=threshold,
        use_pocket_universe=use_pu,
        pocket_universe_service=pocket_universe_service
    )
    return verifier
