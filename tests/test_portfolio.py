"""Tests for portfolio functionality: positions, fills, and order retrieval."""

from decimal import Decimal

import json
import pytest
from unittest.mock import ANY
from pykalshi.enums import Action, Side, OrderStatus, PositionCountFilter
from pykalshi.portfolio import Portfolio


def test_get_positions_workflow(client, mock_response):
    """Test fetching portfolio positions."""
    client._session.request.return_value = mock_response(
        {
            "market_positions": [
                {
                    "ticker": "KXTEST-A",
                    "event_ticker": "KXTEST",
                    "position_fp": "10.00",
                    "total_traded_dollars": "25.00",
                    "resting_orders_count": 2,
                    "fees_paid_dollars": "0.50",
                    "realized_pnl_dollars": "1.00",
                },
                {
                    "ticker": "KXTEST-B",
                    "event_ticker": "KXTEST",
                    "position_fp": "-5.00",
                    "total_traded_dollars": "10.00",
                    "resting_orders_count": 0,
                    "fees_paid_dollars": "0.25",
                    "realized_pnl_dollars": "-0.30",
                },
            ],
            "cursor": "",
        }
    )

    positions = client.portfolio.get_positions()

    # Verify results
    assert len(positions) == 2
    assert positions[0].ticker == "KXTEST-A"
    assert positions[0].position_fp == "10.00"
    assert positions[1].position_fp == "-5.00"  # Short position

    # Verify endpoint called
    client._session.request.assert_called_with(
        "GET",
        "https://external-api.demo.kalshi.co/trade-api/v2/portfolio/positions?limit=100",
        headers=ANY,
        timeout=ANY,
    )


def test_get_positions_with_filters(client, mock_response):
    """Test fetching positions with filters."""
    client._session.request.return_value = mock_response(
        {"market_positions": [], "cursor": ""}
    )

    client.portfolio.get_positions(
        ticker="KXTEST-A", event_ticker="KXTEST", count_filter=PositionCountFilter.POSITION, limit=50
    )

    # Verify all filters passed in URL
    call_url = client._session.request.call_args.args[1]
    assert "ticker=KXTEST-A" in call_url
    assert "event_ticker=KXTEST" in call_url
    assert "count_filter=position" in call_url
    assert "limit=50" in call_url


def test_get_fills_workflow(client, mock_response):
    """Test fetching trade fills."""
    client._session.request.return_value = mock_response(
        {
            "fills": [
                {
                    "trade_id": "trade-001",
                    "ticker": "KXTEST",
                    "order_id": "order-123",
                    "side": "yes",
                    "action": "buy",
                    "count_fp": "5.00",
                    "yes_price_fixed": "0.50",
                    "no_price_fixed": "0.50",
                    "created_time": "2024-01-01T12:00:00Z",
                    "is_taker": True,
                },
                {
                    "trade_id": "trade-002",
                    "ticker": "KXTEST",
                    "order_id": "order-124",
                    "side": "no",
                    "action": "sell",
                    "count_fp": "3.00",
                    "yes_price_fixed": "0.45",
                    "no_price_fixed": "0.55",
                    "created_time": "2024-01-01T13:00:00Z",
                    "is_taker": False,
                },
            ],
            "cursor": "",
        }
    )

    fills = client.portfolio.get_fills()

    # Verify results
    assert len(fills) == 2
    assert fills[0].trade_id == "trade-001"
    assert fills[0].action == Action.BUY
    assert fills[0].side == Side.YES
    assert fills[0].count_fp == "5.00"
    assert fills[0].is_taker == True

    assert fills[1].action == Action.SELL
    assert fills[1].side == Side.NO

    # Verify endpoint called
    client._session.request.assert_called_with(
        "GET",
        "https://external-api.demo.kalshi.co/trade-api/v2/portfolio/fills?limit=100",
        headers=ANY,
        timeout=ANY,
    )


def test_get_fills_with_filters(client, mock_response):
    """Test fetching fills with filters."""
    client._session.request.return_value = mock_response(
        {"fills": [], "cursor": ""}
    )

    client.portfolio.get_fills(
        ticker="KXTEST",
        order_id="order-123",
        min_ts=1700000000,
        max_ts=1700100000,
        limit=25,
    )

    # Verify all filters in URL
    call_url = client._session.request.call_args.args[1]
    assert "ticker=KXTEST" in call_url
    assert "order_id=order-123" in call_url
    assert "min_ts=1700000000" in call_url
    assert "max_ts=1700100000" in call_url
    assert "limit=25" in call_url


