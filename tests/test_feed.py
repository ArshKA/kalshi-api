"""Tests for the WebSocket Feed module."""

import json
import pytest
from unittest.mock import MagicMock

from pykalshi.feed import (
    Feed,
    TickerMessage,
    OrderbookSnapshotMessage,
    OrderbookDeltaMessage,
    TradeMessage,
    FillMessage,
    PositionMessage,
    DEFAULT_WS_BASE,
    DEMO_WS_BASE,
    _parse_ts,
)


class TestParseTs:
    """Issue #18: Kalshi switched ts from int ms to ISO 8601 in April 2026."""

    def test_int_passes_through(self):
        assert _parse_ts(1776882719000) == 1776882719000

    def test_iso_string(self):
        assert _parse_ts("2026-04-22T18:31:59.043421Z") == 1776882719043

    def test_garbage_returns_none(self):
        assert _parse_ts("not-a-timestamp") is None


class TestFeedCreation:
    """Tests for Feed initialization."""

    def test_demo_url(self, client):
        """Feed uses demo WS URL when client is in demo mode."""
        feed = Feed(client)
        assert feed._ws_url == DEMO_WS_BASE

    def test_production_url(self, client):
        """Feed uses production WS URL when client is in production mode."""
        client.api_base = "https://api.elections.kalshi.com/trade-api/v2"
        feed = Feed(client)
        assert feed._ws_url == DEFAULT_WS_BASE

    def test_initial_state(self, client):
        """Feed starts in disconnected state with no subs or handlers."""
        feed = Feed(client)
        assert not feed.is_connected
        assert feed._active_subs == []
        assert feed._handlers == {}
        assert feed._running is False

    def test_client_feed_method(self, client):
        """client.feed() returns a new Feed instance."""
        feed = client.feed()
        assert isinstance(feed, Feed)
        assert feed._client is client


class TestHandlerRegistration:
    """Tests for handler registration via on()."""

    def test_on_direct_call(self, client):
        """on() can register handler via direct call."""
        feed = Feed(client)
        handler = MagicMock()
        feed.on("ticker", handler)
        assert feed._handlers["ticker"] == [handler]

    def test_on_decorator(self, client):
        """on() can be used as a decorator."""
        feed = Feed(client)

        @feed.on("ticker")
        def handler(msg):
            pass

        assert feed._handlers["ticker"] == [handler]

    def test_on_decorator_preserves_function(self, client):
        """Decorator returns the original function unchanged."""
        feed = Feed(client)

        def original(msg):
            return 42

        decorated = feed.on("ticker")(original)
        assert decorated is original
        assert decorated(None) == 42

    def test_multiple_handlers_same_channel(self, client):
        """Multiple handlers can be registered for the same channel."""
        feed = Feed(client)
        h1 = MagicMock()
        h2 = MagicMock()
        feed.on("ticker", h1)
        feed.on("ticker", h2)
        assert feed._handlers["ticker"] == [h1, h2]

    def test_handlers_different_channels(self, client):
        """Handlers for different channels are stored separately."""
        feed = Feed(client)
        h1 = MagicMock()
        h2 = MagicMock()
        feed.on("ticker", h1)
        feed.on("trade", h2)
        assert feed._handlers["ticker"] == [h1]
        assert feed._handlers["trade"] == [h2]


class TestSubscriptions:
    """Tests for subscription management."""

    def test_subscribe_stores_params(self, client):
        """subscribe() stores subscription parameters."""
        feed = Feed(client)
        feed.subscribe("ticker", market_ticker="ABC-123")
        assert len(feed._active_subs) == 1
        assert feed._active_subs[0] == {
            "channels": ["ticker"],
            "market_ticker": "ABC-123",
        }

    def test_subscribe_multiple_tickers(self, client):
        """subscribe() supports multiple market tickers."""
        feed = Feed(client)
        feed.subscribe("ticker", market_tickers=["A", "B", "C"])
        assert feed._active_subs[0]["market_tickers"] == ["A", "B", "C"]

    def test_subscribe_no_market_filter(self, client):
        """subscribe() works without market filter (for fill channel)."""
        feed = Feed(client)
        feed.subscribe("fill")
        assert feed._active_subs[0] == {"channels": ["fill"]}

    def test_multiple_subscriptions(self, client):
        """Multiple subscriptions are tracked independently."""
        feed = Feed(client)
        feed.subscribe("ticker", market_ticker="ABC")
        feed.subscribe("trade", market_ticker="DEF")
        feed.subscribe("fill")
        assert len(feed._active_subs) == 3

    def test_unsubscribe_removes_matching(self, client):
        """unsubscribe() removes the matching subscription."""
        feed = Feed(client)
        feed.subscribe("ticker", market_ticker="ABC")
        feed.subscribe("trade", market_ticker="DEF")
        feed.unsubscribe("ticker", market_ticker="ABC")
        assert len(feed._active_subs) == 1
        assert feed._active_subs[0]["channels"] == ["trade"]

    def test_unsubscribe_no_match(self, client):
        """unsubscribe() is safe when no matching subscription exists."""
        feed = Feed(client)
        feed.subscribe("ticker", market_ticker="ABC")
        feed.unsubscribe("ticker", market_ticker="XYZ")  # Different ticker
        assert len(feed._active_subs) == 1  # Original still there


