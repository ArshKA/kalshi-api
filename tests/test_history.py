"""Tests for historical data endpoints."""

import pytest
from unittest.mock import ANY, AsyncMock

from pykalshi import Market, Order, History
from pykalshi.enums import CandlestickPeriod
from pykalshi.models import (
    HistoricalCutoffResponse, HistoricalCandlestick, FillModel, TradeModel,
    PositionModel,
)

# Docs-derived MarketPosition payload (GET /historical/positions).
HISTORICAL_POSITION = {
    "ticker": "OLD-MKT-A",
    "total_traded_dollars": "12.5000",
    "position_fp": "-10.00",
    "market_exposure_dollars": "0.0000",
    "realized_pnl_dollars": "2.3500",
    "fees_paid_dollars": "0.1200",
    "last_updated_ts": "2026-01-10T00:00:00Z",
}

# Docs-derived EventPosition payload, returned alongside market_positions.
HISTORICAL_EVENT_POSITION = {
    "event_ticker": "OLD-EVT",
    "total_cost_dollars": "12.5000",
    "total_cost_shares_fp": "10.00",
    "event_exposure_dollars": "0.0000",
    "realized_pnl_dollars": "2.3500",
    "fees_paid_dollars": "0.1200",
}


class TestHistoricalCutoff:
    """Tests for the /historical/cutoff endpoint."""

    def test_get_cutoff(self, client, mock_response):
        """Test fetching historical cutoff timestamps."""
        client._session.request.return_value = mock_response({
            "market_settled_ts": "2026-01-15T00:00:00Z",
            "trades_created_ts": "2026-01-15T00:00:00Z",
            "orders_updated_ts": "2026-01-15T00:00:00Z",
        })

        cutoff = client.history.get_cutoff()

        assert isinstance(cutoff, HistoricalCutoffResponse)
        assert cutoff.market_settled_ts == "2026-01-15T00:00:00Z"
        assert cutoff.trades_created_ts == "2026-01-15T00:00:00Z"
        assert cutoff.orders_updated_ts == "2026-01-15T00:00:00Z"
        # Optional field absent from older payloads.
        assert cutoff.market_positions_last_updated_ts is None

    def test_get_cutoff_with_positions_timestamp(self, client, mock_response):
        """Test cutoff response carrying market_positions_last_updated_ts."""
        client._session.request.return_value = mock_response({
            "market_settled_ts": "2026-01-15T00:00:00Z",
            "trades_created_ts": "2026-01-15T00:00:00Z",
            "orders_updated_ts": "2026-01-15T00:00:00Z",
            "market_positions_last_updated_ts": "2026-01-12T00:00:00Z",
        })

        cutoff = client.history.get_cutoff()

        assert cutoff.market_positions_last_updated_ts == "2026-01-12T00:00:00Z"


class TestHistoricalMarkets:
    """Tests for the /historical/markets endpoints."""

    def test_get_markets(self, client, mock_response):
        """Test listing historical markets."""
        client._session.request.return_value = mock_response({
            "markets": [
                {"ticker": "OLD-MKT-A", "status": "finalized", "title": "Old Market A"},
                {"ticker": "OLD-MKT-B", "status": "finalized", "title": "Old Market B"},
            ],
            "cursor": "",
        })

        markets = client.history.get_markets()

        assert len(markets) == 2
        assert all(isinstance(m, Market) for m in markets)
        assert markets[0].ticker == "OLD-MKT-A"

    def test_get_markets_with_filters(self, client, mock_response):
        """Test listing historical markets with filters."""
        client._session.request.return_value = mock_response({
            "markets": [],
            "cursor": "",
        })

        client.history.get_markets(event_ticker="KXTEST", limit=50)

        call_url = client._session.request.call_args.args[1]
        assert "event_ticker=KXTEST" in call_url
        assert "limit=50" in call_url

    def test_get_markets_pagination(self, client, mock_response):
        """Test historical markets pagination with fetch_all."""
        client._session.request.side_effect = [
            mock_response({
                "markets": [{"ticker": "M1"}],
                "cursor": "page2",
            }),
            mock_response({
                "markets": [{"ticker": "M2"}],
                "cursor": "",
            }),
        ]

        markets = client.history.get_markets(fetch_all=True)

        assert len(markets) == 2
        assert client._session.request.call_count == 2

    def test_get_single_market(self, client, mock_response):
        """Test fetching a single historical market."""
        client._session.request.return_value = mock_response({
            "market": {
                "ticker": "OLD-MKT-A",
                "status": "finalized",
                "title": "Old Market A",
                "settlement_value_dollars": "1.00",
            }
        })

        market = client.history.get_market("OLD-MKT-A")

        assert isinstance(market, Market)
        assert market.ticker == "OLD-MKT-A"
        assert market.settlement_value_dollars == "1.00"

    def test_get_market_not_found(self, client, mock_response):
        """Test fetching non-existent historical market."""
        from pykalshi.exceptions import ResourceNotFoundError

        client._session.request.return_value = mock_response(
            {"message": "Market not found"}, status_code=404
        )

        with pytest.raises(ResourceNotFoundError):
            client.history.get_market("NONEXISTENT")


