"""Tests for portfolio functionality: positions, fills, and order retrieval."""

from decimal import Decimal

import json
import pytest
from unittest.mock import ANY
from pykalshi.enums import Action, Side, OrderStatus, PositionCountFilter, TimeInForce
from pykalshi.portfolio import Portfolio


def test_get_balance_documented_response(client, mock_response):
    """Balance parses the documented response, including balance_dollars and breakdown."""
    client._session.request.return_value = mock_response(
        {
            "balance": 5600,
            "balance_dollars": "56.0001",
            "portfolio_value": 10000,
            "updated_ts": 1784701854,
            "balance_breakdown": [
                {"exchange_index": 0, "balance": "56.0001"},
            ],
        }
    )

    balance = client.portfolio.get_balance()

    assert balance.balance == 5600
    assert balance.balance_dollars == "56.0001"
    assert balance.portfolio_value == 10000
    assert balance.balance_breakdown[0].exchange_index == 0
    assert balance.balance_breakdown[0].balance == "56.0001"

    # No query params by default
    call_url = client._session.request.call_args.args[1]
    assert call_url.endswith("/portfolio/balance")


def test_get_balance_without_breakdown(client, mock_response):
    """Older responses without balance_dollars/breakdown still parse."""
    client._session.request.return_value = mock_response(
        {"balance": 5000, "portfolio_value": 10000, "updated_ts": 1784701854}
    )

    balance = client.portfolio.get_balance()

    assert balance.balance == 5000
    assert balance.balance_dollars is None
    assert balance.balance_breakdown == []


def test_get_balance_query_params(client, mock_response):
    """subaccount and exchange_index are passed as query params."""
    client._session.request.return_value = mock_response(
        {"balance": 0, "balance_dollars": "0.0000", "portfolio_value": 0,
         "updated_ts": 1784701854}
    )

    client.portfolio.get_balance(subaccount=3, exchange_index=0)

    call_url = client._session.request.call_args.args[1]
    assert "/portfolio/balance?" in call_url
    assert "subaccount=3" in call_url
    assert "exchange_index=0" in call_url


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


def test_place_order_zero_fill_ack_is_canceled(client, mock_response):
    """An ack with no fills and nothing resting is a canceled order.

    This is what an unfilled IOC/FOK ack looks like (verified on demo:
    fill 0.00 / remaining 0.00, and GET on the order returns `canceled`).
    Reporting it EXECUTED tells the caller a position exists that doesn't.
    """
    client._session.request.return_value = mock_response(
        _create_ack(remaining="0.00", fill="0.00")
    )

    order = client.portfolio.place_order(
        "KXTEST", Action.BUY, Side.YES, count_fp="10.00", yes_price_dollars="0.55",
        time_in_force=TimeInForce.IOC,
    )

    assert order.status == OrderStatus.CANCELED


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


def test_batch_item_rejects_both_count_spellings(client):
    """count_fp and count together must raise, not race via item.update().

    Previously the short-circuiting `or` popped only count_fp, and the
    leftover `count` key silently overwrote the chosen value on the wire.
    """
    with pytest.raises(ValueError, match="count_fp or count, not both"):
        client.portfolio.batch_place_orders([{
            "ticker": "KXTEST", "action": "buy", "side": "yes",
            "yes_price_dollars": "0.50", "count_fp": "10", "count": "99",
        }])


def test_place_order_rejects_removed_buy_max_cost_dollars(client):
    """buy_max_cost_dollars was removed: CreateOrderV2Request has no such
    field, so the server silently ignored the advertised slippage cap. It
    must fail loudly rather than place an uncapped order."""
    with pytest.raises(TypeError, match="buy_max_cost_dollars"):
        client.portfolio.place_order(
            "KXTEST", Action.BUY, Side.YES, count_fp="10.00",
            yes_price_dollars="0.50", buy_max_cost_dollars="5.00",
        )
    client._session.request.assert_not_called()


def test_batch_item_rejects_unknown_keys(client):
    """Unknown batch item keys must raise instead of being forwarded: the
    server ignores fields it does not know, turning them into silent no-ops
    (the removed buy_max_cost_dollars was exactly this)."""
    with pytest.raises(ValueError, match="buy_max_cost_dollars"):
        client.portfolio.batch_place_orders([{
            "ticker": "KXTEST", "action": "buy", "side": "yes",
            "count_fp": "10.00", "yes_price_dollars": "0.50",
            "buy_max_cost_dollars": "5.00",
        }])
    client._session.request.assert_not_called()