class TestDispatch:
    """Tests for message dispatch and parsing."""

    def test_ticker_message(self, client):
        """Ticker messages are parsed and dispatched correctly."""
        feed = Feed(client)
        received = []
        feed.on("ticker", received.append)

        raw = json.dumps({
            "type": "ticker",
            "sid": 1,
            "seq": 1,
            "msg": {
                "market_ticker": "ABC-123",
                "yes_bid_dollars": "0.45",
                "yes_ask_dollars": "0.55",
                "volume_fp": "1000.00",
            }
        })
        feed._dispatch(raw)

        assert len(received) == 1
        msg = received[0]
        assert isinstance(msg, TickerMessage)
        assert msg.market_ticker == "ABC-123"
        assert msg.yes_bid_dollars == "0.45"
        assert msg.yes_ask_dollars == "0.55"
        assert msg.volume_fp == "1000.00"

    def test_orderbook_snapshot_dispatches_to_delta_handlers(self, client):
        """orderbook_snapshot messages go to orderbook_delta handlers."""
        feed = Feed(client)
        received = []
        feed.on("orderbook_delta", received.append)

        raw = json.dumps({
            "type": "orderbook_snapshot",
            "sid": 2,
            "seq": 1,
            "msg": {
                "market_ticker": "ABC-123",
                "yes_dollars": [["0.45", "100.00"], ["0.50", "200.00"]],
                "no_dollars": [["0.55", "150.00"]],
            }
        })
        feed._dispatch(raw)

        assert len(received) == 1
        msg = received[0]
        assert isinstance(msg, OrderbookSnapshotMessage)
        assert msg.market_ticker == "ABC-123"
        assert msg.yes_dollars == [("0.45", "100.00"), ("0.50", "200.00")]
        assert msg.no_dollars == [("0.55", "150.00")]

    def test_orderbook_delta_message(self, client):
        """orderbook_delta messages are parsed correctly."""
        feed = Feed(client)
        received = []
        feed.on("orderbook_delta", received.append)

        raw = json.dumps({
            "type": "orderbook_delta",
            "sid": 2,
            "seq": 2,
            "msg": {
                "market_ticker": "ABC-123",
                "price_dollars": "0.45",
                "delta_fp": "-10.00",
                "side": "yes",
            }
        })
        feed._dispatch(raw)

        assert len(received) == 1
        msg = received[0]
        assert isinstance(msg, OrderbookDeltaMessage)
        assert msg.price_dollars == "0.45"
        assert msg.delta_fp == "-10.00"
        assert msg.side == "yes"

    def test_trade_message(self, client):
        """Trade messages are parsed correctly."""
        feed = Feed(client)
        received = []
        feed.on("trade", received.append)

        raw = json.dumps({
            "type": "trade",
            "sid": 3,
            "seq": 1,
            "msg": {
                "market_ticker": "ABC-123",
                "trade_id": "trade-1",
                "count_fp": "10.00",
                "yes_price_dollars": "0.55",
                "taker_side": "yes",
            }
        })
        feed._dispatch(raw)

        assert len(received) == 1
        msg = received[0]
        assert isinstance(msg, TradeMessage)
        assert msg.trade_id == "trade-1"
        assert msg.count_fp == "10.00"
        assert msg.yes_price_dollars == "0.55"
        assert msg.taker_side == "yes"

    def test_fill_message(self, client):
        """Fill messages are parsed correctly."""
        feed = Feed(client)
        received = []
        feed.on("fill", received.append)

        raw = json.dumps({
            "type": "fill",
            "sid": 4,
            "seq": 1,
            "msg": {
                "trade_id": "fill-1",
                "ticker": "ABC-123",
                "order_id": "ord-1",
                "side": "yes",
                "action": "buy",
                "count_fp": "5.00",
                "yes_price_dollars": "0.60",
                "is_taker": True,
            }
        })
        feed._dispatch(raw)

        assert len(received) == 1
        msg = received[0]
        assert isinstance(msg, FillMessage)
        assert msg.trade_id == "fill-1"
        assert msg.order_id == "ord-1"
        assert msg.is_taker is True

    def test_position_message(self, client):
        """Position messages are parsed correctly."""
        feed = Feed(client)
        received = []
        feed.on("market_positions", received.append)

        raw = json.dumps({
            "type": "market_position",
            "sid": 5,
            "seq": 1,
            "msg": {
                "ticker": "KXTEST-A",
                "position_fp": "10.00",
                "market_exposure_dollars": "4.50",
                "realized_pnl_dollars": "2.50",
                "total_traded_dollars": "25.00",
                "resting_orders_count": 2,
                "fees_paid_dollars": "0.50",
            }
        })
        feed._dispatch(raw)

        assert len(received) == 1
        msg = received[0]
        assert isinstance(msg, PositionMessage)
        assert msg.ticker == "KXTEST-A"
        assert msg.position_fp == "10.00"
        assert msg.market_exposure_dollars == "4.50"
        assert msg.realized_pnl_dollars == "2.50"

    def test_no_handler_registered(self, client):
        """Messages are silently dropped when no handler is registered."""
        feed = Feed(client)
        raw = json.dumps({
            "type": "ticker",
            "sid": 1,
            "seq": 1,
            "msg": {"market_ticker": "X"}
        })
        # Should not raise
        feed._dispatch(raw)

    def test_handler_error_logged_not_raised(self, client):
        """Handler exceptions are logged but don't crash the feed."""
        feed = Feed(client)

        def bad_handler(msg):
            raise ValueError("boom")

        feed.on("ticker", bad_handler)
        raw = json.dumps({
            "type": "ticker",
            "sid": 1,
            "seq": 1,
            "msg": {"market_ticker": "X"}
        })
        # Should not raise
        feed._dispatch(raw)

    def test_multiple_handlers_all_called(self, client):
        """All registered handlers are called for each message."""
        feed = Feed(client)
        h1 = MagicMock()
        h2 = MagicMock()
        feed.on("ticker", h1)
        feed.on("ticker", h2)

        raw = json.dumps({
            "type": "ticker",
            "sid": 1,
            "seq": 1,
            "msg": {"market_ticker": "X"}
        })
        feed._dispatch(raw)

        h1.assert_called_once()
        h2.assert_called_once()

    def test_malformed_json_handled(self, client):
        """Malformed JSON is handled gracefully."""
        feed = Feed(client)
        feed.on("ticker", MagicMock())
        # Should not raise
        feed._dispatch("not json{{{")
        feed._dispatch(b"also not json")

    def test_missing_type_field(self, client):
        """Messages without type field are ignored."""
        feed = Feed(client)
        h = MagicMock()
        feed.on("ticker", h)

        raw = json.dumps({"msg": {"market_ticker": "X"}})
        feed._dispatch(raw)
        h.assert_not_called()

    def test_unknown_type_passes_raw_dict(self, client):
        """Unknown message types pass raw dict to handlers."""
        feed = Feed(client)
        received = []
        feed.on("unknown_channel", received.append)

        raw = json.dumps({
            "type": "unknown_channel",
            "sid": 1,
            "seq": 1,
            "msg": {"foo": "bar"}
        })
        feed._dispatch(raw)

        assert len(received) == 1
        assert received[0] == {"foo": "bar"}

    def test_extra_fields_ignored(self, client):
        """Extra fields in messages don't cause errors."""
        feed = Feed(client)
        received = []
        feed.on("ticker", received.append)

        raw = json.dumps({
            "type": "ticker",
            "sid": 1,
            "seq": 1,
            "msg": {
                "market_ticker": "ABC",
                "future_field": "unknown",
                "another_new_thing": 42,
            }
        })
        feed._dispatch(raw)

        assert len(received) == 1
        assert isinstance(received[0], TickerMessage)
        assert received[0].market_ticker == "ABC"


