"""Tests for AsyncKalshiClient."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, ANY

from pykalshi import AsyncKalshiClient, AsyncMarket, AsyncEvent, AsyncOrder
from pykalshi.exceptions import (
    AuthenticationError,
    ResourceNotFoundError,
    KalshiAPIError,
)


def _mock_response(json_data, status_code=200, text=""):
    """Create a mock httpx.Response."""
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    resp.text = text
    resp.content = b"ok" if json_data else b""
    resp.headers = {}
    return resp


@pytest.fixture
def async_client(mocker):
    """Returns an AsyncKalshiClient with mocked auth and HTTP session."""
    mocker.patch("pykalshi._base._BaseKalshiClient._load_private_key")
    mocker.patch(
        "pykalshi._base._BaseKalshiClient._sign_request",
        return_value=("1234567890", "fake_sig"),
    )
    mocker.patch("httpx.AsyncClient")

    c = AsyncKalshiClient(api_key_id="fake_key", private_key_path="fake_path", demo=True)
    # Make session.request return an AsyncMock
    c._session.request = AsyncMock()
    return c


class TestAsyncGet:
    """Tests for async GET requests."""

    @pytest.mark.asyncio
    async def test_get_success(self, async_client):
        async_client._session.request.return_value = _mock_response({"data": "ok"})
        result = await async_client.get("/test")
        assert result == {"data": "ok"}

    @pytest.mark.asyncio
    async def test_get_401_raises_auth_error(self, async_client):
        async_client._session.request.return_value = _mock_response(
            {"message": "Unauthorized"}, status_code=401
        )
        with pytest.raises(AuthenticationError):
            await async_client.get("/test")

    @pytest.mark.asyncio
    async def test_get_404_raises_not_found(self, async_client):
        async_client._session.request.return_value = _mock_response(
            {"message": "Not found"}, status_code=404
        )
        with pytest.raises(ResourceNotFoundError):
            await async_client.get("/test")


class TestAsyncPost:
    """Tests for async POST requests."""

    @pytest.mark.asyncio
    async def test_post_success(self, async_client):
        async_client._session.request.return_value = _mock_response({"order_id": "123"})
        result = await async_client.post("/orders", {"ticker": "TEST"})
        assert result == {"order_id": "123"}

        call_args = async_client._session.request.call_args
        assert call_args.args[0] == "POST"
        body = json.loads(call_args.kwargs["content"])
        assert body["ticker"] == "TEST"


class TestAsyncGetMarket:
    """Tests for async domain methods."""

    @pytest.mark.asyncio
    async def test_get_market(self, async_client):
        async_client._session.request.return_value = _mock_response({
            "market": {
                "ticker": "KXTEST-A",
                "event_ticker": "KXTEST",
                "title": "Test Market",
                "status": "open",
                "yes_bid_dollars": "0.45",
                "yes_ask_dollars": "0.55",
            }
        })

        market = await async_client.get_market("KXTEST-A")

        assert isinstance(market, AsyncMarket)
        assert market.ticker == "KXTEST-A"
        assert market.title == "Test Market"
        assert market.yes_bid_dollars == "0.45"

    @pytest.mark.asyncio
    async def test_get_markets(self, async_client):
        async_client._session.request.return_value = _mock_response({
            "markets": [
                {"ticker": "M1", "status": "open"},
                {"ticker": "M2", "status": "open"},
            ],
            "cursor": "",
        })

        markets = await async_client.get_markets()

        assert len(markets) == 2
        assert all(isinstance(m, AsyncMarket) for m in markets)


class TestAsyncGetEvent:
    """Tests for async event methods."""

    @pytest.mark.asyncio
    async def test_get_event(self, async_client):
        async_client._session.request.return_value = _mock_response({
            "event": {
                "event_ticker": "KXTEST",
                "series_ticker": "KXSERIES",
                "title": "Test Event",
            }
        })

        event = await async_client.get_event("KXTEST")

        assert isinstance(event, AsyncEvent)
        assert event.event_ticker == "KXTEST"
        assert event.title == "Test Event"


class TestAsyncPortfolio:
    """Tests for async portfolio operations."""

    @pytest.mark.asyncio
    async def test_get_balance(self, async_client):
        async_client._session.request.return_value = _mock_response({
            "balance": 5000,
            "portfolio_value": 10000,
        })

        balance = await async_client.portfolio.get_balance()

        assert balance.balance == 5000
        assert balance.portfolio_value == 10000

    @pytest.mark.asyncio
    async def test_get_positions(self, async_client):
        async_client._session.request.return_value = _mock_response({
            "market_positions": [
                {"ticker": "KXTEST-A", "position_fp": "10.00"},
            ],
            "cursor": "",
        })

        positions = await async_client.portfolio.get_positions()
        assert len(positions) == 1
        assert positions[0].ticker == "KXTEST-A"

    @pytest.mark.asyncio
    async def test_get_order(self, async_client):
        async_client._session.request.return_value = _mock_response({
            "order": {
                "order_id": "abc-123",
                "ticker": "KXTEST",
                "status": "resting",
            }
        })

        order = await async_client.portfolio.get_order("abc-123")
        assert isinstance(order, AsyncOrder)
        assert order.order_id == "abc-123"

    @pytest.mark.asyncio
    async def test_cancel_order(self, async_client):
        # CancelOrderV2Response is a thin ack.
        async_client._session.request.return_value = _mock_response({
            "order_id": "abc-123",
            "reduced_by": "10.00",
            "ts_ms": 1715793660456,
        })

        order = await async_client.portfolio.cancel_order("abc-123")
        assert isinstance(order, AsyncOrder)
        assert order.status.value == "canceled"


class TestAsyncExchange:
    """Tests for async exchange operations."""

    @pytest.mark.asyncio
    async def test_get_status(self, async_client):
        async_client._session.request.return_value = _mock_response({
            "exchange_active": True,
            "trading_active": True,
        })

        status = await async_client.exchange.get_status()
        assert status.trading_active is True

    @pytest.mark.asyncio
    async def test_is_trading(self, async_client):
        async_client._session.request.return_value = _mock_response({
            "exchange_active": True,
            "trading_active": False,
        })

        assert await async_client.exchange.is_trading() is False


class TestAsyncContextManager:
    """Tests for async context manager support."""

    @pytest.mark.asyncio
    async def test_aenter_aexit(self, mocker):
        mocker.patch("pykalshi._base._BaseKalshiClient._load_private_key")
        mocker.patch(
            "pykalshi._base._BaseKalshiClient._sign_request",
            return_value=("1234567890", "fake_sig"),
        )
        mock_async_client = mocker.patch("httpx.AsyncClient")
        mock_async_client.return_value.aclose = AsyncMock()

        async with AsyncKalshiClient(
            api_key_id="fake_key", private_key_path="fake_path", demo=True
        ) as client:
            assert client is not None

        # Verify aclose was called
        mock_async_client.return_value.aclose.assert_called_once()


class TestAsyncCachedProperties:
    """Tests for cached property accessors on async client."""

    def test_portfolio_returns_async_variant(self, async_client):
        from pykalshi import AsyncPortfolio
        assert isinstance(async_client.portfolio, AsyncPortfolio)

    def test_exchange_returns_async_variant(self, async_client):
        from pykalshi import AsyncExchange
        assert isinstance(async_client.exchange, AsyncExchange)

    def test_api_keys_returns_async_variant(self, async_client):
        from pykalshi import AsyncAPIKeys
        assert isinstance(async_client.api_keys, AsyncAPIKeys)

    def test_communications_returns_async_variant(self, async_client):
        from pykalshi import AsyncCommunications
        assert isinstance(async_client.communications, AsyncCommunications)

    def test_properties_are_cached(self, async_client):
        assert async_client.portfolio is async_client.portfolio
        assert async_client.exchange is async_client.exchange
