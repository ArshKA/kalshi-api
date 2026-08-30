"""Shared base class for sync and async Kalshi clients."""

from __future__ import annotations

import json
import logging
import os
import time
from base64 import b64encode
from typing import Any
from urllib.parse import urlparse

import httpx

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from .exceptions import (
    KalshiAPIError,
    AuthenticationError,
    InsufficientFundsError,
    ResourceNotFoundError,
    RateLimitError,
    OrderRejectedError,
)

logger = logging.getLogger(__name__)

DEFAULT_API_BASE = "https://external-api.kalshi.com/trade-api/v2"
DEMO_API_BASE = "https://external-api.demo.kalshi.co/trade-api/v2"

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class _BaseKalshiClient:
    """Config, authentication, signing, headers, and error handling.

    Subclassed by KalshiClient (sync) and AsyncKalshiClient (async).
    Does NOT create an HTTP session — subclasses do that.
    """

    def __init__(
        self,
        api_key_id: str | None = None,
        private_key_path: str | None = None,
        private_key: str | RSAPrivateKey | None = None,
        api_base: str | None = None,
        demo: bool = False,
        timeout: float = 10.0,
        max_retries: int = 3,
        rate_limiter: Any = None,
    ) -> None:
        resolved_api_key_id = api_key_id or os.getenv("KALSHI_API_KEY_ID")
        if not resolved_api_key_id:
            raise ValueError(
                "API key ID required. Set KALSHI_API_KEY_ID env var or pass api_key_id."
            )
        self.api_key_id: str = resolved_api_key_id

        # Credential precedence: args > env vars
        if private_key:
            pass  # Use provided private_key
        elif private_key_path:
            pass  # Use provided private_key_path
        elif os.getenv("KALSHI_PRIVATE_KEY"):
            private_key = os.getenv("KALSHI_PRIVATE_KEY")
        elif os.getenv("KALSHI_PRIVATE_KEY_PATH"):
            private_key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH")
        else:
            raise ValueError(
                "Private key or path required. Set KALSHI_PRIVATE_KEY or KALSHI_PRIVATE_KEY_PATH env var."
            )

        self.api_base = api_base or (DEMO_API_BASE if demo else DEFAULT_API_BASE)
        self._api_path = urlparse(self.api_base).path
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limiter = rate_limiter
        
        if private_key:
            if isinstance(private_key, RSAPrivateKey):
                self.private_key = private_key
            elif isinstance(private_key, str):
                self.private_key = self._load_private_key_string(private_key)
            else:
                raise TypeError(f"Expected private_key to be str or RSAPrivateKey, got {type(private_key).__name__}")
        else:
            # Type ignore because private_key_path must be a str here based on the checks above
            self.private_key = self._load_private_key(private_key_path)  # type: ignore

    @classmethod
    def from_env(cls, **kwargs) -> "_BaseKalshiClient":
        """Create client from .env file.

        Loads dotenv before reading env vars. All keyword arguments
        are forwarded to the constructor.
        """
        from dotenv import load_dotenv
        load_dotenv()
        return cls(**kwargs)
        
    def _load_private_key_string(self, key_string: str) -> RSAPrivateKey:
        """Load RSA private key from PEM string."""
        # Handle literal \n if present
        key_string = key_string.replace("\\n", "\n")
        key = serialization.load_pem_private_key(key_string.encode('utf-8'), password=None)
        if not isinstance(key, RSAPrivateKey):
            raise TypeError(f"Expected RSA private key, got {type(key).__name__}")
        return key

    def _load_private_key(self, key_path: str) -> RSAPrivateKey:
        """Load RSA private key from PEM file."""
        with open(key_path, "rb") as f:
            key = serialization.load_pem_private_key(f.read(), password=None)
            if not isinstance(key, RSAPrivateKey):
                raise TypeError(f"Expected RSA private key, got {type(key).__name__}")
            return key

    def _sign_request(self, method: str, path: str) -> tuple[str, str]:
        """Create RSA-PSS signature for API request."""
        timestamp = str(int(time.time() * 1000))
        message = f"{timestamp}{method}{path}"

        signature = self.private_key.sign(
            message.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH
            ),
            hashes.SHA256(),
        )
        return timestamp, b64encode(signature).decode()

    def _get_headers(self, method: str, endpoint: str) -> dict[str, str]:
        """Generate authenticated headers."""
        path_without_query = urlparse(endpoint).path
        full_path = f"{self._api_path}{path_without_query}"
        timestamp, signature = self._sign_request(method, full_path)
        return {
            "Content-Type": "application/json",
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
        }

    def _handle_response(
        self,
        response: httpx.Response,
        *,
        method: str | None = None,
        endpoint: str | None = None,
        request_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Handle API response and raise custom exceptions with full context."""
        status_code = response.status_code

        if status_code < 400:
            logger.debug("Response %s: Success", status_code)
            if status_code == 204 or not response.content:
                return {}
            return response.json()

        logger.error("Response %s: Error body: %s", status_code, response.text)

        response_body: dict[str, Any] | str | None = None
        try:
            error_data = response.json()
            response_body = error_data
            inner = error_data.get("error", {}) if isinstance(error_data.get("error"), dict) else {}
            message = inner.get("message") or error_data.get("message") or error_data.get(
                "error_message", "Unknown Error"
            )
            code = inner.get("code") or error_data.get("code") or error_data.get("error_code")
        except (ValueError, json.JSONDecodeError):
            message = response.text
            response_body = response.text
            code = None

        if status_code in (401, 403):
            raise AuthenticationError(
                status_code, message, code,
                method=method, endpoint=endpoint,
                request_body=request_body, response_body=response_body,
            )
        elif status_code == 404:
            raise ResourceNotFoundError(
                status_code, message, code,
                method=method, endpoint=endpoint,
                request_body=request_body, response_body=response_body,
            )
        elif code in ("insufficient_funds", "insufficient_balance"):
            raise InsufficientFundsError(
                status_code, message, code,
                method=method, endpoint=endpoint,
                request_body=request_body, response_body=response_body,
            )
        elif code in (
            "order_rejected",
            "market_closed",
            "market_settled",
            "invalid_price",
            "self_trade",
            "post_only_rejected",
        ):
            raise OrderRejectedError(
                status_code, message, code,
                method=method, endpoint=endpoint,
                request_body=request_body, response_body=response_body,
            )
        else:
            raise KalshiAPIError(
                status_code, message, code,
                method=method, endpoint=endpoint,
                request_body=request_body, response_body=response_body,
            )

    @staticmethod
    def _compute_backoff(attempt: int, retry_after: str | None) -> float:
        """Compute wait time for retry with exponential backoff."""
        try:
            return float(retry_after) if retry_after else min(2 ** attempt * 0.5, 30)
        except (ValueError, TypeError):
            return min(2 ** attempt * 0.5, 30)

    def _update_rate_limiter(self, response: httpx.Response) -> None:
        """Update rate limiter from response headers if configured."""
        if self.rate_limiter is not None:
            remaining = response.headers.get("X-RateLimit-Remaining")
            reset_at = response.headers.get("X-RateLimit-Reset")
            self.rate_limiter.update_from_headers(
                remaining=int(remaining) if remaining else None,
                reset_at=int(reset_at) if reset_at else None,
            )