class TestHistoricalCandlesticks:
    """Tests for the /historical/markets/{ticker}/candlesticks endpoint."""

    def test_get_candlesticks(self, client, mock_response):
        """Test fetching historical candlesticks."""
        client._session.request.return_value = mock_response({
            "ticker": "OLD-MKT-A",
            "candlesticks": [
                {
                    "end_period_ts": 1704067200,
                    "yes_bid": {"open": "0.40", "high": "0.45", "low": "0.38", "close": "0.43"},
                    "yes_ask": {"open": "0.55", "high": "0.60", "low": "0.52", "close": "0.57"},
                    "price": {"open": "0.50", "high": "0.55", "low": "0.48", "close": "0.53", "mean": "0.51", "previous": "0.49"},
                    "volume": "100.00",
                    "open_interest": "500.00",
                },
            ],
        })

        candles = client.history.get_candlesticks(
            "OLD-MKT-A", start_ts=1704000000, end_ts=1704100000,
        )

        assert len(candles) == 1
        c = candles[0]
        assert isinstance(c, HistoricalCandlestick)
        assert c.end_period_ts == 1704067200
        assert c.volume == "100.00"
        assert c.price.open == "0.50"
        assert c.price.mean == "0.51"
        assert c.yes_bid.high == "0.45"

    def test_get_candlesticks_url_params(self, client, mock_response):
        """Test candlestick URL parameters are correct."""
        client._session.request.return_value = mock_response({
            "candlesticks": [],
        })

        client.history.get_candlesticks(
            "test-ticker",
            start_ts=1000,
            end_ts=2000,
            period=CandlestickPeriod.ONE_DAY,
        )

        call_url = client._session.request.call_args.args[1]
        assert "/historical/markets/TEST-TICKER/candlesticks" in call_url
        assert "start_ts=1000" in call_url
        assert "end_ts=2000" in call_url
        assert "period_interval=1440" in call_url

    def test_get_candlesticks_empty(self, client, mock_response):
        """Test candlesticks returns empty list when no data."""
        client._session.request.return_value = mock_response({
            "candlesticks": [],
        })

        candles = client.history.get_candlesticks(
            "OLD-MKT-A", start_ts=1, end_ts=2,
        )

        assert candles == []


class TestHistoricalFills:
    """Tests for the /historical/fills endpoint (authenticated)."""

    def test_get_fills(self, client, mock_response):
        """Test fetching historical fills."""
        client._session.request.return_value = mock_response({
            "fills": [
                {
                    "trade_id": "f-001",
                    "ticker": "OLD-MKT-A",
                    "order_id": "o-001",
                    "side": "yes",
                    "action": "buy",
                    "count_fp": "10.00",
                    "yes_price_dollars": "0.55",
                    "no_price_dollars": "0.45",
                    "is_taker": True,
                    "created_time": "2025-12-01T00:00:00Z",
                },
            ],
            "cursor": "",
        })

        fills = client.history.get_fills()

        assert len(fills) == 1
        assert isinstance(fills[0], FillModel)
        assert fills[0].trade_id == "f-001"
        assert fills[0].ticker == "OLD-MKT-A"
        assert fills[0].count_fp == "10.00"

    def test_get_fills_with_filters(self, client, mock_response):
        """Test historical fills with ticker and max_ts filters."""
        client._session.request.return_value = mock_response({
            "fills": [],
            "cursor": "",
        })

        client.history.get_fills(ticker="KXTEST", max_ts=1704000000, limit=50)

        call_url = client._session.request.call_args.args[1]
        assert "ticker=KXTEST" in call_url
        assert "max_ts=1704000000" in call_url
        assert "limit=50" in call_url