def test_get_order_by_id(client, mock_response):
    """Test fetching a single order by ID."""
    client._session.request.return_value = mock_response(
        {
            "order": {
                "order_id": "order-abc-123",
                "ticker": "KXTEST",
                "action": "buy",
                "side": "yes",
                "initial_count_fp": "10.00",
                "yes_price_dollars": "0.55",
                "status": "resting",
                "type": "limit",
            }
        }
    )

    order = client.portfolio.get_order("order-abc-123")

    # Verify order data
    assert order.order_id == "order-abc-123"
    assert order.ticker == "KXTEST"
    assert order.status == OrderStatus.RESTING

    # Verify correct endpoint called
    client._session.request.assert_called_with(
        "GET",
        "https://external-api.demo.kalshi.co/trade-api/v2/portfolio/orders/order-abc-123",
        headers=ANY,
        timeout=ANY,
    )


def test_get_order_not_found(client, mock_response):
    """Test that 404 raises ResourceNotFoundError."""
    from pykalshi.exceptions import ResourceNotFoundError

    client._session.request.return_value = mock_response(
        {"message": "Order not found", "code": "not_found"}, status_code=404
    )

    with pytest.raises(ResourceNotFoundError):
        client.portfolio.get_order("nonexistent-order")


def test_cancel_order(client, mock_response):
    """Test canceling an order by ID."""
    # CancelOrderV2Response: a thin ack, not a full order object.
    client._session.request.return_value = mock_response(
        {
            "order_id": "order-abc-123",
            "client_order_id": "client-abc-123",
            "reduced_by": "10.00",
            "ts_ms": 1715793660456,
        }
    )

    order = client.portfolio.cancel_order("order-abc-123")

    assert order.order_id == "order-abc-123"
    assert order.status == OrderStatus.CANCELED
    assert order.data.client_order_id == "client-abc-123"

    # Verify DELETE request
    client._session.request.assert_called_with(
        "DELETE",
        "https://external-api.demo.kalshi.co/trade-api/v2/portfolio/events/orders/order-abc-123",
        headers=ANY,
        timeout=ANY,
    )


def test_order_cancel_delegates_to_portfolio(client, mock_response):
    """Test that Order.cancel() delegates to Portfolio.cancel_order()."""
    from pykalshi.orders import Order
    from pykalshi.models import OrderModel

    # Initial order state
    initial_model = OrderModel(
        order_id="order-abc-123",
        ticker="KXTEST",
        status=OrderStatus.RESTING,
    )
    order = Order(client, initial_model)

    # Mock the cancel response
    client._session.request.return_value = mock_response(
        {"order_id": "order-abc-123", "reduced_by": "10.00", "ts_ms": 1715793660456}
    )

    result = order.cancel()

    # Should return self
    assert result is order
    # Should update internal data
    assert order.status == OrderStatus.CANCELED


def test_order_amend(client, mock_response):
    """Test Order.amend() method."""
    from pykalshi.orders import Order
    from pykalshi.models import OrderModel

    initial_model = OrderModel(
        order_id="order-abc-123",
        ticker="KXTEST",
        status=OrderStatus.RESTING,
        action=Action.BUY,
        side=Side.YES,
        yes_price_dollars="0.50",
        remaining_count_fp="10.00",
    )
    order = Order(client, initial_model)

    # AmendOrderV2Response is a thin ack.
    client._session.request.return_value = mock_response(
        {
            "order_id": "order-abc-123",
            "remaining_count": "10.00",
            "fill_count": "0.00",
            "ts_ms": 1715793690123,
        }
    )

    result = order.amend(yes_price_dollars="0.55")

    assert result is order
    assert order.yes_price_dollars == "0.5500"

    # Verify POST to amend endpoint
    call_args = client._session.request.call_args
    assert call_args.args[0] == "POST"
    assert "/portfolio/events/orders/order-abc-123/amend" in call_args.args[1]

    # AmendOrderV2Request: ticker, side (bid/ask), price, count -- all required.
    body = json.loads(call_args.kwargs["content"])
    assert body == {
        "ticker": "KXTEST",
        "side": "bid",
        "price": "0.5500",
        "count": "10.00",
    }


