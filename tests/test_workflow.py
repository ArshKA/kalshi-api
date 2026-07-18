import pytest
import json
from unittest.mock import ANY
from pykalshi.enums import Action, Side, OrderStatus
from pykalshi.portfolio import Portfolio


def test_user_balance_workflow(client, mock_response):
    """Test fetching user balance."""
    client._session.request.return_value = mock_response(
        {"balance": 5000, "portfolio_value": 10000}
    )

    balance = client.portfolio.get_balance()

    # Verify values
    assert balance.balance == 5000
    assert balance.portfolio_value == 10000

    # Verify endpoint called
    client._session.request.assert_called_with(
        "GET",
        "https://demo-api.kalshi.co/trade-api/v2/portfolio/balance",
        headers=ANY,
        timeout=ANY,
    )


def test_place_order_workflow(client, mock_response, mocker):
    """Test placing an order via Portfolio object."""
    client._session.request.return_value = mock_response(
        {
            "order": {
                "order_id": "bfs-123",
                "ticker": "KXTEST",
                "action": "buy",
                "side": "yes",
                "initial_count_fp": "5.00",
                "yes_price_dollars": "0.50",
                "status": "resting",
                "created_time": "2023-01-01T00:00:00Z",
            }
        }
    )

    # Mock Market object (just need ticker)
    market = mocker.MagicMock()
    market.ticker = "KXTEST"

    order = client.portfolio.place_order(
        market, action=Action.BUY, side=Side.YES, count_fp="5.00", yes_price_dollars="0.50"
    )

    # Verify Order object returned
    assert order.order_id == "bfs-123"
    assert order.status == OrderStatus.RESTING

    # Verify correct payload sent
    call_args = client._session.request.call_args
    assert call_args.args[0] == "POST"
    assert "/portfolio/events/orders" in call_args.args[1]
    body = json.loads(call_args.kwargs["content"])
    assert body["ticker"] == "KXTEST"
    assert body["action"] == "buy"
    assert body["side"] == "yes"
    assert body["count_fp"] == "5.00"
    assert body["yes_price_dollars"] == "0.50"


def test_market_orderbook_workflow(client, mock_response):
    """Test fetching orderbook via Market object."""
    client._session.request.side_effect = [
        # Call 1: Market data
        mock_response(
            {
                "market": {
                    "ticker": "KXTEST",
                    "title": "Test Market",
                    "status": "open",
                    "yes_bid_dollars": "0.10",
                    "yes_ask_dollars": "0.12",
                    "expiration_time": "2024-01-01T00:00:00Z",
                }
            }
        ),
        # Call 2: Orderbook data
        mock_response({"orderbook": {"yes_dollars": [["0.10", "50.00"]], "no_dollars": [["0.90", "50.00"]]}}),
    ]

    # 1. Fetch market
    market = client.get_market("KXTEST")

    # 2. Fetch orderbook
    ob = market.get_orderbook()

    # Verify typed OrderbookResponse
    assert ob.orderbook.yes_dollars == [("0.10", "50.00")]
    assert ob.best_yes_bid == "0.10"
    assert client._session.request.call_count == 2

    # Verify URL of second call
    call_args_list = client._session.request.call_args_list
    assert "/markets/KXTEST/orderbook" in call_args_list[1].args[1]


def test_orderbook_response_accepts_orderbook_fp_key(client, mock_response):
    """Test OrderbookResponse accepts 'orderbook_fp' key from API."""
    client._session.request.side_effect = [
        mock_response({"market": {"ticker": "KXTEST", "status": "open"}}),
        mock_response({"orderbook_fp": {"yes_dollars": [["0.50", "10.00"]], "no_dollars": [["0.50", "10.00"]]}}),
    ]

    market = client.get_market("KXTEST")
    ob = market.get_orderbook()

    assert ob.orderbook.yes_dollars == [("0.50", "10.00")]
    assert ob.best_yes_bid == "0.50"


