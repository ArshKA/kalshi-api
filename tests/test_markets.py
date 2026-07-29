"""Tests for Market and Event functionality."""

import pytest
from unittest.mock import ANY

from pykalshi import Market, Event
from pykalshi.enums import MarketStatus, CandlestickPeriod


class TestGetMarket:
    """Tests for fetching single markets."""

    def test_get_market(self, client, mock_response):
        """Test fetching a market by ticker."""
        client._session.request.return_value = mock_response({
            "market": {
                "ticker": "KXTEST-A",
                "event_ticker": "KXTEST",
                "title": "Test Market",
                "status": "open",
                "yes_bid_dollars": "0.45",
                "yes_ask_dollars": "0.55",
                "volume_fp": "1000.00",
            }
        })

        market = client.get_market("KXTEST-A")

        assert isinstance(market, Market)
        assert market.ticker == "KXTEST-A"
        assert market.title == "Test Market"
        assert market.yes_bid_dollars == "0.45"
        assert market.yes_ask_dollars == "0.55"

    def test_get_market_not_found(self, client, mock_response):
        """Test fetching non-existent market raises error."""
        from pykalshi.exceptions import ResourceNotFoundError

        client._session.request.return_value = mock_response(
            {"message": "Market not found"}, status_code=404
        )

        with pytest.raises(ResourceNotFoundError):
            client.get_market("NONEXISTENT")


class TestGetMarkets:
    """Tests for listing markets."""

    def test_get_markets(self, client, mock_response):
        """Test listing markets."""
        client._session.request.return_value = mock_response({
            "markets": [
                {"ticker": "KXTEST-A", "status": "open"},
                {"ticker": "KXTEST-B", "status": "open"},
            ],
            "cursor": "",
        })

        markets = client.get_markets()

        assert len(markets) == 2
        assert all(isinstance(m, Market) for m in markets)

    def test_get_markets_with_filters(self, client, mock_response):
        """Test listing markets with filters."""
        client._session.request.return_value = mock_response({
            "markets": [],
            "cursor": "",
        })

        client.get_markets(
            series_ticker="INXD",
            event_ticker="KXTEST",
            status=MarketStatus.OPEN,
            limit=50,
        )

        call_url = client._session.request.call_args.args[1]
        assert "series_ticker=INXD" in call_url
        assert "event_ticker=KXTEST" in call_url
        assert "status=open" in call_url
        assert "limit=50" in call_url

    def test_get_markets_pagination(self, client, mock_response):
        """Test markets pagination with fetch_all."""
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

        markets = client.get_markets(fetch_all=True)

        assert len(markets) == 2
        assert client._session.request.call_count == 2