class TestAuthHeaders:
    """Tests for authentication header generation."""

    def test_auth_headers_structure(self, client):
        """Auth headers contain required fields."""
        feed = Feed(client)
        headers = feed._auth_headers()
        assert "KALSHI-ACCESS-KEY" in headers
        assert "KALSHI-ACCESS-SIGNATURE" in headers
        assert "KALSHI-ACCESS-TIMESTAMP" in headers

    def test_auth_headers_uses_client_key(self, client):
        """Auth headers use the client's API key."""
        feed = Feed(client)
        headers = feed._auth_headers()
        assert headers["KALSHI-ACCESS-KEY"] == "fake_key"


class TestRepr:
    """Tests for Feed string representation."""

    def test_repr_disconnected(self, client):
        """Repr shows disconnected state."""
        feed = Feed(client)
        assert "disconnected" in repr(feed)
        assert "subs=0" in repr(feed)

    def test_repr_with_subs(self, client):
        """Repr shows subscription count."""
        feed = Feed(client)
        feed.subscribe("ticker", market_ticker="ABC")
        feed.subscribe("trade", market_ticker="DEF")
        assert "subs=2" in repr(feed)


class TestMessageModels:
    """Tests for Pydantic message models."""

    def test_ticker_model_optional_fields(self):
        """TickerMessage handles optional fields."""
        msg = TickerMessage(market_ticker="TEST")
        assert msg.market_ticker == "TEST"
        assert msg.yes_bid_dollars is None
        assert msg.volume_fp is None

    def test_ticker_model_all_fields(self):
        """TickerMessage accepts all fields."""
        msg = TickerMessage(
            market_ticker="TEST",
            price_dollars="0.50",
            yes_bid_dollars="0.45",
            yes_ask_dollars="0.55",
            volume_fp="1000.00",
            open_interest_fp="500.00",
            dollar_volume_dollars="500.00",
            dollar_open_interest_dollars="250.00",
            ts=1234567890,
        )
        assert msg.yes_bid_dollars == "0.45"
        assert msg.ts == 1234567890

    def test_orderbook_snapshot_model(self):
        """OrderbookSnapshotMessage parses correctly."""
        msg = OrderbookSnapshotMessage(
            market_ticker="TEST",
            yes_dollars=[("0.45", "100.00"), ("0.50", "200.00")],
            no_dollars=[("0.55", "150.00")],
        )
        assert len(msg.yes_dollars) == 2
        assert msg.yes_dollars[0] == ("0.45", "100.00")
        assert msg.no_dollars[0] == ("0.55", "150.00")

    def test_orderbook_delta_model(self):
        """OrderbookDeltaMessage parses correctly."""
        msg = OrderbookDeltaMessage(
            market_ticker="TEST",
            price_dollars="0.45",
            delta_fp="-10.00",
            side="yes",
        )
        assert msg.delta_fp == "-10.00"
        assert msg.side == "yes"

    def test_trade_model(self):
        """TradeMessage parses correctly."""
        msg = TradeMessage(
            market_ticker="TEST",
            trade_id="t1",
            count_fp="10.00",
            yes_price_dollars="0.55",
            taker_side="yes",
        )
        assert msg.trade_id == "t1"
        assert msg.taker_side == "yes"

    def test_fill_model(self):
        """FillMessage parses correctly."""
        msg = FillMessage(
            trade_id="f1",
            ticker="TEST",
            order_id="o1",
            side="yes",
            action="buy",
            count_fp="5.00",
            yes_price_dollars="0.60",
            is_taker=True,
        )
        assert msg.count_fp == "5.00"
        assert msg.is_taker is True

    def test_position_model(self):
        """PositionMessage parses correctly."""
        msg = PositionMessage(
            ticker="KXTEST",
            position_fp="10.00",
            market_exposure_dollars="4.50",
            realized_pnl_dollars="2.50",
            total_traded_dollars="25.00",
            resting_orders_count=2,
            fees_paid_dollars="0.50",
            ts=1704067200,
        )
        assert msg.ticker == "KXTEST"
        assert msg.position_fp == "10.00"
        assert msg.realized_pnl_dollars == "2.50"
        assert msg.ts == 1704067200

    def test_ticker_model_accepts_iso_ts(self):
        """Issue #18: TsField coerces ISO strings so typed models still validate."""
        msg = TickerMessage(market_ticker="TEST", ts="2026-04-22T18:31:59Z")
        assert msg.ts == 1776882719000

    def test_models_ignore_extra_fields(self):
        """Models ignore unknown fields (forward compatibility)."""
        msg = TickerMessage(
            market_ticker="TEST",
            unknown_future_field="surprise",
        )
        assert msg.market_ticker == "TEST"
        assert not hasattr(msg, "unknown_future_field")


