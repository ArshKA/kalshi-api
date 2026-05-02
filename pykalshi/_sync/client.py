# AUTO-GENERATED from pykalshi/_async/client.py — do not edit manually.
# Re-run: python scripts/generate_sync.py
"""Kalshi API Client."""

from __future__ import annotations

import time
import json
import logging
from functools import cached_property
from typing import Any, TYPE_CHECKING
from urllib.parse import urlencode

import httpx

from .._base import _BaseKalshiClient, _RETRYABLE_STATUS_CODES
from .events import Event
from .markets import Market, Series
from .mve import MveCollection
from ..models import MarketModel, EventModel, SeriesModel, TradeModel, CandlestickResponse, MveCollectionModel
from ..dataframe import DataFrameList
from .portfolio import Portfolio
from ..enums import MarketStatus, CandlestickPeriod
from .exchange import Exchange
from .api_keys import APIKeys
from .communications import Communications
from .history import History
from ..exceptions import RateLimitError
from .._utils import normalize_ticker, normalize_tickers

if TYPE_CHECKING:
    from ..feed import Feed
    from ..rate_limiter import RateLimiterProtocol

logger = logging.getLogger(__name__)


class KalshiClient(_BaseKalshiClient):
    """Authenticated client for the Kalshi Trading API.

    Usage:
        with KalshiClient.from_env() as client:
            market = client.get_market("TICKER")
            balance = client.portfolio.get_balance()
    """

    def __init__(
        self,
        api_key_id: str | None = None,
        private_key_path: str | None = None,
        api_base: str | None = None,
        demo: bool = False,
        timeout: float = 10.0,
        max_retries: int = 3,
        rate_limiter: RateLimiterProtocol | None = None,
    ) -> None:
        super().__init__(
            api_key_id=api_key_id,
            private_key_path=private_key_path,
            api_base=api_base,
            demo=demo,
            timeout=timeout,
            max_retries=max_retries,
            rate_limiter=rate_limiter,
        )
        self._session = httpx.Client()

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._session.close()

    def __enter__(self) -> KalshiClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # --- HTTP methods ---

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> httpx.Response:
        """Execute async HTTP request with retry on transient failures."""
        url = f"{self.api_base}{endpoint}"

        for attempt in range(self.max_retries + 1):
            if self.rate_limiter is not None:
                wait_time = self.rate_limiter.acquire()
                if wait_time > 0:
                    logger.debug("Rate limiter waited %.3fs", wait_time)

            headers = self._get_headers(method, endpoint)
            request_kwargs: dict[str, Any] = {"headers": headers, "timeout": self.timeout}
            if "data" in kwargs:
                request_kwargs["content"] = kwargs["data"]
            try:
                response = self._session.request(method, url, **request_kwargs)
            except httpx.TimeoutException as e:
                if attempt == self.max_retries:
                    raise
                wait = self._compute_backoff(attempt, None)
                logger.warning(
                    "%s %s failed (%s), retry %d/%d in %.1fs",
                    method, endpoint, type(e).__name__,
                    attempt + 1, self.max_retries, wait,
                )
                time.sleep(wait)
                continue
            except httpx.ConnectError as e:
                if attempt == self.max_retries:
                    raise
                wait = self._compute_backoff(attempt, None)
                logger.warning(
                    "%s %s failed (%s), retry %d/%d in %.1fs",
                    method, endpoint, type(e).__name__,
                    attempt + 1, self.max_retries, wait,
                )
                time.sleep(wait)
                continue

            self._update_rate_limiter(response)

            if response.status_code not in _RETRYABLE_STATUS_CODES:
                return response
            if attempt == self.max_retries:
                if response.status_code == 429:
                    raise RateLimitError(
                        429, "Rate limit exceeded after retries",
                        method=method, endpoint=endpoint,
                    )
                return response

            wait = self._compute_backoff(attempt, response.headers.get("Retry-After"))
            logger.warning(
                "%s %s returned %d, retry %d/%d in %.1fs",
                method, endpoint, response.status_code,
                attempt + 1, self.max_retries, wait,
            )
            time.sleep(wait)

        return response  # unreachable, satisfies type checker

    def get(self, endpoint: str) -> dict[str, Any]:
        """Make authenticated GET request."""
        logger.debug("GET %s", endpoint)
        response = self._request("GET", endpoint)
        return self._handle_response(response, method="GET", endpoint=endpoint)

    def paginated_get(
        self,
        path: str,
        response_key: str,
        params: dict[str, Any],
        fetch_all: bool = False,
    ) -> list[dict]:
        """Fetch items with automatic cursor-based pagination."""
        params = dict(params)
        all_items: list[dict] = []
        while True:
            filtered = {k: v for k, v in params.items() if v is not None}
            endpoint = f"{path}?{urlencode(filtered)}" if filtered else path
            response = self.get(endpoint)
            all_items.extend(response.get(response_key) or [])
            cursor = response.get("cursor", "")
            if not fetch_all or not cursor:
                break
            params["cursor"] = cursor
        return all_items

    def post(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
        """Make authenticated POST request."""
        logger.debug("POST %s", endpoint)
        body = json.dumps(data, separators=(",", ":"))
        response = self._request("POST", endpoint, data=body)
        return self._handle_response(
            response, method="POST", endpoint=endpoint, request_body=data
        )

    def put(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
        """Make authenticated PUT request."""
        logger.debug("PUT %s", endpoint)
        body = json.dumps(data, separators=(",", ":"))
        response = self._request("PUT", endpoint, data=body)
        return self._handle_response(
            response, method="PUT", endpoint=endpoint, request_body=data
        )

    def delete(self, endpoint: str, body: dict | None = None) -> dict[str, Any]:
        """Make authenticated DELETE request."""
        logger.debug("DELETE %s", endpoint)
        if body:
            data = json.dumps(body, separators=(",", ":"))
            response = self._request("DELETE", endpoint, data=data)
        else:
            response = self._request("DELETE", endpoint)
        return self._handle_response(response, method="DELETE", endpoint=endpoint)

    # --- Domain accessors ---

    @cached_property
    def portfolio(self) -> Portfolio:
        return Portfolio(self)

    @cached_property
    def exchange(self) -> Exchange:
        return Exchange(self)

    @cached_property
    def api_keys(self) -> APIKeys:
        return APIKeys(self)

    @cached_property
    def communications(self) -> Communications:
        return Communications(self)

    @cached_property
    def history(self) -> History:
        return History(self)

    def feed(self) -> Feed:
        """Create a new async real-time data feed."""
        from ..feed import Feed
        return Feed(self)

    # --- Domain query methods ---

    def get_market(self, ticker: str) -> Market:
        response = self.get(f"/markets/{ticker.upper()}")
        model = MarketModel.model_validate(response["market"])
        return Market(self, model)

    def get_markets(
        self,
        *,
        status: MarketStatus | None = None,
        mve_filter: str | None = None,
        tickers: list[str] | None = None,
        series_ticker: str | None = None,
        event_ticker: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
        fetch_all: bool = False,
        **extra_params,
    ) -> DataFrameList[Market]:
        params = {
            "status": status.value if status is not None else None,
            "mve_filter": mve_filter,
            "tickers": ",".join(normalize_tickers(tickers)) if tickers else None,
            "series_ticker": normalize_ticker(series_ticker),
            "event_ticker": normalize_ticker(event_ticker),
            "limit": limit,
            "cursor": cursor,
            **extra_params,
        }
        data = self.paginated_get("/markets", "markets", params, fetch_all)
        return DataFrameList(Market(self, MarketModel.model_validate(m)) for m in data)

    def get_event(
        self,
        event_ticker: str,
        *,
        with_nested_markets: bool = False,
    ) -> Event:
        params = {}
        if with_nested_markets:
            params["with_nested_markets"] = "true"
        endpoint = f"/events/{event_ticker.upper()}"
        if params:
            endpoint += "?" + urlencode(params)
        response = self.get(endpoint)
        model = EventModel.model_validate(response["event"])
        return Event(self, model)

    def get_events(
        self,
        *,
        series_ticker: str | None = None,
        status: MarketStatus | None = None,
        limit: int = 100,
        cursor: str | None = None,
        fetch_all: bool = False,
        **extra_params,
    ) -> DataFrameList[Event]:
        params = {
            "limit": limit,
            "series_ticker": normalize_ticker(series_ticker),
            "status": status.value if status is not None else None,
            "cursor": cursor,
            **extra_params,
        }
        data = self.paginated_get("/events", "events", params, fetch_all)
        return DataFrameList(Event(self, EventModel.model_validate(e)) for e in data)

    def get_series(
        self,
        series_ticker: str,
        *,
        include_volume: bool = False,
    ) -> Series:
        params = {}
        if include_volume:
            params["include_volume"] = "true"
        endpoint = f"/series/{series_ticker.upper()}"
        if params:
            endpoint += "?" + urlencode(params)
        response = self.get(endpoint)
        model = SeriesModel.model_validate(response["series"])
        return Series(self, model)

    def get_all_series(
        self,
        *,
        category: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
        fetch_all: bool = False,
        **extra_params,
    ) -> DataFrameList[Series]:
        params = {"limit": limit, "category": category, "cursor": cursor, **extra_params}
        data = self.paginated_get("/series", "series", params, fetch_all)
        return DataFrameList(Series(self, SeriesModel.model_validate(s)) for s in data)

    def get_mve_collection(self, collection_ticker: str) -> MveCollection:
        response = self.get(f"/multivariate_event_collections/{collection_ticker}")
        model = MveCollectionModel.model_validate(response.get("multivariate_contract", response))
        return MveCollection(self, model)

    def get_mve_collections(
        self,
        *,
        status: str | None = None,
        associated_event_ticker: str | None = None,
        series_ticker: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
        fetch_all: bool = False,
    ) -> DataFrameList[MveCollection]:
        params = {
            "limit": limit,
            "status": status,
            "associated_event_ticker": normalize_ticker(associated_event_ticker),
            "series_ticker": normalize_ticker(series_ticker),
            "cursor": cursor,
        }
        data = self.paginated_get(
            "/multivariate_event_collections", "multivariate_contracts", params, fetch_all
        )
        return DataFrameList(
            MveCollection(self, MveCollectionModel.model_validate(c)) for c in data
        )

    def get_multivariate_events(
        self,
        *,
        series_ticker: str | None = None,
        collection_ticker: str | None = None,
        with_nested_markets: bool = False,
        limit: int = 200,
        cursor: str | None = None,
        fetch_all: bool = False,
    ) -> DataFrameList[Event]:
        params: dict = {"limit": limit}
        if series_ticker:
            params["series_ticker"] = normalize_ticker(series_ticker)
        if collection_ticker:
            params["collection_ticker"] = collection_ticker
        if with_nested_markets:
            params["with_nested_markets"] = "true"
        if cursor:
            params["cursor"] = cursor

        data = self.paginated_get("/events/multivariate", "events", params, fetch_all)
        return DataFrameList(Event(self, EventModel.model_validate(e)) for e in data)

    def get_trades(
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
        params = {
            "limit": limit,
            "ticker": normalize_ticker(ticker),
            "min_ts": min_ts,
            "max_ts": max_ts,
            "cursor": cursor,
            **extra_params,
        }
        data = self.paginated_get("/markets/trades", "trades", params, fetch_all)
        return DataFrameList(TradeModel.model_validate(t) for t in data)

    def get_candlesticks_batch(
        self,
        tickers: list[str],
        start_ts: int,
        end_ts: int,
        period: CandlestickPeriod = CandlestickPeriod.ONE_HOUR,
    ) -> dict[str, CandlestickResponse]:
        if not tickers:
            raise ValueError("tickers must not be empty")

        query = urlencode({
            "market_tickers": ",".join(normalize_tickers(tickers)),
            "start_ts": start_ts,
            "end_ts": end_ts,
            "period_interval": period.value,
        })
        response = self.get(f"/markets/candlesticks?{query}")
        return {
            item["market_ticker"]: CandlestickResponse.model_validate(item)
            for item in (response.get("markets") or [])
        }
