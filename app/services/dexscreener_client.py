import logging
import requests

logger = logging.getLogger(__name__)

class DexscreenerClient:
    """
    A client to interact with the DexScreener API endpoints.
    """
    BASE_URL = "https://api.dexscreener.com"

    def __init__(self):
        """
        Optionally, you can accept parameters here such as API keys,
        if DexScreener’s endpoints require them, or use them for
        advanced rate-limiting logic.
        """
        self.session = requests.Session()

    def get_latest_token_profiles(self):
        """
        Fetch the latest token profiles.

        Endpoint:
        GET /token-profiles/latest/v1

        :return: Parsed JSON response
        :raises requests.exceptions.RequestException: On network/API errors
        """
        url = f"{self.BASE_URL}/token-profiles/latest/v1"
        logger.debug(f"GET {url}")
        response = self.session.get(url)
        response.raise_for_status()
        # The API, as documented, returns a single JSON object with these fields:
        # {
        #   "url": "https://example.com",
        #   "chainId": "text",
        #   "tokenAddress": "text",
        #   "icon": "https://example.com",
        #   "header": "https://example.com",
        #   "description": "text",
        #   "links": [
        #     {
        #       "type": "text",
        #       "label": "text",
        #       "url": "https://example.com"
        #     }
        #   ]
        # }
        # But in practice, it might be an array or a single object. Double check.
        return response.json()

    def get_latest_boosted_tokens(self):
        """
        Fetch the latest boosted tokens.

        Endpoint:
        GET /token-boosts/latest/v1

        :return: Parsed JSON response
        :raises requests.exceptions.RequestException: On network/API errors
        """
        url = f"{self.BASE_URL}/token-boosts/latest/v1"
        logger.debug(f"GET {url}")
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_top_boosted_tokens(self):
        """
        Fetch tokens with the most active boosts.

        Endpoint:
        GET /token-boosts/top/v1

        :return: Parsed JSON response
        :raises requests.exceptions.RequestException: On network/API errors
        """
        url = f"{self.BASE_URL}/token-boosts/top/v1"
        logger.debug(f"GET {url}")
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_orders_for_token(self, chain_id: str, token_address: str):
        """
        Check orders paid for a specific token.

        Endpoint:
        GET /orders/v1/{chainId}/{tokenAddress}

        :param chain_id: e.g. "solana", "eth", "bsc"
        :param token_address: e.g. "A55Xjv..."
        :return: JSON array of orders or empty list
        :raises requests.exceptions.RequestException: On network/API errors
        """
        url = f"{self.BASE_URL}/orders/v1/{chain_id}/{token_address}"
        logger.debug(f"GET {url}")
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_pairs(self, chain_id: str, pair_id: str):
        """
        Get one or multiple pairs by chain and pair address.

        Endpoint:
        GET /latest/dex/pairs/{chainId}/{pairId}
        Rate-limit: 300 requests per minute

        :param chain_id: e.g. "eth"
        :param pair_id:  e.g. "0x1234abcd..."
        :return: Parsed JSON response
        :raises requests.exceptions.RequestException: On network/API errors
        """
        url = f"{self.BASE_URL}/latest/dex/pairs/{chain_id}/{pair_id}"
        logger.debug(f"GET {url}")
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