class TestMarketCandlesticks:
    """Tests for market candlestick data."""

    def test_get_candlesticks(self, client, mock_response):
        """Test fetching candlesticks for a market."""
        client._session.request.side_effect = [
            # First call: get market
            mock_response({
                "market": {
                    "ticker": "INXD-24JAN01",
                    "series_ticker": "INXD",
                }
            }),
            # Second call: get candlesticks
            mock_response({
                "ticker": "INXD-24JAN01",
                "candlesticks": [
                    {
                        "end_period_ts": 1704067200,
                        "volume_fp": "100.00",
                        "open_interest_fp": "500.00",
                        "price": {"open_dollars": "0.50", "high_dollars": "0.55", "low_dollars": "0.48", "close_dollars": "0.53"},
                    },
                    {
                        "end_period_ts": 1704070800,
                        "volume_fp": "150.00",
                        "open_interest_fp": "520.00",
                        "price": {"open_dollars": "0.53", "high_dollars": "0.58", "low_dollars": "0.52", "close_dollars": "0.56"},
                    },
                ],
            }),
        ]

        market = client.get_market("INXD-24JAN01")
        candles = market.get_candlesticks(
            start_ts=1704000000,
            end_ts=1704100000,
            period=CandlestickPeriod.ONE_HOUR,
        )

        assert candles.ticker == "INXD-24JAN01"
        assert len(candles.candlesticks) == 2
        assert candles.candlesticks[0].volume_fp == "100.00"
        assert candles.candlesticks[0].price.open_dollars == "0.50"

    def test_get_candlesticks_no_series_ticker_error(self, client, mock_response):
        """Test candlesticks raises error when series_ticker missing."""
        client._session.request.return_value = mock_response({
            "market": {
                "ticker": "ORPHAN",
                "series_ticker": None,
                "event_ticker": None,
            }
        })

        market = client.get_market("ORPHAN")

        with pytest.raises(ValueError, match="series_ticker"):
            market.get_candlesticks(start_ts=1, end_ts=2)

    def test_get_candlesticks_resolves_series_from_event(self, client, mock_response):
        """Test candlesticks resolves series_ticker from event if missing."""
        client._session.request.side_effect = [
            # First call: get market (no series_ticker)
            mock_response({
                "market": {
                    "ticker": "KXTEST-A",
                    "series_ticker": None,
                    "event_ticker": "KXTEST",
                }
            }),
            # Second call: resolve series from event
            mock_response({
                "event": {
                    "event_ticker": "KXTEST",
                    "series_ticker": "KXSERIES",
                }
            }),
            # Third call: get candlesticks
            mock_response({
                "ticker": "KXTEST-A",
                "candlesticks": [],
            }),
        ]

        market = client.get_market("KXTEST-A")
        # series_ticker property returns None (no lazy loading)
        assert market.series_ticker is None
        # But get_candlesticks still works by calling resolve_series_ticker()
        candles = market.get_candlesticks(start_ts=1, end_ts=2)
        assert candles.ticker == "KXTEST-A"

    def test_resolve_series_ticker_explicit(self, client, mock_response):
        """Test resolve_series_ticker() makes explicit API call."""
        client._session.request.side_effect = [
            mock_response({
                "market": {
                    "ticker": "KXTEST-A",
                    "series_ticker": None,
                    "event_ticker": "KXTEST",
                }
            }),
            mock_response({
                "event": {
                    "event_ticker": "KXTEST",
                    "series_ticker": "KXSERIES",
                }
            }),
        ]

        market = client.get_market("KXTEST-A")
        assert market.series_ticker is None
        resolved = market.resolve_series_ticker()
        assert resolved == "KXSERIES"

    def test_resolve_series_ticker_returns_cached(self, client, mock_response):
        """Test resolve_series_ticker() returns existing value without API call."""
        client._session.request.return_value = mock_response({
            "market": {
                "ticker": "KXTEST-A",
                "series_ticker": "EXISTING",
            }
        })

        market = client.get_market("KXTEST-A")
        assert market.series_ticker == "EXISTING"
        resolved = market.resolve_series_ticker()
        assert resolved == "EXISTING"
        # Only one API call made (for get_market)
        assert client._session.request.call_count == 1


class TestMarketTrades:
    """Tests for Market.get_trades() method."""

    def test_market_get_trades(self, client, mock_response):
        """Test fetching trades for a specific market."""
        client._session.request.side_effect = [
            # First call: get market
            mock_response({
                "market": {"ticker": "KXTEST-A", "title": "Test Market"}
            }),
            # Second call: get trades
            mock_response({
                "trades": [
                    {
                        "trade_id": "t-001",
                        "ticker": "KXTEST-A",
                        "count_fp": "10.00",
                        "yes_price_dollars": "0.55",
                        "no_price_dollars": "0.45",
                        "taker_side": "yes",
                    },
                    {
                        "trade_id": "t-002",
                        "ticker": "KXTEST-A",
                        "count_fp": "5.00",
                        "yes_price_dollars": "0.56",
                        "no_price_dollars": "0.44",
                    },
                ],
                "cursor": "",
            }),
        ]

        market = client.get_market("KXTEST-A")
        trades = market.get_trades()

        assert len(trades) == 2
        assert trades[0].trade_id == "t-001"
        assert trades[0].ticker == "KXTEST-A"

        # Verify ticker filter was passed
        call_url = client._session.request.call_args.args[1]
        assert "ticker=KXTEST-A" in call_url

    def test_market_get_trades_with_filters(self, client, mock_response):
        """Test fetching trades with additional filters."""
        client._session.request.side_effect = [
            mock_response({"market": {"ticker": "KXTEST-A"}}),
            mock_response({"trades": [], "cursor": ""}),
        ]

        market = client.get_market("KXTEST-A")
        market.get_trades(min_ts=1704000000, max_ts=1704100000, limit=50)

        call_url = client._session.request.call_args.args[1]
        assert "ticker=KXTEST-A" in call_url
        assert "min_ts=1704000000" in call_url
        assert "max_ts=1704100000" in call_url
        assert "limit=50" in call_url


