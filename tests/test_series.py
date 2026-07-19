"""Tests for Series, trades, and batch candlesticks functionality."""

import pytest
import json
from unittest.mock import ANY

from pykalshi import Series
from pykalshi.enums import CandlestickPeriod


class TestGetSeries:
    """Tests for fetching a single series."""

    def test_get_series(self, client, mock_response):
        """Test fetching a series by ticker."""
        client._session.request.return_value = mock_response({
            "series": {
                "ticker": "INXD",
                "title": "S&P 500 Daily",
                "category": "economics",
                "tags": ["stocks", "daily"],
                "frequency": "daily",
            }
        })

        series = client.get_series("INXD")

        assert isinstance(series, Series)
        assert series.ticker == "INXD"
        assert series.title == "S&P 500 Daily"
        assert series.category == "economics"
        client._session.request.assert_called_with(
            "GET",
            "https://external-api.demo.kalshi.co/trade-api/v2/series/INXD",
            headers=ANY,
            timeout=ANY,
        )

    def test_get_series_not_found(self, client, mock_response):
        """Test fetching non-existent series raises error."""
        from pykalshi.exceptions import ResourceNotFoundError

        client._session.request.return_value = mock_response(
            {"message": "Series not found"}, status_code=404
        )

        with pytest.raises(ResourceNotFoundError):
            client.get_series("NONEXISTENT")


class TestGetAllSeries:
    """Tests for listing all series."""

    def test_get_all_series(self, client, mock_response):
        """Test listing series."""
        client._session.request.return_value = mock_response({
            "series": [
                {"ticker": "INXD", "title": "S&P 500 Daily", "category": "economics"},
                {"ticker": "KXBTC", "title": "Bitcoin Price", "category": "crypto"},
            ],
            "cursor": "",
        })

        series_list = client.get_all_series()

        assert len(series_list) == 2
        assert all(isinstance(s, Series) for s in series_list)
        assert series_list[0].ticker == "INXD"
        assert series_list[1].ticker == "KXBTC"

    def test_get_all_series_with_category(self, client, mock_response):
        """Test listing series filtered by category."""
        client._session.request.return_value = mock_response({
            "series": [{"ticker": "KXBTC", "category": "crypto"}],
            "cursor": "",
        })

        client.get_all_series(category="crypto")

        call_url = client._session.request.call_args.args[1]
        assert "category=crypto" in call_url

    def test_get_all_series_pagination(self, client, mock_response):
        """Test series pagination with fetch_all."""
        client._session.request.side_effect = [
            mock_response({
                "series": [{"ticker": "S1"}],
                "cursor": "next_page",
            }),
            mock_response({
                "series": [{"ticker": "S2"}],
                "cursor": "",
            }),
        ]

        series_list = client.get_all_series(fetch_all=True)

        assert len(series_list) == 2
        assert series_list[0].ticker == "S1"
        assert series_list[1].ticker == "S2"
        assert client._session.request.call_count == 2


class TestSeriesObject:
    """Tests for Series object methods."""

    def test_series_get_markets(self, client, mock_response):
        """Test fetching markets for a series."""
        client._session.request.side_effect = [
            # First call: get series
            mock_response({
                "series": {"ticker": "INXD", "title": "S&P 500 Daily"}
            }),
            # Second call: get markets
            mock_response({
                "markets": [
                    {"ticker": "INXD-24JAN01", "title": "S&P 500 Jan 1"},
                    {"ticker": "INXD-24JAN02", "title": "S&P 500 Jan 2"},
                ],
                "cursor": "",
            }),
        ]

        series = client.get_series("INXD")
        markets = series.get_markets()

        assert len(markets) == 2
        assert markets[0].ticker == "INXD-24JAN01"

        # Verify series_ticker filter was passed
        call_url = client._session.request.call_args.args[1]
        assert "series_ticker=INXD" in call_url

    def test_series_repr(self, client, mock_response):
        """Test Series string representation."""
        client._session.request.return_value = mock_response({
            "series": {"ticker": "TEST"}
        })

        series = client.get_series("TEST")

        assert "TEST" in repr(series)
        assert repr(series).startswith("<Series ")

    def test_series_attribute_delegation(self, client, mock_response):
        """Test that Series delegates unknown attributes to data."""
        client._session.request.return_value = mock_response({
            "series": {
                "ticker": "TEST",
                "frequency": "daily",
                "settlement_timer_seconds": 3600,
            }
        })

        series = client.get_series("TEST")

        assert series.frequency == "daily"
        assert series.settlement_timer_seconds == 3600

    def test_series_get_events(self, client, mock_response):
        """Test fetching events for a series."""
        client._session.request.side_effect = [
            # First call: get series
            mock_response({
                "series": {"ticker": "INXD", "title": "S&P 500 Daily"}
            }),
            # Second call: get events
            mock_response({
                "events": [
                    {"event_ticker": "INXD-24JAN01", "series_ticker": "INXD", "title": "S&P 500 Jan 1"},
                    {"event_ticker": "INXD-24JAN02", "series_ticker": "INXD", "title": "S&P 500 Jan 2"},
                ],
                "cursor": "",
            }),
        ]

        series = client.get_series("INXD")
        events = series.get_events()

        assert len(events) == 2
        assert events[0].event_ticker == "INXD-24JAN01"
        assert events[0].series_ticker == "INXD"

        # Verify series_ticker filter was passed
        call_url = client._session.request.call_args.args[1]
        assert "series_ticker=INXD" in call_url