def test_order_decrease(client, mock_response):
    """Test Order.decrease() method."""
    from pykalshi.orders import Order
    from pykalshi.models import OrderModel

    initial_model = OrderModel(
        order_id="order-abc-123",
        ticker="KXTEST",
        status=OrderStatus.RESTING,
        remaining_count_fp="10.00",
    )
    order = Order(client, initial_model)

    # DecreaseOrderV2Response is a thin ack.
    client._session.request.return_value = mock_response(
        {
            "order_id": "order-abc-123",
            "remaining_count": "7.00",
            "ts_ms": 1715793690123,
        }
    )

    result = order.decrease(reduce_by_fp="3.00")

    assert result is order
    assert order.remaining_count_fp == "7.00"

    # Verify POST to decrease endpoint
    call_args = client._session.request.call_args
    assert call_args.args[0] == "POST"
    assert "/portfolio/events/orders/order-abc-123/decrease" in call_args.args[1]
    # DecreaseOrderV2Request uses reduce_by, not the v1 reduce_by_fp.
    assert json.loads(call_args.kwargs["content"]) == {"reduce_by": "3.00"}


def test_order_refresh(client, mock_response):
    """Test Order.refresh() method."""
    from pykalshi.orders import Order
    from pykalshi.models import OrderModel

    initial_model = OrderModel(
        order_id="order-abc-123",
        ticker="KXTEST",
        status=OrderStatus.RESTING,
        fill_count_fp="0",
    )
    order = Order(client, initial_model)

    # Simulate order getting partially filled
    client._session.request.return_value = mock_response(
        {
            "order": {
                "order_id": "order-abc-123",
                "ticker": "KXTEST",
                "status": "resting",
                "fill_count_fp": "5.00",
            }
        }
    )

    result = order.refresh()

    assert result is order
    assert order.fill_count_fp == "5.00"

    # Verify GET to order endpoint
    client._session.request.assert_called_with(
        "GET",
        "https://external-api.demo.kalshi.co/trade-api/v2/portfolio/orders/order-abc-123",
        headers=ANY,
        timeout=ANY,
    )


def test_order_wait_until_terminal_executed(client, mock_response, mocker):
    """Test wait_until_terminal returns when order becomes EXECUTED."""
    from pykalshi.orders import Order
    from pykalshi.models import OrderModel

    initial_model = OrderModel(
        order_id="order-abc-123",
        ticker="KXTEST",
        status=OrderStatus.RESTING,
    )
    order = Order(client, initial_model)

    # Mock time to avoid actual sleeping
    mocker.patch("pykalshi._sync.orders.time.sleep")
    mock_monotonic = mocker.patch("pykalshi._sync.orders.time.monotonic")
    mock_monotonic.side_effect = [0.0, 0.5, 1.0]  # start, check, check

    # First refresh: still resting, second refresh: executed
    client._session.request.side_effect = [
        mock_response({"order": {"order_id": "order-abc-123", "ticker": "KXTEST", "status": "resting"}}),
        mock_response({"order": {"order_id": "order-abc-123", "ticker": "KXTEST", "status": "executed"}}),
    ]

    result = order.wait_until_terminal(timeout=5.0)

    assert result is order
    assert order.status == OrderStatus.EXECUTED
    assert client._session.request.call_count == 2


def test_order_wait_until_terminal_already_terminal(client, mock_response, mocker):
    """Test wait_until_terminal returns immediately if already terminal."""
    from pykalshi.orders import Order
    from pykalshi.models import OrderModel

    initial_model = OrderModel(
        order_id="order-abc-123",
        ticker="KXTEST",
        status=OrderStatus.CANCELED,
    )
    order = Order(client, initial_model)

    mock_sleep = mocker.patch("pykalshi._sync.orders.time.sleep")

    result = order.wait_until_terminal(timeout=5.0)

    assert result is order
    assert order.status == OrderStatus.CANCELED
    mock_sleep.assert_not_called()
    client._session.request.assert_not_called()


def test_order_wait_until_terminal_timeout(client, mock_response, mocker):
    """Test wait_until_terminal raises TimeoutError when deadline exceeded."""
    from pykalshi.orders import Order
    from pykalshi.models import OrderModel

    initial_model = OrderModel(
        order_id="order-abc-123",
        ticker="KXTEST",
        status=OrderStatus.RESTING,
    )
    order = Order(client, initial_model)

    mocker.patch("pykalshi._sync.orders.time.sleep")
    mock_monotonic = mocker.patch("pykalshi._sync.orders.time.monotonic")
    # Simulate time passing: start at 0, then jump past deadline
    mock_monotonic.side_effect = [0.0, 0.5, 2.1]  # start, first check (ok), second check (past deadline)

    client._session.request.return_value = mock_response(
        {"order": {"order_id": "order-abc-123", "ticker": "KXTEST", "status": "resting"}}
    )

    with pytest.raises(TimeoutError) as exc_info:
        order.wait_until_terminal(timeout=2.0)

    assert "order-abc-123" in str(exc_info.value)
    assert "resting" in str(exc_info.value)