class TestMarketNavigation:
    """Tests for Market navigation methods."""

    def test_market_get_event(self, client, mock_response):
        """Test fetching parent event for a market."""
        client._session.request.side_effect = [
            # First call: get market
            mock_response({
                "market": {"ticker": "KXTEST-A", "event_ticker": "KXTEST"}
            }),
            # Second call: get event
            mock_response({
                "event": {
                    "event_ticker": "KXTEST",
                    "series_ticker": "KXSERIES",
                    "title": "Test Event",
                }
            }),
        ]

        market = client.get_market("KXTEST-A")
        event = market.get_event()

        assert event is not None
        assert event.event_ticker == "KXTEST"
        assert event.series_ticker == "KXSERIES"

    def test_market_get_event_returns_none_when_no_event_ticker(self, client, mock_response):
        """Test that get_event returns None when event_ticker is not set."""
        client._session.request.return_value = mock_response({
            "market": {"ticker": "ORPHAN", "event_ticker": None}
        })

        market = client.get_market("ORPHAN")
        event = market.get_event()

        assert event is None
        # Only one API call made (for get_market)
        assert client._session.request.call_count == 1


class TestMarketObject:
    """Tests for Market object methods and properties."""

    def test_market_equality(self, client, mock_response):
        """Test Market equality is based on ticker."""
        client._session.request.side_effect = [
            mock_response({"market": {"ticker": "TEST"}}),
            mock_response({"market": {"ticker": "TEST"}}),
            mock_response({"market": {"ticker": "OTHER"}}),
        ]

        m1 = client.get_market("TEST")
        m2 = client.get_market("TEST")
        m3 = client.get_market("OTHER")

        assert m1 == m2
        assert m1 != m3
        assert hash(m1) == hash(m2)

    def test_market_repr(self, client, mock_response):
        """Test Market string representation."""
        client._session.request.return_value = mock_response({
            "market": {"ticker": "KXTEST"}
        })

        market = client.get_market("KXTEST")

        assert "KXTEST" in repr(market)
        assert repr(market).startswith("<Market ")

    def test_market_attribute_delegation(self, client, mock_response):
        """Test Market delegates unknown attributes to data."""
        client._session.request.return_value = mock_response({
            "market": {
                "ticker": "TEST",
                "rules_primary": "Test rules here",
                "tick_size": 1,
            }
        })

        market = client.get_market("TEST")

        assert market.rules_primary == "Test rules here"
        assert market.tick_size == 1


class TestGetEvent:
    """Tests for fetching events."""

    def test_get_event(self, client, mock_response):
        """Test fetching an event by ticker."""
        client._session.request.return_value = mock_response({
            "event": {
                "event_ticker": "KXTEST",
                "series_ticker": "KXSERIES",
                "title": "Test Event",
                "category": "politics",
            }
        })

        event = client.get_event("KXTEST")

        assert isinstance(event, Event)
        assert event.event_ticker == "KXTEST"
        assert event.series_ticker == "KXSERIES"
        assert event.title == "Test Event"

    def test_get_event_not_found(self, client, mock_response):
        """Test fetching non-existent event raises error."""
        from pykalshi.exceptions import ResourceNotFoundError

        client._session.request.return_value = mock_response(
            {"message": "Event not found"}, status_code=404
        )

        with pytest.raises(ResourceNotFoundError):
            client.get_event("NONEXISTENT")