class TestGetTrades:
    """Tests for public trade history."""

    def test_get_trades(self, client, mock_response):
        """Test fetching public trades."""
        client._session.request.return_value = mock_response({
            "trades": [
                {
                    "trade_id": "t-001",
                    "ticker": "KXTEST-A",
                    "count_fp": "10.00",
                    "yes_price_dollars": "0.55",
                    "no_price_dollars": "0.45",
                    "taker_side": "yes",
                    "ts": 1704067200,
                },
                {
                    "trade_id": "t-002",
                    "ticker": "KXTEST-A",
                    "count_fp": "5.00",
                    "yes_price_dollars": "0.56",
                    "no_price_dollars": "0.44",
                    "taker_side": "no",
                    "ts": 1704067201,
                },
            ],
            "cursor": "",
        })

        trades = client.get_trades()

        assert len(trades) == 2
        assert trades[0].trade_id == "t-001"
        assert trades[0].count_fp == "10.00"
        assert trades[0].yes_price_dollars == "0.55"
        assert trades[0].taker_side == "yes"
        client._session.request.assert_called_with(
            "GET",
            "https://external-api.demo.kalshi.co/trade-api/v2/markets/trades?limit=100",
            headers=ANY,
            timeout=ANY,
        )

    def test_get_trades_with_filters(self, client, mock_response):
        """Test fetching trades with filters."""
        client._session.request.return_value = mock_response({
            "trades": [],
            "cursor": "",
        })

        client.get_trades(
            ticker="KXTEST-A",
            min_ts=1704000000,
            max_ts=1704100000,
            limit=50,
        )

        call_url = client._session.request.call_args.args[1]
        assert "ticker=KXTEST-A" in call_url
        assert "min_ts=1704000000" in call_url
        assert "max_ts=1704100000" in call_url
        assert "limit=50" in call_url

    def test_get_trades_pagination(self, client, mock_response):
        """Test trades pagination with fetch_all."""
        client._session.request.side_effect = [
            mock_response({
                "trades": [{"trade_id": "t1", "ticker": "X", "count_fp": "1.00", "yes_price_dollars": "0.50", "no_price_dollars": "0.50"}],
                "cursor": "page2",
            }),
            mock_response({
                "trades": [{"trade_id": "t2", "ticker": "X", "count_fp": "1.00", "yes_price_dollars": "0.50", "no_price_dollars": "0.50"}],
                "cursor": "",
            }),
        ]

        trades = client.get_trades(fetch_all=True)

        assert len(trades) == 2
        assert client._session.request.call_count == 2


class TestBatchCandlesticks:
    """Tests for batch candlestick retrieval."""

    def test_get_candlesticks_batch(self, client, mock_response):
        """Test batch candlestick retrieval."""
        client._session.request.return_value = mock_response({
            "markets": [
                {
                    "market_ticker": "TICK1",
                    "candlesticks": [
                        {
                            "end_period_ts": 1704067200,
                            "volume_fp": "100.00",
                            "open_interest_fp": "500.00",
                            "price": {"open_dollars": "0.50", "high_dollars": "0.55", "low_dollars": "0.48", "close_dollars": "0.53"},
                        }
                    ],
                },
                {
                    "market_ticker": "TICK2",
                    "candlesticks": [
                        {
                            "end_period_ts": 1704067200,
                            "volume_fp": "200.00",
                            "open_interest_fp": "300.00",
                            "price": {"open_dollars": "0.60", "high_dollars": "0.65", "low_dollars": "0.58", "close_dollars": "0.62"},
                        }
                    ],
                },
            ]
        })

        result = client.get_candlesticks_batch(
            tickers=["TICK1", "TICK2"],
            start_ts=1704000000,
            end_ts=1704100000,
            period=CandlestickPeriod.ONE_HOUR,
        )

        assert "TICK1" in result
        assert "TICK2" in result
        assert result["TICK1"].ticker == "TICK1"
        assert len(result["TICK1"].candlesticks) == 1
        assert result["TICK1"].candlesticks[0].volume_fp == "100.00"

        # Verify GET request with query params
        call_args = client._session.request.call_args
        assert call_args.args[0] == "GET"
        url = call_args.args[1]
        assert "/markets/candlesticks" in url
        assert "market_tickers=TICK1%2CTICK2" in url
        assert "start_ts=1704000000" in url
        assert "end_ts=1704100000" in url
        assert "period_interval=60" in url

    def test_get_candlesticks_batch_empty(self, client, mock_response):
        """Test batch candlesticks with no results."""
        client._session.request.return_value = mock_response({
            "markets": []
        })

        result = client.get_candlesticks_batch(
            tickers=["NONEXISTENT"],
            start_ts=1704000000,
            end_ts=1704100000,
        )

        assert result == {}

    def test_get_candlesticks_batch_different_periods(self, client, mock_response):
        """Test batch candlesticks with different period intervals."""
        client._session.request.return_value = mock_response({"markets": []})

        # Test ONE_MINUTE
        client.get_candlesticks_batch(
            tickers=["X"],
            start_ts=1,
            end_ts=2,
            period=CandlestickPeriod.ONE_MINUTE,
        )
        url = client._session.request.call_args.args[1]
        assert "period_interval=1" in url

        # Test ONE_DAY
        client.get_candlesticks_batch(
            tickers=["X"],
            start_ts=1,
            end_ts=2,
            period=CandlestickPeriod.ONE_DAY,
        )
        url = client._session.request.call_args.args[1]
        assert "period_interval=1440" in url