# --- Tick size validation ---

class TestValidateTickSize:
    """Tests for Portfolio._validate_tick_size."""

    _validate = staticmethod(Portfolio._validate_tick_size)

    # linear_cent: tick $0.01

    def test_linear_cent_valid(self):
        self._validate(Decimal("0.50"), "linear_cent")
        self._validate(Decimal("0.01"), "linear_cent")
        self._validate(Decimal("1.00"), "linear_cent")

    def test_linear_cent_invalid(self):
        with pytest.raises(ValueError, match="linear_cent"):
            self._validate(Decimal("0.505"), "linear_cent")

    # deci_cent: tick $0.001

    def test_deci_cent_valid(self):
        self._validate(Decimal("0.501"), "deci_cent")
        self._validate(Decimal("0.001"), "deci_cent")
        self._validate(Decimal("0.01"), "deci_cent")

    def test_deci_cent_invalid(self):
        with pytest.raises(ValueError, match="deci_cent"):
            self._validate(Decimal("0.5005"), "deci_cent")

    # tapered_deci_cent: $0.001 at edges, $0.01 in middle

    def test_tapered_edges_valid(self):
        """Prices at or below $0.10 and at or above $0.90 use $0.001 tick."""
        self._validate(Decimal("0.051"), "tapered_deci_cent")
        self._validate(Decimal("0.100"), "tapered_deci_cent")
        self._validate(Decimal("0.901"), "tapered_deci_cent")
        self._validate(Decimal("0.999"), "tapered_deci_cent")

    def test_tapered_middle_valid(self):
        """Prices between $0.10 and $0.90 use $0.01 tick."""
        self._validate(Decimal("0.50"), "tapered_deci_cent")
        self._validate(Decimal("0.11"), "tapered_deci_cent")
        self._validate(Decimal("0.89"), "tapered_deci_cent")

    def test_tapered_middle_invalid(self):
        """$0.001 granularity rejected in the $0.10-$0.90 middle range."""
        with pytest.raises(ValueError, match="tapered_deci_cent"):
            self._validate(Decimal("0.501"), "tapered_deci_cent")

    def test_tapered_boundary_at_010(self):
        """$0.10 exactly is in the edge zone (tick $0.001)."""
        self._validate(Decimal("0.100"), "tapered_deci_cent")
        self._validate(Decimal("0.099"), "tapered_deci_cent")

    def test_tapered_just_above_010_invalid(self):
        """$0.101 is in the middle zone (tick $0.01), so $0.001 granularity fails."""
        with pytest.raises(ValueError, match="tapered_deci_cent"):
            self._validate(Decimal("0.101"), "tapered_deci_cent")

    def test_tapered_boundary_at_090(self):
        """$0.90 is in the edge zone (tick $0.001)."""
        self._validate(Decimal("0.900"), "tapered_deci_cent")

    def test_tapered_boundary_just_below_090(self):
        """$0.899 is in the middle zone -> tick $0.01 -> 0.899 invalid."""
        with pytest.raises(ValueError, match="tapered_deci_cent"):
            self._validate(Decimal("0.899"), "tapered_deci_cent")


# --- Fractional validation ---

class TestValidateFractional:
    """Tests for Portfolio._validate_fractional."""

    _validate = staticmethod(Portfolio._validate_fractional)

    def test_whole_count_fractional_disabled(self):
        self._validate("10", fractional_enabled=False)
        self._validate("1", fractional_enabled=False)

    def test_fractional_count_fractional_disabled(self):
        with pytest.raises(ValueError, match="Fractional trading is not enabled"):
            self._validate("10.50", fractional_enabled=False)

    def test_fractional_count_fractional_enabled(self):
        self._validate("10.50", fractional_enabled=True)
        self._validate("0.01", fractional_enabled=True)


# ---------------------------------------------------------------------------
# V2 order surface
#
# Kalshi deprecated the v1 order WRITE endpoints (POST /portfolio/orders now
# returns 410 deprecated_v1_order_endpoint) but kept the READ endpoints where
# they were. These tests pin both halves of that split, and pin the V2
# request/response shapes so a mock can't drift back to the v1 contract.
# ---------------------------------------------------------------------------