def test_batch_item_passes_through_known_v2_fields(client, mock_response):
    """The unknown-key whitelist must not reject documented V2 fields."""
    client._session.request.return_value = mock_response(
        {"orders": [_create_ack("o1")]}
    )

    client.portfolio.batch_place_orders([{
        "ticker": "KXTEST", "action": "buy", "side": "yes",
        "count_fp": "10.00", "yes_price_dollars": "0.50",
        "client_order_id": "c1", "expiration_ts": 1800000000,
        "cancel_order_on_pause": True, "exchange_index": -1,
    }])

    body = json.loads(client._session.request.call_args.kwargs["content"])
    item = body["orders"][0]
    assert item["client_order_id"] == "c1"
    assert item["expiration_time"] == 1800000000
    assert item["cancel_order_on_pause"] is True
    assert item["exchange_index"] == -1
    assert "expiration_ts" not in item


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


def test_batch_cancel_orders_report_canceled_not_resting(client, mock_response):
    """A batch-cancel receipt carries no counts, so the count-derived status
    inferred `resting` -- the exact opposite of what happened, on the path a
    kill-switch uses to pull every order at once."""
    client._session.request.return_value = mock_response(
        {"orders": [
            {"order_id": "o1", "reduced_by": "10.00", "ts_ms": 1},
            {"order_id": "o2", "reduced_by": "5.00", "ts_ms": 2},
        ]}
    )

    orders = client.portfolio.batch_cancel_orders(["o1", "o2"])

    assert [o.status for o in orders] == [OrderStatus.CANCELED, OrderStatus.CANCELED]
    # reduced_by is the receipt's only payload: how much actually came off.
    assert [o.reduced_by_fp for o in orders] == ["10.00", "5.00"]


def test_batch_place_orders_warns_about_rejected_items(client, mock_response, caplog):
    """The API rejects batch items individually. A rejected item has no
    order_id and cannot become an Order, so it used to vanish -- 2 orders in,
    1 Order out, no exception and no log line."""
    client._session.request.return_value = mock_response({"orders": [
        {"order_id": "o1", "fill_count": "0.00", "remaining_count": "1.00", "ts_ms": 1},
        {"error": {"code": "market_not_found", "message": "market not found"},
         "ts_ms": None},
    ]})

    with caplog.at_level("WARNING", logger="pykalshi._sync.portfolio"):
        orders = client.portfolio.batch_place_orders([
            {"ticker": "KXREAL", "action": "buy", "side": "yes",
             "count_fp": "1.00", "yes_price_dollars": "0.01"},
            {"ticker": "KXGONE", "action": "buy", "side": "yes",
             "count_fp": "1.00", "yes_price_dollars": "0.01"},
        ])

    assert [o.order_id for o in orders] == ["o1"]
    assert "KXGONE" in caplog.text
    assert "market_not_found" in caplog.text


def test_batch_cancel_orders_warns_about_rejected_items(client, mock_response, caplog):
    """Same silence on the cancel leg: an order that did not cancel simply
    disappeared from the result.

    The cancel leg's failure shape differs from the create leg's, and the
    difference is the whole point of this test. BatchCancelOrdersV2Response
    *requires* order_id on every item, including failures -- reduced_by is
    "0.00" and ts_ms is absent when the cancel errored. A rejection check
    keyed on a missing order_id (which is correct for the create leg) lets
    this item straight through, and default_status=CANCELED then reports a
    still-resting order as canceled.
    """
    client._session.request.return_value = mock_response({"orders": [
        {"order_id": "o1", "reduced_by": "1.00", "ts_ms": 1},
        {"order_id": "o2", "reduced_by": "0.00", "ts_ms": None,
         "error": {"code": "not_found", "message": "not found"}},
    ]})

    with caplog.at_level("WARNING", logger="pykalshi._sync.portfolio"):
        orders = client.portfolio.batch_cancel_orders(["o1", "o2"])

    assert [o.order_id for o in orders] == ["o1"]
    assert "o2" in caplog.text
    assert "not_found" in caplog.text
    # The failed cancel must not come back wearing a CANCELED status.
    assert all(o.status != OrderStatus.CANCELED or o.order_id == "o1" for o in orders)


# place_order(buy_max_cost_dollars=...) is covered by
# test_place_order_rejects_removed_buy_max_cost_dollars above: the parameter was
# deleted from the signature outright, so it raises TypeError rather than the
# ValueError this branch originally proposed.


def test_batch_item_refuses_buy_max_cost_dollars(client):
    with pytest.raises(ValueError, match="buy_max_cost_dollars"):
        client.portfolio.batch_place_orders([{
            "ticker": "KXTEST", "action": "buy", "side": "yes",
            "count_fp": "1.00", "yes_price_dollars": "0.57",
            "buy_max_cost_dollars": "0.0001",
        }])