class TestLifecycle:
    """Tests for start/stop lifecycle."""

    def test_double_start_is_noop(self, client):
        """Starting an already-started feed is a no-op."""
        feed = Feed(client)
        feed._running = True
        feed.start()  # Should not create a new thread
        assert feed._thread is None  # No thread created

    def test_stop_when_not_started_is_safe(self, client):
        """Stopping a never-started feed is safe."""
        feed = Feed(client)
        feed.stop()  # Should not raise
        assert not feed.is_connected


class TestLatencyMetrics:
    """Tests for feed health and latency tracking."""

    def test_initial_metrics_are_none(self, client):
        """Latency metrics start as None before any messages."""
        feed = Feed(client)
        assert feed.latency_ms is None
        assert feed.uptime_seconds is None
        assert feed.seconds_since_last_message is None
        assert feed.messages_received == 0
        assert feed.reconnect_count == 0

    def test_message_count_increments(self, client):
        """Message count increments on each dispatch."""
        feed = Feed(client)
        feed.on("ticker", lambda x: None)  # Register handler

        for i in range(5):
            raw = json.dumps({
                "type": "ticker",
                "msg": {"market_ticker": "TEST"}
            })
            feed._dispatch(raw)

        assert feed.messages_received == 5

    def test_last_message_time_tracked(self, client):
        """Last message time is updated on dispatch."""
        feed = Feed(client)
        feed.on("ticker", lambda x: None)

        assert feed._last_message_at is None

        raw = json.dumps({
            "type": "ticker",
            "msg": {"market_ticker": "TEST"}
        })
        feed._dispatch(raw)

        assert feed._last_message_at is not None
        assert feed.seconds_since_last_message is not None
        assert feed.seconds_since_last_message >= 0

    def test_server_timestamp_extracted(self, client):
        """Server timestamp is extracted from message payload."""
        feed = Feed(client)
        feed.on("ticker", lambda x: None)

        server_ts = 1704067200000  # Example timestamp in ms
        raw = json.dumps({
            "type": "ticker",
            "msg": {"market_ticker": "TEST", "ts": server_ts}
        })
        feed._dispatch(raw)

        assert feed._last_server_ts == server_ts

    def test_server_timestamp_iso_string(self, client):
        """Issue #18: ISO 8601 ts must not raise (was crashing every message)."""
        feed = Feed(client)
        feed.on("ticker", lambda x: None)

        raw = json.dumps({
            "type": "ticker",
            "msg": {"market_ticker": "TEST", "ts": "2026-04-22T18:31:59.043421Z"},
        })
        feed._dispatch(raw)

        assert feed._last_server_ts == 1776882719043

    def test_latency_calculated_from_timestamps(self, client):
        """Latency is calculated when server timestamp is available."""
        import time
        feed = Feed(client)
        feed.on("ticker", lambda x: None)

        # Simulate message with server timestamp slightly in the past
        now_ms = int(time.time() * 1000)
        server_ts = now_ms - 50  # 50ms ago

        raw = json.dumps({
            "type": "ticker",
            "msg": {"market_ticker": "TEST", "ts": server_ts}
        })
        feed._dispatch(raw)

        # Latency should be approximately 50ms (with some tolerance for test execution)
        assert feed.latency_ms is not None
        assert feed.latency_ms >= 45  # Allow some tolerance
        assert feed.latency_ms < 200  # Sanity check

    def test_repr_shows_metrics(self, client):
        """Repr includes message count and latency when available."""
        import time
        feed = Feed(client)
        feed.on("ticker", lambda x: None)

        # Initial repr
        assert "msgs=0" in repr(feed)
        assert "latency=" not in repr(feed)

        # After message with timestamp
        now_ms = int(time.time() * 1000)
        raw = json.dumps({
            "type": "ticker",
            "msg": {"market_ticker": "TEST", "ts": now_ms - 25}
        })
        feed._dispatch(raw)

        repr_str = repr(feed)
        assert "msgs=1" in repr_str
        assert "latency=" in repr_str
        assert "ms" in repr_str

    def test_malformed_message_still_counts(self, client):
        """Malformed JSON still increments message count."""
        feed = Feed(client)

        feed._dispatch("not valid json {{{")

        assert feed.messages_received == 1
        assert feed._last_message_at is not None