class TestTickSizeValidation:
    """Tests for price_level_structure tick size validation."""

    def test_linear_cent_valid(self):
        """linear_cent accepts $0.01 increments."""
        Portfolio._validate_tick_size(
            __import__("decimal").Decimal("0.45"), "linear_cent"
        )

    def test_linear_cent_invalid(self):
        """linear_cent rejects sub-cent prices."""
        with pytest.raises(ValueError, match="linear_cent"):
            Portfolio._validate_tick_size(
                __import__("decimal").Decimal("0.451"), "linear_cent"
            )

    def test_deci_cent_valid(self):
        """deci_cent accepts $0.001 increments."""
        Portfolio._validate_tick_size(
            __import__("decimal").Decimal("0.451"), "deci_cent"
        )

    def test_deci_cent_invalid(self):
        """deci_cent rejects sub-mill prices."""
        with pytest.raises(ValueError, match="deci_cent"):
            Portfolio._validate_tick_size(
                __import__("decimal").Decimal("0.4511"), "deci_cent"
            )

    def test_tapered_deci_cent_outer_valid(self):
        """tapered_deci_cent outer ranges ($0–$0.10, $0.90–$1.00) accept $0.001."""
        Portfolio._validate_tick_size(
            __import__("decimal").Decimal("0.051"), "tapered_deci_cent"
        )
        Portfolio._validate_tick_size(
            __import__("decimal").Decimal("0.951"), "tapered_deci_cent"
        )

    def test_tapered_deci_cent_inner_valid(self):
        """tapered_deci_cent inner range ($0.10–$0.90) accepts $0.01."""
        Portfolio._validate_tick_size(
            __import__("decimal").Decimal("0.45"), "tapered_deci_cent"
        )

    def test_tapered_deci_cent_inner_invalid(self):
        """tapered_deci_cent inner range rejects $0.001."""
        with pytest.raises(ValueError, match="tapered_deci_cent"):
            Portfolio._validate_tick_size(
                __import__("decimal").Decimal("0.451"), "tapered_deci_cent"
            )

    def test_build_order_with_tick_validation(self):
        """_build_order_data validates tick size when structure provided."""
        with pytest.raises(ValueError, match="linear_cent"):
            Portfolio._build_order_data(
                "TICK",
                Action.BUY,
                Side.YES,
                "1",
                yes_price_dollars="0.451",
                price_level_structure="linear_cent",
            )

    def test_build_order_without_structure_skips_validation(self):
        """_build_order_data skips tick validation when structure is None."""
        data = Portfolio._build_order_data(
            "TICK",
            Action.BUY,
            Side.YES,
            "1",
            yes_price_dollars="0.451",
        )
        assert data["yes_price_dollars"] == "0.451"


class TestFractionalTradingValidation:
    """Tests for fractional_trading_enabled validation."""

    def test_whole_count_passes(self):
        """Whole number count_fp passes when fractional disabled."""
        Portfolio._validate_fractional("5", False)
        Portfolio._validate_fractional("5.00", False)

    def test_fractional_count_rejected(self):
        """Fractional count_fp rejected when fractional disabled."""
        with pytest.raises(ValueError, match="Fractional trading"):
            Portfolio._validate_fractional("5.50", False)

    def test_fractional_count_allowed(self):
        """Fractional count_fp allowed when fractional enabled."""
        Portfolio._validate_fractional("5.50", True)

    def test_build_order_fractional_validation(self):
        """_build_order_data validates fractional when flag provided."""
        with pytest.raises(ValueError, match="Fractional"):
            Portfolio._build_order_data(
                "TICK",
                Action.BUY,
                Side.YES,
                "5.50",
                yes_price_dollars="0.45",
                fractional_trading_enabled=False,
            )

    def test_build_order_fractional_allowed(self):
        """_build_order_data allows fractional when enabled."""
        data = Portfolio._build_order_data(
            "TICK",
            Action.BUY,
            Side.YES,
            "5.50",
            yes_price_dollars="0.45",
            fractional_trading_enabled=True,
        )
        assert data["count_fp"] == "5.50"