def test_place_order_keeps_the_realised_fill_price_and_fee(client, mock_response):
    """A marketable order's ack carries average_fill_price/average_fee_paid --
    the only place a caller sees what the order actually paid without a
    separate /portfolio/fills round-trip. Both used to be discarded."""
    ack = _create_ack(remaining="0.00", fill="1.00")
    ack["average_fill_price"] = "0.5700"
    ack["average_fee_paid"] = "0.0172"
    client._session.request.return_value = mock_response(ack)

    order = client.portfolio.place_order(
        "KXTEST", Action.BUY, Side.YES, count_fp="1.00",
        yes_price_dollars="0.57", time_in_force=TimeInForce.IOC,
    )

    assert order.average_fill_price_dollars == "0.5700"
    assert order.average_fee_paid_dollars == "0.0172"


def test_cancel_order_keeps_reduced_by(client, mock_response):
    """The cancel response is a reduce receipt; reduced_by says how many
    contracts actually came off the book."""
    client._session.request.return_value = mock_response(
        {"order_id": "o1", "reduced_by": "3.00", "ts_ms": 1}
    )

    order = client.portfolio.cancel_order("o1")

    assert order.status == OrderStatus.CANCELED
    assert order.reduced_by_fp == "3.00"


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


# --- Subaccounts ---
#
# Fixture JSON mirrors responses observed against the live production API
# (2026-07-26) plus the current docs.kalshi.com OpenAPI schemas. Where the two
# disagree (e.g. the balances schema marks settlement-advance fields required
# but the live API omits them), the models accept both.

LIVE_SUBACCOUNT_BALANCES = {
    "subaccount_balances": [
        {"balance": "64876.8883", "exchange_index": 0,
         "subaccount_number": 0, "updated_ts": 1784701854},
        {"balance": "0.0000", "exchange_index": 0,
         "subaccount_number": 1, "updated_ts": 1785052854},
    ]
}


def test_create_subaccount_parses_live_response(client, mock_response):
    """Live 201 body is exactly {"subaccount_number": N} -- no wrapper, no id."""
    client._session.request.return_value = mock_response({"subaccount_number": 1})

    sub = client.portfolio.create_subaccount()

    assert sub.subaccount_number == 1
    call_args = client._session.request.call_args
    assert call_args.args[0] == "POST"
    assert call_args.args[1].endswith("/portfolio/subaccounts")
    assert json.loads(call_args.kwargs["content"]) == {}


def test_create_subaccount_sends_exchange_index(client, mock_response):
    client._session.request.return_value = mock_response({"subaccount_number": 2})

    client.portfolio.create_subaccount(exchange_index=0)

    body = json.loads(client._session.request.call_args.kwargs["content"])
    assert body == {"exchange_index": 0}


def test_get_subaccount_balances_reads_live_key(client, mock_response):
    """The response key is `subaccount_balances`, not `balances`."""
    client._session.request.return_value = mock_response(LIVE_SUBACCOUNT_BALANCES)

    balances = client.portfolio.get_subaccount_balances()

    assert len(balances) == 2
    assert balances[0].subaccount_number == 0
    assert balances[0].balance == "64876.8883"
    assert balances[0].exchange_index == 0
    assert balances[0].updated_ts == 1784701854
    assert balances[1].subaccount_number == 1
    assert balances[1].balance == "0.0000"

    call_url = client._session.request.call_args.args[1]
    assert call_url.endswith("/portfolio/subaccounts/balances")


def test_get_subaccount_balances_accepts_settlement_advance_fields(client, mock_response):
    """Docs mark these required; live omits them. Accept both."""
    client._session.request.return_value = mock_response({
        "subaccount_balances": [
            {"balance": "10.0000", "exchange_index": 0, "subaccount_number": 3,
             "updated_ts": 1784701854, "voluntarily_locked": True,
             "settlement_advance": "0.0000",
             "settlement_advance_state": "b2f9cb52-8ef5-4d37-a389-4d97cbf8ac09"},
        ]
    })

    balances = client.portfolio.get_subaccount_balances()

    assert balances[0].voluntarily_locked is True
    assert balances[0].settlement_advance == "0.0000"