class TestGetEvents:
    """Tests for listing events."""

    def test_get_events(self, client, mock_response):
        """Test listing events."""
        client._session.request.return_value = mock_response({
            "events": [
                {"event_ticker": "E1", "series_ticker": "S1", "title": "Event 1"},
                {"event_ticker": "E2", "series_ticker": "S1", "title": "Event 2"},
            ],
            "cursor": "",
        })

        events = client.get_events()

        assert len(events) == 2
        assert all(isinstance(e, Event) for e in events)

    def test_get_events_with_filters(self, client, mock_response):
        """Test listing events with filters."""
        client._session.request.return_value = mock_response({
            "events": [],
            "cursor": "",
        })

        client.get_events(
            series_ticker="KXSERIES",
            status=MarketStatus.OPEN,
            limit=25,
        )

        call_url = client._session.request.call_args.args[1]
        assert "series_ticker=KXSERIES" in call_url
        assert "status=open" in call_url
        assert "limit=25" in call_url

    def test_get_events_pagination(self, client, mock_response):
        """Test events pagination with fetch_all."""
        client._session.request.side_effect = [
            mock_response({
                "events": [{"event_ticker": "E1", "series_ticker": "S"}],
                "cursor": "page2",
            }),
            mock_response({
                "events": [{"event_ticker": "E2", "series_ticker": "S"}],
                "cursor": "",
            }),
        ]

        events = client.get_events(fetch_all=True)

        assert len(events) == 2
        assert client._session.request.call_count == 2


class TestEventNavigation:
    """Tests for Event navigation methods."""

    def test_event_get_series(self, client, mock_response):
        """Test fetching parent series for an event."""
        client._session.request.side_effect = [
            # First call: get event
            mock_response({
                "event": {
                    "event_ticker": "KXTEST",
                    "series_ticker": "KXSERIES",
                    "title": "Test Event",
                }
            }),
            # Second call: get series
            mock_response({
                "series": {
                    "ticker": "KXSERIES",
                    "title": "Test Series",
                    "category": "politics",
                }
            }),
        ]

        event = client.get_event("KXTEST")
        series = event.get_series()

        assert series.ticker == "KXSERIES"
        assert series.title == "Test Series"


class TestMarketStatus:
    """Tests for MarketStatus enum usage."""

    def test_market_status_values(self):
        """Test MarketStatus enum has expected values."""
        assert MarketStatus.OPEN.value == "open"
        assert MarketStatus.CLOSED.value == "closed"
        assert MarketStatus.SETTLED.value == "settled"

    def test_market_with_status(self, client, mock_response):
        """Test market status is properly parsed."""
        client._session.request.return_value = mock_response({
            "market": {"ticker": "TEST", "status": "open"}
        })

        market = client.get_market("TEST")

        assert market.status == MarketStatus.OPEN


