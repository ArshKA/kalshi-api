from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlencode

from .markets import AsyncMarket
from .orders import AsyncOrder
from ..enums import CandlestickPeriod
from ..dataframe import DataFrameList
from .._utils import normalize_ticker
from ..models import (
    MarketModel, OrderModel, FillModel, TradeModel,
    HistoricalCutoffResponse, HistoricalCandlestick,
)

if TYPE_CHECKING:
    from .client import AsyncKalshiClient


class AsyncHistory:
    """Access to historical data that has rolled off the live API."""

    def __init__(self, client: AsyncKalshiClient) -> None:
        self._client = client

    async def get_cutoff(self) -> HistoricalCutoffResponse:
        """Get boundary timestamps between live and historical data."""
        data = await self._client.get("/historical/cutoff")
        return HistoricalCutoffResponse.model_validate(data)

    async def get_markets(
        self,
        *,
        tickers: str | None = None,
        event_ticker: str | None = None,
        mve_filter: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
        fetch_all: bool = False,
        **extra_params,
    ) -> DataFrameList[AsyncMarket]:
        """Get historical (settled) markets.

        Args:
            tickers: Comma-separated ticker list.
            event_ticker: Filter by event ticker.
            mve_filter: "exclude" to exclude multivariate markets.
            limit: Results per page (max 1000).
            cursor: Pagination cursor.
            fetch_all: Automatically fetch all pages.
        """
        params = {
            "tickers": tickers,
            "event_ticker": normalize_ticker(event_ticker),
            "mve_filter": mve_filter,
            "limit": limit,
            "cursor": cursor,
            **extra_params,
        }
        data = await self._client.paginated_get("/historical/markets", "markets", params, fetch_all)
        return DataFrameList(AsyncMarket(self._client, MarketModel.model_validate(m)) for m in data)

    async def get_market(self, ticker: str) -> AsyncMarket:
        """Get a single historical market by ticker."""
        response = await self._client.get(f"/historical/markets/{ticker.upper()}")
        model = MarketModel.model_validate(response["market"])
        return AsyncMarket(self._client, model)

    async def get_candlesticks(
        self,
        ticker: str,
        *,
        start_ts: int,
        end_ts: int,
        period: CandlestickPeriod = CandlestickPeriod.ONE_HOUR,
    ) -> list[HistoricalCandlestick]:
        """Get historical candlestick data for a settled market.

        Args:
            ticker: Market ticker.
            start_ts: Start Unix timestamp (seconds).
            end_ts: End Unix timestamp (seconds).
            period: Candlestick interval (1min, 1hr, 1day).
        """
        query = urlencode({
            "start_ts": start_ts,
            "end_ts": end_ts,
            "period_interval": period.value,
        })
        response = await self._client.get(
            f"/historical/markets/{ticker.upper()}/candlesticks?{query}"
        )
        return [
            HistoricalCandlestick.model_validate(c)
            for c in (response.get("candlesticks") or [])
        ]

    async def get_fills(
        self,
        *,
        ticker: str | None = None,
        max_ts: int | None = None,
        limit: int = 100,
        cursor: str | None = None,
        fetch_all: bool = False,
        **extra_params,
    ) -> DataFrameList[FillModel]:
        """Get historical fills (requires authentication).

        Args:
            ticker: Filter by market ticker.
            max_ts: Filter fills before this Unix timestamp.
            limit: Results per page (max 1000).
            cursor: Pagination cursor.
            fetch_all: Automatically fetch all pages.
        """
        params = {
            "ticker": normalize_ticker(ticker),
            "max_ts": max_ts,
            "limit": limit,
            "cursor": cursor,
            **extra_params,
        }
        data = await self._client.paginated_get("/historical/fills", "fills", params, fetch_all)
        return DataFrameList(FillModel.model_validate(f) for f in data)

    async def get_orders(
        self,
        *,
        ticker: str | None = None,
        max_ts: int | None = None,
        limit: int = 100,
        cursor: str | None = None,
        fetch_all: bool = False,
        **extra_params,
    ) -> DataFrameList[AsyncOrder]:
        """Get historical orders (requires authentication).

        Args:
            ticker: Filter by market ticker.
            max_ts: Filter orders updated before this Unix timestamp.
            limit: Results per page (max 1000).
            cursor: Pagination cursor.
            fetch_all: Automatically fetch all pages.
        """
        params = {
            "ticker": normalize_ticker(ticker),
            "max_ts": max_ts,
            "limit": limit,
            "cursor": cursor,
            **extra_params,
        }
        data = await self._client.paginated_get("/historical/orders", "orders", params, fetch_all)
        return DataFrameList(AsyncOrder(self._client, OrderModel.model_validate(d)) for d in data)

    async def get_trades(
        self,
        *,
        ticker: str | None = None,
        min_ts: int | None = None,
        max_ts: int | None = None,
        limit: int = 100,
        cursor: str | None = None,
        fetch_all: bool = False,
        **extra_params,
    ) -> DataFrameList[TradeModel]:
        """Get historical public trades.

        Args:
            ticker: Filter by market ticker.
            min_ts: Filter trades after this Unix timestamp.
            max_ts: Filter trades before this Unix timestamp.
            limit: Results per page (max 1000).
            cursor: Pagination cursor.
            fetch_all: Automatically fetch all pages.
        """
        params = {
            "ticker": normalize_ticker(ticker),
            "min_ts": min_ts,
            "max_ts": max_ts,
            "limit": limit,
            "cursor": cursor,
            **extra_params,
        }
        data = await self._client.paginated_get("/historical/trades", "trades", params, fetch_all)
        return DataFrameList(TradeModel.model_validate(t) for t in data)