def test_transfer_between_subaccounts_sends_documented_schema(client, mock_response):
    """ApplySubaccountTransferRequest: client_transfer_id + int subaccount
    numbers + amount_cents. The old {from,to}_subaccount_id / amount_dollars
    body never matched the live API."""
    client._session.request.return_value = mock_response({})

    transfer_id = client.portfolio.transfer_between_subaccounts(
        0, 1, 2500,
        client_transfer_id="5f8f9c1e-2f9b-4f1a-9d0e-8f7a6b5c4d3e",
    )

    assert transfer_id == "5f8f9c1e-2f9b-4f1a-9d0e-8f7a6b5c4d3e"
    call_args = client._session.request.call_args
    assert call_args.args[0] == "POST"
    assert call_args.args[1].endswith("/portfolio/subaccounts/transfer")
    body = json.loads(call_args.kwargs["content"])
    assert body == {
        "client_transfer_id": "5f8f9c1e-2f9b-4f1a-9d0e-8f7a6b5c4d3e",
        "from_subaccount": 0,
        "to_subaccount": 1,
        "amount_cents": 2500,
    }
    assert isinstance(body["from_subaccount"], int)
    assert isinstance(body["amount_cents"], int)


def test_transfer_between_subaccounts_generates_uuid(client, mock_response):
    """Without an explicit client_transfer_id a fresh UUID4 is generated and
    returned so callers can retry idempotently (retry -> HTTP 409)."""
    import uuid as _uuid

    client._session.request.return_value = mock_response({})

    transfer_id = client.portfolio.transfer_between_subaccounts(1, 0, 100)

    body = json.loads(client._session.request.call_args.kwargs["content"])
    assert body["client_transfer_id"] == transfer_id
    assert _uuid.UUID(transfer_id).version == 4


def test_transfer_between_subaccounts_sends_exchange_index(client, mock_response):
    client._session.request.return_value = mock_response({})

    client.portfolio.transfer_between_subaccounts(0, 1, 100, exchange_index=0)

    body = json.loads(client._session.request.call_args.kwargs["content"])
    assert body["exchange_index"] == 0


def test_get_subaccount_transfers_parses_documented_shape(client, mock_response):
    """SubaccountTransfer: int subaccount numbers, amount_cents, created_ts."""
    client._session.request.return_value = mock_response({
        "transfers": [
            {"transfer_id": "t-1", "from_subaccount": 0, "to_subaccount": 1,
             "amount_cents": 2500, "created_ts": 1785052854, "exchange_index": 0},
        ],
        "cursor": "",
    })

    transfers = client.portfolio.get_subaccount_transfers()

    assert len(transfers) == 1
    t = transfers[0]
    assert t.transfer_id == "t-1"
    assert t.from_subaccount == 0
    assert t.to_subaccount == 1
    assert t.amount_cents == 2500
    assert t.created_ts == 1785052854

    call_url = client._session.request.call_args.args[1]
    assert "/portfolio/subaccounts/transfers" in call_url


def test_get_subaccount_netting(client, mock_response):
    client._session.request.return_value = mock_response({
        "netting_configs": [
            {"subaccount_number": 0, "enabled": True, "exchange_index": 0},
            {"subaccount_number": 1, "enabled": False, "exchange_index": 0},
        ]
    })

    configs = client.portfolio.get_subaccount_netting()

    assert len(configs) == 2
    assert configs[0].subaccount_number == 0
    assert configs[0].enabled is True
    assert configs[1].enabled is False

    call_url = client._session.request.call_args.args[1]
    assert call_url.endswith("/portfolio/subaccounts/netting")


def test_update_subaccount_netting(client, mock_response):
    client._session.request.return_value = mock_response({})

    client.portfolio.update_subaccount_netting(1, True)

    call_args = client._session.request.call_args
    assert call_args.args[0] == "PUT"
    assert call_args.args[1].endswith("/portfolio/subaccounts/netting")
    assert json.loads(call_args.kwargs["content"]) == {
        "subaccount_number": 1, "enabled": True,
    }


def test_amend_order_subaccount_is_query_param(client, mock_response):
    """AmendOrderV2 takes subaccount as a query parameter; the request body
    schema has no subaccount field."""
    client._session.request.return_value = mock_response(_create_ack())

    client.portfolio.amend_order(
        "order-abc-123", ticker="KXTEST", book_side="bid",
        count_fp="10.00", yes_price_dollars="0.55", subaccount=2,
    )

    call_args = client._session.request.call_args
    assert "/portfolio/events/orders/order-abc-123/amend?subaccount=2" in call_args.args[1]
    body = json.loads(call_args.kwargs["content"])
    assert "subaccount" not in body


def test_decrease_order_subaccount_is_query_param(client, mock_response):
    client._session.request.return_value = mock_response(_create_ack())

    client.portfolio.decrease_order("order-abc-123", "5.00", subaccount=3)

    call_args = client._session.request.call_args
    assert "/portfolio/events/orders/order-abc-123/decrease?subaccount=3" in call_args.args[1]
    body = json.loads(call_args.kwargs["content"])
    assert body == {"reduce_by": "5.00"}