class TestBatchOrderbooks:
    """Tests for KalshiClient.get_orderbooks (GET /markets/orderbooks)."""

    # Recorded from a live unauthenticated call to production (2026-07-28).
    BATCH_RESPONSE = {
        "orderbooks": [
            {
                "ticker": "TICK1",
                "orderbook_fp": {
                    "yes_dollars": [["0.0100", "1000.00"], ["0.4500", "200.00"]],
                    "no_dollars": [["0.5000", "150.00"]],
                },
            },
            {
                "ticker": "TICK2",
                "orderbook_fp": {
                    "yes_dollars": [["0.3000", "50.00"]],
                    "no_dollars": [],
                },
            },
        ]
    }

    def test_get_orderbooks(self, client, mock_response):
        """Batch fetch returns a dict of OrderbookResponse keyed by ticker."""
        from pykalshi import OrderbookResponse

        client._session.request.return_value = mock_response(self.BATCH_RESPONSE)

        result = client.get_orderbooks(["TICK1", "TICK2"])

        assert set(result) == {"TICK1", "TICK2"}
        assert isinstance(result["TICK1"], OrderbookResponse)
        assert result["TICK1"].best_yes_bid == "0.4500"
        assert result["TICK1"].best_no_bid == "0.5000"
        assert result["TICK1"].orderbook.yes_dollars == [
            ("0.0100", "1000.00"), ("0.4500", "200.00"),
        ]
        assert result["TICK2"].best_yes_bid == "0.3000"
        assert result["TICK2"].best_no_bid is None

        call_args = client._session.request.call_args
        assert call_args.args[0] == "GET"
        url = call_args.args[1]
        assert "/markets/orderbooks?" in url

    def test_get_orderbooks_uses_repeated_params(self, client, mock_response):
        """Tickers must be repeated params, never comma-joined (the API
        silently misreads tickers=A,B as one bogus ticker)."""
        client._session.request.return_value = mock_response({"orderbooks": []})

        client.get_orderbooks(["TICK1", "TICK2", "TICK3"])

        url = client._session.request.call_args.args[1]
        assert "tickers=TICK1&tickers=TICK2&tickers=TICK3" in url
        assert "%2C" not in url

    def test_get_orderbooks_comma_ticker_raises(self, client):
        """A ticker containing a comma is rejected before any request."""
        with pytest.raises(ValueError, match="comma"):
            client.get_orderbooks(["TICK1,TICK2"])
        client._session.request.assert_not_called()

    def test_get_orderbooks_empty_raises(self, client):
        """An empty ticker list is rejected."""
        with pytest.raises(ValueError, match="empty"):
            client.get_orderbooks([])
        client._session.request.assert_not_called()

    def test_get_orderbooks_normalizes_and_dedupes(self, client, mock_response):
        """Tickers are uppercased and duplicates collapse to one request."""
        client._session.request.return_value = mock_response({"orderbooks": []})

        client.get_orderbooks(["tick1", "TICK1", "tick2"])

        assert client._session.request.call_count == 1
        url = client._session.request.call_args.args[1]
        assert "tickers=TICK1&tickers=TICK2" in url

    def test_get_orderbooks_chunks_over_100(self, client, mock_response):
        """More than 100 tickers are split into sequential requests of <=100
        and the results merged."""
        from urllib.parse import urlparse, parse_qs

        tickers = [f"T{i:03d}" for i in range(150)]

        def respond(chunk):
            return mock_response({
                "orderbooks": [
                    {"ticker": t, "orderbook_fp": {"yes_dollars": [["0.0100", "1.00"]]}}
                    for t in chunk
                ]
            })

        client._session.request.side_effect = [
            respond(tickers[:100]),
            respond(tickers[100:]),
        ]

        result = client.get_orderbooks(tickers)

        assert client._session.request.call_count == 2
        sent = [
            parse_qs(urlparse(call.args[1]).query)["tickers"]
            for call in client._session.request.call_args_list
        ]
        assert sent[0] == tickers[:100]
        assert sent[1] == tickers[100:]
        assert len(result) == 150
        assert result["T149"].best_yes_bid == "0.0100"

    def test_get_orderbooks_null_book_tolerated(self, client, mock_response):
        """A null/absent orderbook_fp yields an empty book, not an error."""
        client._session.request.return_value = mock_response({
            "orderbooks": [{"ticker": "TICK1", "orderbook_fp": None}]
        })

        result = client.get_orderbooks(["TICK1"])

        assert result["TICK1"].best_yes_bid is None
        assert result["TICK1"].best_no_bid is None

    def test_get_orderbooks_extra_params_forwarded(self, client, mock_response):
        """extra_params are appended to the query string of each request."""
        client._session.request.return_value = mock_response({"orderbooks": []})

        client.get_orderbooks(["TICK1"], foo="bar")

        url = client._session.request.call_args.args[1]
        assert "tickers=TICK1" in url
        assert "foo=bar" in url
