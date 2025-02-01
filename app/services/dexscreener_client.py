import logging
import time
import json
from typing import Any, Dict, Optional, Union, List
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class TokenLink:
    """Represents a token's external link."""
    url: str
    type: Optional[str] = None
    label: Optional[str] = None

@dataclass
class TokenProfile:
    """Represents a token profile from DexScreener."""
    url: str
    chain_id: str
    token_address: str
    name: Optional[str] = None
    symbol: Optional[str] = None
    icon: Optional[str] = None
    header: Optional[str] = None
    open_graph: Optional[str] = None
    description: Optional[str] = None
    links: List[TokenLink] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TokenProfile':
        """Create a TokenProfile instance from API response data."""
        links = []
        if data.get('links'):
            for link_data in data['links']:
                links.append(TokenLink(
                    url=link_data['url'],
                    type=link_data.get('type'),
                    label=link_data.get('label')
                ))
        
        return cls(
            url=data['url'],
            chain_id=data['chainId'],
            token_address=data['tokenAddress'],
            name=data.get('name'),
            symbol=data.get('symbol'),
            icon=data.get('icon'),
            header=data.get('header'),
            open_graph=data.get('openGraph'),
            description=data.get('description'),
            links=links
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert the profile to a dictionary for storage/serialization."""
        return {
            'url': self.url,
            'chain_id': self.chain_id,
            'token_address': self.token_address,
            'name': self.name,
            'symbol': self.symbol,
            'icon': self.icon,
            'header': self.header,
            'open_graph': self.open_graph,
            'description': self.description,
            'links': [
                {
                    'url': link.url,
                    **({"type": link.type} if link.type else {}),
                    **({"label": link.label} if link.label else {})
                }
                for link in (self.links or [])
            ]
        }

@dataclass
class RateLimit:
    """Rate limit configuration."""
    requests_per_minute: int
    endpoint_type: str

    def get_delay(self) -> float:
        """Calculate delay needed between requests in seconds."""
        return 60.0 / self.requests_per_minute

class DexscreenerError(Exception):
    """Base exception for DexScreener API errors."""
    pass

class DexscreenerAPIError(DexscreenerError):
    """Raised when the API returns an error response."""
    def __init__(self, message: str, status_code: int, response_text: str):
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(f"{message} (Status: {status_code}): {response_text}")

class DexscreenerRateLimitError(DexscreenerError):
    """Raised when rate limit is exceeded."""
    def __init__(self, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        message = f"Rate limit exceeded. Retry after {retry_after}s" if retry_after else "Rate limit exceeded"
        super().__init__(message)

class DexscreenerValidationError(DexscreenerError):
    """Raised when response validation fails."""
    pass

@dataclass
class BoostedToken:
    """Represents a boosted token from DexScreener."""
    url: str
    chain_id: str
    token_address: str
    amount: int
    total_amount: int
    icon: Optional[str] = None
    header: Optional[str] = None
    open_graph: Optional[str] = None
    description: Optional[str] = None
    links: List[TokenLink] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BoostedToken':
        """Create a BoostedToken instance from API response data."""
        links = []
        if data.get('links'):
            for link_data in data['links']:
                links.append(TokenLink(
                    url=link_data['url'],
                    type=link_data.get('type'),
                    label=link_data.get('label')
                ))
        
        return cls(
            url=data['url'],
            chain_id=data['chainId'],
            token_address=data['tokenAddress'],
            amount=data.get('amount', 0),
            total_amount=data.get('totalAmount', 0),
            icon=data.get('icon'),
            header=data.get('header'),
            open_graph=data.get('openGraph'),
            description=data.get('description'),
            links=links
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert the boosted token to a dictionary for storage/serialization."""
        return {
            'url': self.url,
            'chain_id': self.chain_id,
            'token_address': self.token_address,
            'amount': self.amount,
            'total_amount': self.total_amount,
            'icon': self.icon,
            'header': self.header,
            'open_graph': self.open_graph,
            'description': self.description,
            'links': [
                {
                    'url': link.url,
                    **({"type": link.type} if link.type else {}),
                    **({"label": link.label} if link.label else {})
                }
                for link in (self.links or [])
            ]
        }

class DexscreenerClient:
    """Client for interacting with the DexScreener API."""
    
    # Base URL for all API endpoints
    BASE_URL = "https://api.dexscreener.com"
    
    # Rate limits for different endpoint types
    RATE_LIMITS = {
        "profiles": RateLimit(60, "token profiles"),
        "pairs": RateLimit(300, "pair data"),
        "boosts": RateLimit(60, "token boosts")
    }

    def __init__(self):
        """Initialize the DexScreener client."""
        self.session = requests.Session()

        # Track request timestamps for rate limiting
        self._last_request_time: Dict[str, float] = {
            "profiles": 0.0,
            "pairs": 0.0,
            "boosts": 0.0
        }
        
        # Track service health
        self._consecutive_failures = 0
        self._total_requests = 0
        self._failed_requests = 0

    def _make_request(
        self,
        endpoint: str,
        rate_limit_key: str,
        params: Optional[Dict[str, str]] = None
    ) -> Any:
        """
        Make a rate-limited request to the DexScreener API.
        
        :param endpoint: API endpoint path
        :param rate_limit_key: Key for rate limit configuration
        :param params: Optional query parameters
        :return: JSON response data
        :raises: DexscreenerError on API errors
        """
        # Apply rate limiting
        rate_limit = self.RATE_LIMITS[rate_limit_key]
        last_request = self._last_request_time[rate_limit_key]
        now = time.time()
        
        # Calculate delay needed
        delay = rate_limit.get_delay() - (now - last_request)
        if delay > 0:
            logger.debug(f"Rate limiting: sleeping {delay:.2f}s for {rate_limit.endpoint_type}")
            time.sleep(delay)
        
        # Make the request
        url = f"{self.BASE_URL}{endpoint}"
        self._total_requests += 1
        self._last_request_time[rate_limit_key] = time.time()
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After')
                raise DexscreenerRateLimitError(int(retry_after) if retry_after else None)
            
            response.raise_for_status()
            
            # Reset failure counter on success
            self._consecutive_failures = 0
            return response.json()
            
        except requests.exceptions.RequestException as e:
            self._consecutive_failures += 1
            self._failed_requests += 1
            
            if isinstance(e, requests.exceptions.HTTPError):
                raise DexscreenerAPIError(
                    "API request failed",
                    e.response.status_code,
                    e.response.text
                )
            
            error_msg = f"Request failed: {str(e)}"
            logger.error(error_msg)
            raise DexscreenerError(error_msg)

    def get_latest_token_profiles(self) -> List[TokenProfile]:
        """
        Get the latest token profiles.
        Rate limit: 60 requests per minute.
        
        :return: List of TokenProfile objects
        :raises: DexscreenerError on API or validation errors
        """
        try:
            response = self._make_request(
                "/token-profiles/latest/v1",
                "profiles"
            )
            
            # Validate response format
            if not isinstance(response, list):
                raise DexscreenerValidationError(
                    f"Expected list response, got {type(response)}"
                )
            
            # Convert each profile to TokenProfile object
            profiles = []
            for profile_data in response:
                try:
                    # Validate required fields
                    required_fields = ['url', 'chainId', 'tokenAddress']
                    missing = [f for f in required_fields if f not in profile_data]
                    if missing:
                        logger.warning(
                            f"Skipping profile due to missing fields {missing}: "
                            f"{profile_data.get('tokenAddress', 'unknown')}"
                        )
                        continue
                    
                    profile = TokenProfile.from_dict(profile_data)
                    profiles.append(profile)
                    
                except Exception as e:
                    logger.warning(
                        f"Failed to parse profile {profile_data.get('tokenAddress', 'unknown')}: {str(e)}"
                    )
                    continue
            
            return profiles
            
        except Exception as e:
            logger.error(f"Failed to fetch token profiles: {str(e)}")
            raise

    def get_token_pairs(self, chain_id: str, token_address: str) -> List[Dict[str, Any]]:
        """
        Get all pairs/pools for a given token.
        Rate limit: 300 requests per minute.
        
        :param chain_id: Chain identifier (e.g., "solana")
        :param token_address: Token address to query
        :return: List of pair dictionaries
        """
        try:
            url = f"{self.BASE_URL}/token-pairs/v1/{chain_id}/{token_address}"
            logger.info(f"Fetching pairs from URL: {url}")
            logger.info(f"Chain ID: {chain_id}, Token Address: {token_address}")
            
            response = self._make_request(
                f"/token-pairs/v1/{chain_id}/{token_address}",
                "pairs"
            )
            
            # Handle both possible response formats
            if isinstance(response, dict):
                pairs = response.get("pairs", [])
            else:
                pairs = response if isinstance(response, list) else []
            
            # Log more details about the pairs found
            logger.info(f"Found {len(pairs)} pairs for token {token_address} on chain {chain_id}")
            if pairs:
                # Log token information from the first pair
                first_pair = pairs[0]
                base_token = first_pair.get('baseToken', {})
                token_name = base_token.get('name', 'unknown')
                token_symbol = base_token.get('symbol', 'unknown')
                logger.info(f"Token Name: {token_name} ({token_symbol})")
                
                for idx, pair in enumerate(pairs):
                    dex = pair.get('dexId', 'unknown')
                    price = pair.get('priceUsd', 'unknown')
                    volume = pair.get('volume', {}).get('h24', 'unknown')
                    liquidity = pair.get('liquidity', {}).get('usd', 'unknown')
                    quote_token = pair.get('quoteToken', {}).get('symbol', 'unknown')
                    logger.info(f"Pair {idx + 1}: DEX={dex}, {token_symbol}/{quote_token}, Price=${price}, 24h Volume=${volume}, Liquidity=${liquidity}")
            else:
                logger.warning(f"No pairs found for token {token_address} on chain {chain_id}")
            
            return pairs
            
        except Exception as e:
            logger.error(f"Failed to get pairs for token {token_address} on chain {chain_id}: {e}")
            return []

    def get_pair(self, chain_id: str, pair_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific pair.
        Rate limit: 300 requests per minute.
        
        :param chain_id: Chain identifier (e.g., "solana")
        :param pair_id: Pair address to query
        :return: Pair information dictionary or None if not found
        """
        response = self._make_request(
            f"/latest/dex/pairs/{chain_id}/{pair_id}",
            "pairs"
        )
        pairs = response.get("pairs", [])
        return pairs[0] if pairs else None

    @property
    def is_healthy(self) -> bool:
        """Check if the service is healthy based on error rates."""
        return (
            self._consecutive_failures < 5 and
            (self._total_requests == 0 or
             self._failed_requests / self._total_requests < 0.25)
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        return {
            "total_requests": self._total_requests,
            "failed_requests": self._failed_requests,
            "consecutive_failures": self._consecutive_failures,
            "error_rate": (
                self._failed_requests / self._total_requests
                if self._total_requests > 0 else 0
            ),
            "is_healthy": self.is_healthy,
            "last_request_times": self._last_request_time.copy()
        }

    def get_latest_boosted_tokens(self) -> List[BoostedToken]:
        """
        Get the latest boosted tokens.
        Rate limit: 60 requests per minute.
        
        :return: List of BoostedToken objects
        :raises: DexscreenerError on API or validation errors
        """
        try:
            response = self._make_request(
                "/token-boosts/latest/v1",
                "boosts"
            )
            
            # Validate response format
            if not isinstance(response, list):
                raise DexscreenerValidationError(
                    f"Expected list response, got {type(response)}"
                )
            
            # Convert each token to BoostedToken object
            boosted_tokens = []
            for token_data in response:
                try:
                    # Validate required fields
                    required_fields = ['url', 'chainId', 'tokenAddress']
                    missing = [f for f in required_fields if f not in token_data]
                    if missing:
                        logger.warning(
                            f"Skipping boosted token due to missing fields {missing}: "
                            f"{token_data.get('tokenAddress', 'unknown')}"
                        )
                        continue
                    
                    token = BoostedToken.from_dict(token_data)
                    boosted_tokens.append(token)
                    
                except Exception as e:
                    logger.warning(
                        f"Failed to parse boosted token {token_data.get('tokenAddress', 'unknown')}: {str(e)}"
                    )
                    continue
            
            return boosted_tokens
            
        except Exception as e:
            logger.error(f"Failed to fetch boosted tokens: {str(e)}")
            raise

    def get_top_boosted_tokens(self) -> List[BoostedToken]:
        """
        Get tokens with most active boosts.
        Rate limit: 60 requests per minute.
        
        :return: List of BoostedToken objects
        :raises: DexscreenerError on API or validation errors
        """
        try:
            response = self._make_request(
                "/token-boosts/top/v1",
                "boosts"
            )
            
            # Validate response format
            if not isinstance(response, list):
                raise DexscreenerValidationError(
                    f"Expected list response, got {type(response)}"
                )
            
            # Convert each token to BoostedToken object
            boosted_tokens = []
            for token_data in response:
                try:
                    # Validate required fields
                    required_fields = ['url', 'chainId', 'tokenAddress']
                    missing = [f for f in required_fields if f not in token_data]
                    if missing:
                        logger.warning(
                            f"Skipping boosted token due to missing fields {missing}: "
                            f"{token_data.get('tokenAddress', 'unknown')}"
                        )
                        continue
                    
                    token = BoostedToken.from_dict(token_data)
                    boosted_tokens.append(token)
                    
                except Exception as e:
                    logger.warning(
                        f"Failed to parse boosted token {token_data.get('tokenAddress', 'unknown')}: {str(e)}"
                    )
                    continue
            
            return sorted(
                boosted_tokens,
                key=lambda x: (x.total_amount, x.amount),
                reverse=True
            )
            
        except Exception as e:
            logger.error(f"Failed to fetch top boosted tokens: {str(e)}")
            raise

    def get_orders_for_token(self, chain_id: str, token_address: str) -> Dict[str, Any]:
        """
        Check orders paid for a specific token with validation.

        :param chain_id: e.g. "solana", "eth", "bsc"
        :param token_address: e.g. "A55Xjv..."
        :return: JSON array of orders or empty list
        :raises: DexscreenerError and its subclasses
        """
        if not chain_id or not token_address:
            raise ValueError("Both chain_id and token_address are required")
            
        return self._make_request(
            f'/orders/v1/{chain_id}/{token_address}',
            "pairs"
        )

    def get_pairs(self, chain_id: str, pair_id: str) -> Dict[str, Any]:
        """
        Get one or multiple pairs by chain and pair address with validation.

        :param chain_id: e.g. "eth"
        :param pair_id: e.g. "0x1234abcd..."
        :return: Parsed and validated JSON response
        :raises: DexscreenerError and its subclasses
        """
        if not chain_id or not pair_id:
            raise ValueError("Both chain_id and pair_id are required")
            
        data = self._make_request(
            f'/latest/dex/pairs/{chain_id}/{pair_id}',
            "pairs"
        )
        expected_fields = ['pairs']
        self._validate_response(data, expected_fields)
        return data

    def _validate_response(self, data: Any, expected_fields: list) -> None:
        """
        Validate response data against expected fields.
        
        :param data: Response data to validate
        :param expected_fields: List of required field names
        :raises: DexscreenerValidationError if validation fails
        """
        if not isinstance(data, (dict, list)):
            raise DexscreenerValidationError(f"Expected dict or list, got {type(data)}")
        
        if isinstance(data, dict):
            missing_fields = [field for field in expected_fields if field not in data]
            if missing_fields:
                raise DexscreenerValidationError(f"Missing required fields: {missing_fields}")
