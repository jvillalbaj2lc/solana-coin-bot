# app/services/rugcheck_service.py

import logging
import requests

logger = logging.getLogger(__name__)

class RugcheckService:
    """
    Service to interact with RugCheck.xyz (or a similar anti-rug tool).

    Typical usage:
        rugcheck = RugcheckService(api_url, api_token)
        is_safe = rugcheck.verify_token(token_address)
        if not is_safe:
            # reject token ...
    """
    def __init__(self, api_url: str, api_token: str, required_status: str = "Good"):
        """
        :param api_url: Base URL for RugCheck API (e.g., 'https://api.rugcheck.xyz/verify')
        :param api_token: Bearer token or similar credential for the API
        :param required_status: Status required for the token to be deemed safe (default "Good")
        """
        self.api_url = api_url
        self.api_token = api_token
        self.required_status = required_status

    def verify_token(self, token_address: str) -> bool:
        """
        Verify the token using RugCheck:
        1) Send a POST request with the tokenAddress in the payload.
        2) Check if the returned status matches the required status.
        3) Check if 'bundled' is False.

        :param token_address: The address of the token to verify.
        :return: True if the token is safe, False otherwise.
        """
        if not self.api_url or not self.api_token:
            logger.warning("RugCheckService: Missing API url/token; cannot verify.")
            return False
        if not token_address:
            logger.warning("RugCheckService: No token address provided.")
            return False

        payload = {"tokenAddress": token_address}
        headers = {"Authorization": f"Bearer {self.api_token}"}

        try:
            resp = requests.post(self.api_url, json=payload, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            # The sample response might look like:
            # {
            #   "status": "Good",
            #   "bundled": false,
            #   ...
            # }
            status = data.get("status", "")
            bundled = data.get("bundled", False)

            logger.debug(f"RugCheck response for {token_address}: status={status}, bundled={bundled}")

            if status != self.required_status:
                logger.info(f"Token {token_address} has status '{status}' != '{self.required_status}'")
                return False
            if bundled:
                logger.info(f"Token {token_address} is flagged as bundled. Rejecting.")
                return False

            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"RugCheckService: Request error verifying token {token_address} - {e}")
            return False
        except ValueError as e:
            logger.error(f"RugCheckService: JSON decode error - {e}")
            return False
