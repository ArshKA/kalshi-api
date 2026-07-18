"""Tests for portfolio functionality: positions, fills, and order retrieval."""

from decimal import Decimal

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
        "https://demo-api.kalshi.co/trade-api/v2/portfolio/positions?limit=100",
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
        "https://demo-api.kalshi.co/trade-api/v2/portfolio/fills?limit=100",
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
        "https://demo-api.kalshi.co/trade-api/v2/portfolio/events/orders/order-abc-123",
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
    client._session.request.return_value = mock_response(
        {
            "order": {
                "order_id": "order-abc-123",
                "ticker": "KXTEST",
                "action": "buy",
                "side": "yes",
                "initial_count_fp": "10.00",
                "yes_price_dollars": "0.55",
                "status": "canceled",
                "type": "limit",
            }
        }
    )

    order = client.portfolio.cancel_order("order-abc-123")

    assert order.order_id == "order-abc-123"
    assert order.status == OrderStatus.CANCELED

    # Verify DELETE request
    client._session.request.assert_called_with(
        "DELETE",
        "https://demo-api.kalshi.co/trade-api/v2/portfolio/events/orders/order-abc-123",
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
        {
            "order": {
                "order_id": "order-abc-123",
                "ticker": "KXTEST",
                "status": "canceled",
            }
        }
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
        yes_price_dollars="0.50",
    )
    order = Order(client, initial_model)

    client._session.request.return_value = mock_response(
        {
            "order": {
                "order_id": "order-abc-123",
                "ticker": "KXTEST",
                "status": "resting",
                "yes_price_dollars": "0.55",
            }
        }
    )

    result = order.amend(yes_price_dollars="0.55")

    assert result is order
    assert order.yes_price_dollars == "0.55"

    # Verify POST to amend endpoint
    call_args = client._session.request.call_args
    assert call_args.args[0] == "POST"
    assert "/portfolio/events/orders/order-abc-123/amend" in call_args.args[1]


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

    client._session.request.return_value = mock_response(
        {
            "order": {
                "order_id": "order-abc-123",
                "ticker": "KXTEST",
                "status": "resting",
                "remaining_count_fp": "7.00",
            }
        }
    )

    result = order.decrease(reduce_by_fp="3.00")

    assert result is order
    assert order.remaining_count_fp == "7.00"

    # Verify POST to decrease endpoint
    call_args = client._session.request.call_args
    assert call_args.args[0] == "POST"
    assert "/portfolio/events/orders/order-abc-123/decrease" in call_args.args[1]


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
        "https://demo-api.kalshi.co/trade-api/v2/portfolio/events/orders/order-abc-123",
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