def _create_ack(order_id="order-abc-123", remaining="10.00", fill="0.00"):
    """CreateOrderV2Response -- a thin ack, not a full order object."""
    return {
        "order_id": order_id,
        "client_order_id": "client-abc-123",
        "fill_count": fill,
        "remaining_count": remaining,
        "ts_ms": 1715793600123,
    }


def test_place_order_sends_v2_request_shape(client, mock_response):
    """Buying YES maps to a bid at the YES price."""
    client._session.request.return_value = mock_response(_create_ack())

    client.portfolio.place_order(
        "KXTEST", Action.BUY, Side.YES, count_fp="10.00",
        yes_price_dollars="0.55", post_only=True,
    )

    call_args = client._session.request.call_args
    assert call_args.args[0] == "POST"
    assert call_args.args[1].endswith("/portfolio/events/orders")

    body = json.loads(call_args.kwargs["content"])
    # V2 is a single YES-denominated book: side is bid/ask, price is `price`,
    # count is `count`. None of the v1 keys should survive.
    assert body["ticker"] == "KXTEST"
    assert body["side"] == "bid"
    assert body["price"] == "0.5500"
    assert body["count"] == "10.00"
    assert body["post_only"] is True
    for stale in ("action", "count_fp", "yes_price_dollars", "no_price_dollars", "type"):
        assert stale not in body


def test_place_order_buy_no_maps_to_ask_at_yes_price(client, mock_response):
    """Buying NO at 0.83 is selling YES at 0.17 -- an ask, YES-denominated."""
    client._session.request.return_value = mock_response(_create_ack())

    client.portfolio.place_order(
        "KXTEST", Action.BUY, Side.NO, count_fp="10.00", no_price_dollars="0.83",
    )

    body = json.loads(client._session.request.call_args.kwargs["content"])
    assert body["side"] == "ask"
    assert body["price"] == "0.1700"


def test_place_order_parses_v2_ack(client, mock_response):
    """The thin ack still yields a usable Order without an extra round-trip."""
    client._session.request.return_value = mock_response(_create_ack())

    order = client.portfolio.place_order(
        "KXTEST", Action.BUY, Side.YES, count_fp="10.00", yes_price_dollars="0.55",
    )

    assert order.order_id == "order-abc-123"
    assert order.ticker == "KXTEST"
    assert order.status == OrderStatus.RESTING
    assert order.remaining_count_fp == "10.00"
    assert order.fill_count_fp == "0.00"
    assert order.data.yes_price_dollars == "0.5500"
    assert client._session.request.call_count == 1


def test_place_order_fully_filled_ack_is_executed(client, mock_response):
    client._session.request.return_value = mock_response(
        _create_ack(remaining="0.00", fill="10.00")
    )

    order = client.portfolio.place_order(
        "KXTEST", Action.BUY, Side.YES, count_fp="10.00", yes_price_dollars="0.55",
    )

    assert order.status == OrderStatus.EXECUTED


def test_get_orders_uses_v1_read_path(client, mock_response):
    """Listing orders was NOT migrated; /portfolio/events/orders 404s."""
    client._session.request.return_value = mock_response({"orders": [], "cursor": ""})

    list(client.portfolio.get_orders(status=OrderStatus.RESTING))

    call_url = client._session.request.call_args.args[1]
    assert "/portfolio/orders" in call_url
    assert "/portfolio/events/orders" not in call_url


def test_queue_position_uses_v1_read_path(client, mock_response):
    client._session.request.return_value = mock_response(
        {"queue_position": 3, "order_id": "order-abc-123"}
    )

    client.portfolio.get_queue_position("order-abc-123")

    call_url = client._session.request.call_args.args[1]
    assert call_url.endswith("/portfolio/orders/order-abc-123/queue_position")