class TestHistoricalOrders:
    """Tests for the /historical/orders endpoint (authenticated)."""

    def test_get_orders(self, client, mock_response):
        """Test fetching historical orders."""
        client._session.request.return_value = mock_response({
            "orders": [
                {
                    "order_id": "o-001",
                    "ticker": "OLD-MKT-A",
                    "status": "executed",
                    "action": "buy",
                    "side": "yes",
                    "yes_price_dollars": "0.55",
                    "initial_count_fp": "10.00",
                    "fill_count_fp": "10.00",
                    "remaining_count_fp": "0.00",
                },
            ],
            "cursor": "",
        })

        orders = client.history.get_orders()

        assert len(orders) == 1
        assert isinstance(orders[0], Order)
        assert orders[0].ticker == "OLD-MKT-A"
        assert orders[0].status.value == "executed"

    def test_get_orders_with_filters(self, client, mock_response):
        """Test historical orders with ticker and max_ts filters."""
        client._session.request.return_value = mock_response({
            "orders": [],
            "cursor": "",
        })

        client.history.get_orders(ticker="KXTEST", max_ts=1704000000, limit=50)

        call_url = client._session.request.call_args.args[1]
        assert "ticker=KXTEST" in call_url
        assert "max_ts=1704000000" in call_url
        assert "limit=50" in call_url

    def test_get_orders_pagination(self, client, mock_response):
        """Test historical orders pagination with fetch_all."""
        client._session.request.side_effect = [
            mock_response({
                "orders": [{"order_id": "o-1", "ticker": "T", "status": "executed"}],
                "cursor": "page2",
            }),
            mock_response({
                "orders": [{"order_id": "o-2", "ticker": "T", "status": "canceled"}],
                "cursor": "",
            }),
        ]

        orders = client.history.get_orders(fetch_all=True)

        assert len(orders) == 2
        assert client._session.request.call_count == 2


class TestHistoricalPositions:
    """Tests for the /historical/positions endpoint (authenticated)."""

    def test_get_positions(self, client, mock_response):
        """Test fetching historical positions."""
        client._session.request.return_value = mock_response({
            "market_positions": [HISTORICAL_POSITION],
            "event_positions": [HISTORICAL_EVENT_POSITION],
            "cursor": "",
        })

        positions = client.history.get_positions()

        assert len(positions) == 1
        p = positions[0]
        assert isinstance(p, PositionModel)
        assert p.ticker == "OLD-MKT-A"
        assert p.position_fp == "-10.00"
        assert p.total_traded_dollars == "12.5000"
        assert p.market_exposure_dollars == "0.0000"
        assert p.realized_pnl_dollars == "2.3500"
        assert p.fees_paid_dollars == "0.1200"
        assert p.last_updated_ts == "2026-01-10T00:00:00Z"

        call_url = client._session.request.call_args.args[1]
        assert "/historical/positions" in call_url

    def test_get_positions_with_filters(self, client, mock_response):
        """Test historical positions with ticker and event_ticker filters."""
        client._session.request.return_value = mock_response({
            "market_positions": [],
            "event_positions": [],
            "cursor": "",
        })

        client.history.get_positions(
            ticker="old-mkt-a", event_ticker="old-evt", limit=50,
        )

        call_url = client._session.request.call_args.args[1]
        assert "ticker=OLD-MKT-A" in call_url
        assert "event_ticker=OLD-EVT" in call_url
        assert "limit=50" in call_url

    def test_get_positions_pagination(self, client, mock_response):
        """Test historical positions pagination with fetch_all."""
        client._session.request.side_effect = [
            mock_response({
                "market_positions": [dict(HISTORICAL_POSITION, ticker="M1")],
                "event_positions": [],
                "cursor": "page2",
            }),
            mock_response({
                "market_positions": [dict(HISTORICAL_POSITION, ticker="M2")],
                "event_positions": [],
                "cursor": "",
            }),
        ]

        positions = client.history.get_positions(fetch_all=True)

        assert len(positions) == 2
        assert [p.ticker for p in positions] == ["M1", "M2"]
        assert client._session.request.call_count == 2


