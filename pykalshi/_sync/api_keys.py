# AUTO-GENERATED from pykalshi/_async/api_keys.py — do not edit manually.
# Re-run: python scripts/generate_sync.py
from __future__ import annotations

from typing import TYPE_CHECKING

from ..models import APIKey, GeneratedAPIKey, APILimits

if TYPE_CHECKING:
    from .client import KalshiClient


class APIKeys:
    """API key management and account limits."""

    def __init__(self, client: KalshiClient) -> None:
        self._client = client

    def list(self) -> list[APIKey]:
        """List all API keys for this account."""
        data = self._client.get("/api_keys")
        return [APIKey.model_validate(k) for k in (data.get("api_keys") or [])]

    def create(self, public_key: str, name: str | None = None) -> str:
        """Create an API key with a provided RSA public key.

        Args:
            public_key: PEM-encoded RSA public key.
            name: Optional name for the key.

        Returns:
            The API key ID string.
        """
        body: dict = {"public_key": public_key}
        if name:
            body["name"] = name
        data = self._client.post("/api_keys", body)
        return data["api_key_id"]

    def generate(self, name: str | None = None) -> GeneratedAPIKey:
        """Generate a new API key pair (Kalshi creates both keys).

        Returns a GeneratedAPIKey with the private_key field populated.
        The private key is only returned ONCE - store it securely.

        Args:
            name: Optional name for the key.
        """
        body: dict = {}
        if name:
            body["name"] = name
        data = self._client.post("/api_keys/generate", body)
        return GeneratedAPIKey.model_validate(data)

    def delete(self, key_id: str) -> None:
        """Delete an API key.

        Args:
            key_id: The API key ID to delete.
        """
        self._client.delete(f"/api_keys/{key_id}")

    def get_limits(self) -> APILimits:
        """Get API rate limits for this account."""
        data = self._client.get("/account/limits")
        return APILimits.model_validate(data)
