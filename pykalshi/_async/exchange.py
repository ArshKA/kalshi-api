from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models import ExchangeStatus, Announcement
from ..exceptions import KalshiAPIError

if TYPE_CHECKING:
    from .client import AsyncKalshiClient


class AsyncExchange:
    """Exchange status, schedule, and announcements."""

    def __init__(self, client: AsyncKalshiClient) -> None:
        self._client = client

    async def get_status(self) -> ExchangeStatus:
        """Get current exchange operational status."""
        try:
            data = await self._client.get("/exchange/status")
        except KalshiAPIError as e:
            if e.status_code == 503 and isinstance(e.response_body, dict):
                data = e.response_body
            else:
                raise
        return ExchangeStatus.model_validate(data)

    async def is_trading(self) -> bool:
        """Quick check if trading is currently active."""
        status = await self.get_status()
        return status.trading_active

    async def get_schedule(self) -> dict[str, Any]:
        """Get exchange trading schedule (raw format)."""
        data = await self._client.get("/exchange/schedule")
        return data.get("schedule", {})

    async def get_announcements(self) -> list[Announcement]:
        """Get exchange-wide announcements."""
        data = await self._client.get("/exchange/announcements")
        return [Announcement.model_validate(a) for a in (data.get("announcements") or [])]

    async def get_user_data_timestamp(self) -> int:
        """Get timestamp of last user data validation (Unix ms)."""
        data = await self._client.get("/exchange/user_data_timestamp")
        return data.get("user_data_timestamp", 0)
