# app/services/rugcheck_service.py

import logging
from typing import Dict, Any, List, Optional
import requests
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class RiskAssessment:
    """Represents a risk assessment result."""
    is_safe: bool
    score: int
    risks: List[Dict[str, Any]]
    token_program: Optional[str] = None
    token_type: Optional[str] = None
    
    def get_risk_summary(self) -> str:
        """Get a human-readable summary of risks."""
        if not self.risks:
            return "No risks detected"
            
        total_risk_score = sum(risk.get('score', 0) for risk in self.risks)
        risk_summary = [f"Total Risk Score: {self.score} (sum of individual risks: {total_risk_score})"]
        
        # Sort risks by score (highest first)
        sorted_risks = sorted(self.risks, key=lambda x: x.get('score', 0), reverse=True)
        
        for risk in sorted_risks:
            score = risk.get('score', 'N/A')
            value = f" ({risk['value']})" if risk.get('value') else ""
            risk_summary.append(
                f"- {risk['name']}{value}: {risk['description']} "
                f"[Score: {score}, Level: {risk.get('level', 'unknown').upper()}]"
            )
        return "\n".join(risk_summary)
    
    def get_risk_level(self) -> str:
        """Get a human-readable risk level based on score."""
        if self.score < 500:
            return "LOW"
        elif self.score < 750:
            return "MEDIUM"
        elif self.score < 1000:
            return "HIGH"
        else:
            return "CRITICAL"

class RugcheckError(Exception):
    """Base exception for RugCheck-related errors."""
    pass

class RugcheckAPIError(RugcheckError):
    """Raised when the API returns an error."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_text: Optional[str] = None):
        self.status_code = status_code
        self.response_text = response_text
        error_msg = message
        if status_code:
            error_msg += f" (Status: {status_code})"
        if response_text:
            error_msg += f": {response_text}"
        super().__init__(error_msg)

class RugcheckService:
    """
    Service to interact with RugCheck API for risk assessment.
    
    The API returns a risk score where:
    - Lower scores are better
    - Scores < 1000 are generally considered acceptable
    - Each risk factor contributes to the total score
    - Individual risks have their own scores and levels
    """
    
    # Base URL for the API
    BASE_URL = "https://api.rugcheck.xyz/v1/tokens"
    
    # Risk score thresholds
    DEFAULT_MAX_SCORE = 1000
    RISK_LEVELS = {
        "LOW": (0, 500),
        "MEDIUM": (500, 750),
        "HIGH": (750, 1000),
        "CRITICAL": (1000, float('inf'))
    }
    
    def __init__(self, max_risk_score: Optional[int] = None, timeout: int = 10):
        """
        Initialize the RugCheck service.
        
        :param max_risk_score: Maximum allowed risk score (default: 1000)
        :param timeout: Request timeout in seconds
        """
        self.max_risk_score = max_risk_score or self.DEFAULT_MAX_SCORE
        self.timeout = timeout
        self.session = requests.Session()
        
        # Track service health
        self._consecutive_failures = 0
        self._total_requests = 0
        self._failed_requests = 0
        
        logger.info(
            f"Initialized RugCheck service with max risk score {self.max_risk_score} "
            f"(scores above this are considered unsafe)"
        )

    def assess_token_risk(self, token_address: str) -> RiskAssessment:
        """
        Perform a detailed risk assessment of a token.
        
        :param token_address: The token address to assess
        :return: RiskAssessment object with detailed results
        :raises: RugcheckError on validation/API errors
        """
        if not token_address:
            raise RugcheckError("No token address provided")

        self._total_requests += 1
        
        try:
            # Construct the URL for the token's risk report
            url = f"{self.BASE_URL}/{token_address}/report/summary"
            logger.debug(f"Requesting RugCheck assessment from: {url}")
            
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            # Extract risk data
            score = data.get("score")
            if score is None:
                raise RugcheckError("Missing risk score in API response")
            
            # Create assessment result
            assessment = RiskAssessment(
                is_safe=score <= self.max_risk_score,
                score=score,
                risks=data.get("risks", []),
                token_program=data.get("tokenProgram"),
                token_type=data.get("tokenType")
            )
            
            # Reset failure counter on success
            self._consecutive_failures = 0
            return assessment
            
        except requests.exceptions.Timeout:
            self._handle_request_failure()
            raise RugcheckError("Request timed out")
        except requests.exceptions.RequestException as e:
            self._handle_request_failure()
            if hasattr(e, 'response') and e.response is not None:
                raise RugcheckAPIError(
                    "API request failed",
                    e.response.status_code,
                    e.response.text
                )
            raise RugcheckError(f"Request failed: {str(e)}")
        except ValueError as e:
            self._handle_request_failure()
            raise RugcheckError(f"Invalid response format: {str(e)}")

    def _handle_request_failure(self):
        """Handle request failure by updating counters."""
        self._consecutive_failures += 1
        self._failed_requests += 1

    @property
    def is_healthy(self) -> bool:
        """Check if the service is healthy."""
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
            "is_healthy": self.is_healthy
        }