class TestHistoricalTrades:
    """Tests for the /historical/trades endpoint."""

    def test_get_trades(self, client, mock_response):
        """Test fetching historical trades."""
        client._session.request.return_value = mock_response({
            "trades": [
                {
                    "trade_id": "t-001",
                    "ticker": "OLD-MKT-A",
                    "count_fp": "10.00",
                    "yes_price_dollars": "0.55",
                    "no_price_dollars": "0.45",
                    "taker_side": "yes",
                    "created_time": "2025-12-01T00:00:00Z",
                },
            ],
            "cursor": "",
        })

        trades = client.history.get_trades()

        assert len(trades) == 1
        assert isinstance(trades[0], TradeModel)
        assert trades[0].trade_id == "t-001"
        assert trades[0].yes_price_dollars == "0.55"

    def test_get_trades_with_filters(self, client, mock_response):
        """Test historical trades with ticker and timestamp filters."""
        client._session.request.return_value = mock_response({
            "trades": [],
            "cursor": "",
        })

        client.history.get_trades(
            ticker="KXTEST", min_ts=1700000000, max_ts=1704000000, limit=50,
        )

        call_url = client._session.request.call_args.args[1]
        assert "ticker=KXTEST" in call_url
        assert "min_ts=1700000000" in call_url
        assert "max_ts=1704000000" in call_url
        assert "limit=50" in call_url

    def test_get_trades_pagination(self, client, mock_response):
        """Test historical trades pagination."""
        client._session.request.side_effect = [
            mock_response({
                "trades": [{"trade_id": "t-1", "ticker": "T", "count_fp": "1.00", "yes_price_dollars": "0.50", "no_price_dollars": "0.50"}],
                "cursor": "page2",
            }),
            mock_response({
                "trades": [{"trade_id": "t-2", "ticker": "T", "count_fp": "2.00", "yes_price_dollars": "0.60", "no_price_dollars": "0.40"}],
                "cursor": "",
            }),
        ]

        trades = client.history.get_trades(fetch_all=True)

        assert len(trades) == 2
        assert client._session.request.call_count == 2


class TestHistoryAccessor:
    """Tests for client.history accessor."""

    def test_history_is_cached_property(self, client):
        """Test that client.history returns the same instance."""
        h1 = client.history
        h2 = client.history
        assert h1 is h2
        assert isinstance(h1, History)


@pytest.fixture
def async_client(mocker):
    """Returns an AsyncKalshiClient with mocked auth and HTTP session."""
    from pykalshi import AsyncKalshiClient

    mocker.patch("pykalshi._base._BaseKalshiClient._load_private_key")
    mocker.patch(
        "pykalshi._base._BaseKalshiClient._sign_request",
        return_value=("1234567890", "fake_sig"),
    )
    mocker.patch("httpx.AsyncClient")

    c = AsyncKalshiClient(api_key_id="fake_key", private_key_path="fake_path", demo=True)
    c._session.request = AsyncMock()
    return c


class TestAsyncHistoricalPositions:
    """Async tests for /historical/positions and the cutoff field."""

    async def test_get_positions(self, async_client, mock_response):
        """Test fetching historical positions asynchronously."""
        async_client._session.request.return_value = mock_response({
            "market_positions": [HISTORICAL_POSITION],
            "event_positions": [HISTORICAL_EVENT_POSITION],
            "cursor": "",
        })

        positions = await async_client.history.get_positions()

        assert len(positions) == 1
        assert isinstance(positions[0], PositionModel)
        assert positions[0].ticker == "OLD-MKT-A"
        assert positions[0].position_fp == "-10.00"

        call_url = async_client._session.request.call_args.args[1]
        assert "/historical/positions" in call_url

    async def test_get_positions_with_filters(self, async_client, mock_response):
        """Test async historical positions filter params."""
        async_client._session.request.return_value = mock_response({
            "market_positions": [],
            "event_positions": [],
            "cursor": "",
        })

        await async_client.history.get_positions(
            ticker="old-mkt-a", event_ticker="old-evt", limit=50,
        )

        call_url = async_client._session.request.call_args.args[1]
        assert "ticker=OLD-MKT-A" in call_url
        assert "event_ticker=OLD-EVT" in call_url
        assert "limit=50" in call_url

    async def test_get_positions_pagination(self, async_client, mock_response):
        """Test async historical positions pagination with fetch_all."""
        async_client._session.request.side_effect = [
            mock_response({
                "market_positions": [dict(HISTORICAL_POSITION, ticker="M1")],
                "event_positions": [],
                "cursor": "page2",
            }),
            mock_response({
                "market_positions": [dict(HISTORICAL_POSITION, ticker="M2")],
                "event_positions": [],
                "cursor": "",
            }),
        ]

        positions = await async_client.history.get_positions(fetch_all=True)

        assert [p.ticker for p in positions] == ["M1", "M2"]
        assert async_client._session.request.call_count == 2

    async def test_get_cutoff_with_positions_timestamp(self, async_client, mock_response):
        """Test async cutoff response carrying market_positions_last_updated_ts."""
        async_client._session.request.return_value = mock_response({
            "market_settled_ts": "2026-01-15T00:00:00Z",
            "trades_created_ts": "2026-01-15T00:00:00Z",
            "orders_updated_ts": "2026-01-15T00:00:00Z",
            "market_positions_last_updated_ts": "2026-01-12T00:00:00Z",
        })

        cutoff = await async_client.history.get_cutoff()

        assert cutoff.market_positions_last_updated_ts == "2026-01-12T00:00:00Z"