def test_batch_place_orders_converts_to_v2_items(client, mock_response):
    client._session.request.return_value = mock_response(
        {"orders": [_create_ack("o1"), _create_ack("o2")]}
    )

    orders = client.portfolio.batch_place_orders([
        {"ticker": "KXTEST", "action": "buy", "side": "yes",
         "count_fp": "10.00", "yes_price_dollars": "0.45"},
        {"ticker": "KXTEST", "action": "buy", "side": "no",
         "count_fp": "5.00", "no_price_dollars": "0.45"},
    ])

    body = json.loads(client._session.request.call_args.kwargs["content"])
    # time_in_force and self_trade_prevention_type are required by
    # BatchCreateOrdersV2Request, so they are filled in when not supplied.
    assert body["orders"][0] == {
        "ticker": "KXTEST", "side": "bid", "count": "10.00", "price": "0.4500",
        "time_in_force": "good_till_canceled",
        "self_trade_prevention_type": "maker",
    }
    assert body["orders"][1] == {
        "ticker": "KXTEST", "side": "ask", "count": "5.00", "price": "0.5500",
        "time_in_force": "good_till_canceled",
        "self_trade_prevention_type": "maker",
    }
    assert [o.order_id for o in orders] == ["o1", "o2"]
    # Batch acks carry no ticker/price either, so the request context must be
    # folded back in -- otherwise callers get blank tickers and null prices.
    assert [o.ticker for o in orders] == ["KXTEST", "KXTEST"]
    assert orders[0].data.yes_price_dollars == "0.4500"
    assert orders[1].data.yes_price_dollars == "0.5500"
    assert orders[0].data.side == Side.YES
    assert orders[1].data.side == Side.NO


def test_batch_place_orders_matches_acks_by_client_order_id(client, mock_response):
    """Acks returned out of order must still line up with their requests."""
    client._session.request.return_value = mock_response({"orders": [
        {"order_id": "o2", "client_order_id": "c2", "remaining_count": "5.00", "ts_ms": 2},
        {"order_id": "o1", "client_order_id": "c1", "remaining_count": "10.00", "ts_ms": 1},
    ]})

    orders = client.portfolio.batch_place_orders([
        {"ticker": "KXAAA", "action": "buy", "side": "yes", "count_fp": "10.00",
         "yes_price_dollars": "0.45", "client_order_id": "c1"},
        {"ticker": "KXBBB", "action": "buy", "side": "yes", "count_fp": "5.00",
         "yes_price_dollars": "0.60", "client_order_id": "c2"},
    ])

    got = {o.order_id: (o.ticker, o.data.yes_price_dollars) for o in orders}
    assert got == {"o2": ("KXBBB", "0.6000"), "o1": ("KXAAA", "0.4500")}


def test_batch_cancel_orders_parses_ack_items(client, mock_response):
    client._session.request.return_value = mock_response(
        {"orders": [
            {"order_id": "o1", "reduced_by": "10.00", "ts_ms": 1},
            {"order_id": "o2", "reduced_by": "5.00", "ts_ms": 2},
        ]}
    )

    orders = client.portfolio.batch_cancel_orders(["o1", "o2"])

    assert [o.order_id for o in orders] == ["o1", "o2"]
    call_args = client._session.request.call_args
    assert call_args.args[0] == "DELETE"
    assert call_args.args[1].endswith("/portfolio/events/orders/batched")


def test_place_order_always_sends_required_v2_fields(client, mock_response):
    """time_in_force and self_trade_prevention_type are required by
    CreateOrderV2Request. Omitting them yields 400 missing_parameters, so they
    must be sent even when the caller passes nothing (or explicitly None)."""
    client._session.request.return_value = mock_response(_create_ack())

    client.portfolio.place_order(
        "KXTEST", Action.BUY, Side.YES, count_fp="1.00",
        yes_price_dollars="0.01", time_in_force=None, self_trade_prevention=None,
    )

    body = json.loads(client._session.request.call_args.kwargs["content"])
    assert body["time_in_force"] == "good_till_canceled"
    assert body["self_trade_prevention_type"] == "maker"


def test_order_cancel_preserves_known_fields(client, mock_response):
    """A V2 ack must not wipe fields the Order already knew.

    cancel/amend/decrease return a thin ack with no ticker/side/price. Replacing
    the model wholesale would blank them on an object that was fully populated.
    """
    from pykalshi.orders import Order
    from pykalshi.models import OrderModel

    order = Order(client, OrderModel(
        order_id="order-abc-123",
        ticker="KXTEST",
        status=OrderStatus.RESTING,
        action=Action.BUY,
        side=Side.YES,
        yes_price_dollars="0.55",
        remaining_count_fp="10.00",
    ))

    client._session.request.return_value = mock_response(
        {"order_id": "order-abc-123", "reduced_by": "10.00", "ts_ms": 1}
    )

    order.cancel()

    assert order.status == OrderStatus.CANCELED   # updated from the ack
    assert order.ticker == "KXTEST"               # preserved
    assert order.data.action == Action.BUY        # preserved
    assert order.data.side == Side.YES            # preserved
    assert order.data.yes_price_dollars == "0.55" # preserved
