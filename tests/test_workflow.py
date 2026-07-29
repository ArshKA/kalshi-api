import pytest
import json
from decimal import Decimal
from unittest.mock import ANY, AsyncMock, MagicMock
from pykalshi import AsyncKalshiClient
from pykalshi.enums import Action, Side, OrderStatus
from pykalshi.models import PriceRange
from pykalshi.portfolio import Portfolio, AsyncPortfolio


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
        "https://external-api.demo.kalshi.co/trade-api/v2/portfolio/balance",
        headers=ANY,
        timeout=ANY,
    )


def test_place_order_workflow(client, mock_response, mocker):
    """Test placing an order via Portfolio object."""
    # CreateOrderV2Response is a thin ack, not a full order object.
    client._session.request.return_value = mock_response(
        {
            "order_id": "bfs-123",
            "fill_count": "0.00",
            "remaining_count": "5.00",
            "ts_ms": 1715793600123,
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
    assert body["side"] == "bid"
    assert body["count"] == "5.00"
    assert body["price"] == "0.5000"


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
        assert data["price"] == "0.4510"


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
        assert data["count"] == "5.50"


# center_half_edge_quint_cent per the Jul 23 2026 changelog: edge bands
# $0.00-$0.10 / $0.90-$1.00 at 0.2c, center band $0.10-$0.90 at 0.5c.
CENTER_HALF_EDGE_QUINT = [
    {"start": "0.002", "end": "0.10", "step": "0.002"},
    {"start": "0.10", "end": "0.90", "step": "0.005"},
    {"start": "0.90", "end": "0.998", "step": "0.002"},
]

# The legacy tapered_deci_cent grid expressed as ranges.
TAPERED_RANGES = [
    {"start": "0.001", "end": "0.10", "step": "0.001"},
    {"start": "0.10", "end": "0.90", "step": "0.01"},
    {"start": "0.90", "end": "0.999", "step": "0.001"},
]

MARKET_WITH_RANGES = {
    "ticker": "KXTEST",
    "status": "open",
    "price_level_structure": "center_half_edge_quint_cent",
    "price_ranges": CENTER_HALF_EDGE_QUINT,
}

# Pre-rollout payload: label only, no ranges — the legacy fallback path.
MARKET_WITHOUT_RANGES = {
    "ticker": "KXTEST",
    "status": "open",
    "price_level_structure": "linear_cent",
}


@pytest.mark.parametrize("impl", [Portfolio, AsyncPortfolio], ids=["sync", "async"])
class TestPriceRangesValidation:
    """price_ranges is the canonical tick definition (Jul 23 2026 changelog);
    when present it takes precedence over the price_level_structure label."""

    def test_center_band_on_tick(self, impl):
        impl._validate_price_ranges(Decimal("0.455"), CENTER_HALF_EDGE_QUINT)

    def test_center_band_off_tick(self, impl):
        with pytest.raises(ValueError, match="not on a valid tick"):
            impl._validate_price_ranges(Decimal("0.4525"), CENTER_HALF_EDGE_QUINT)

    def test_edge_band_on_tick(self, impl):
        impl._validate_price_ranges(Decimal("0.004"), CENTER_HALF_EDGE_QUINT)
        impl._validate_price_ranges(Decimal("0.996"), CENTER_HALF_EDGE_QUINT)

    def test_edge_band_off_tick(self, impl):
        with pytest.raises(ValueError, match="not on a valid tick"):
            impl._validate_price_ranges(Decimal("0.003"), CENTER_HALF_EDGE_QUINT)

    def test_band_boundaries_inclusive(self, impl):
        for p in ("0.002", "0.10", "0.90", "0.998"):
            impl._validate_price_ranges(Decimal(p), CENTER_HALF_EDGE_QUINT)

    def test_below_all_bands_rejected(self, impl):
        with pytest.raises(ValueError, match="outside"):
            impl._validate_price_ranges(Decimal("0.001"), CENTER_HALF_EDGE_QUINT)

    def test_above_all_bands_rejected(self, impl):
        with pytest.raises(ValueError, match="outside"):
            impl._validate_price_ranges(Decimal("0.999"), CENTER_HALF_EDGE_QUINT)

    def test_accepts_pricerange_models(self, impl):
        """PriceRange models (as carried by MarketModel) validate identically
        to raw dicts (as carried by WS market_lifecycle_v2 frames)."""
        bands = [PriceRange(**r) for r in CENTER_HALF_EDGE_QUINT]
        impl._validate_price_ranges(Decimal("0.455"), bands)
        with pytest.raises(ValueError, match="not on a valid tick"):
            impl._validate_price_ranges(Decimal("0.4525"), bands)

    def test_no_float_drift(self, impl):
        """Decimal arithmetic: prices that float math would misjudge pass."""
        # 0.1 + 3*0.005 is not exactly 0.115 in binary floats.
        impl._validate_price_ranges(Decimal("0.115"), CENTER_HALF_EDGE_QUINT)
        impl._validate_price_ranges(
            Decimal("0.29"), [{"start": "0.01", "end": "0.99", "step": "0.07"}]
        )

    def test_zero_start_edge_band(self, impl):
        """Bands may start at $0.00 (the changelog describes edge bands as
        $0.00-$0.10 / $0.90-$1.00); the grid anchors on start either way."""
        bands = [
            {"start": "0.00", "end": "0.10", "step": "0.001"},
            {"start": "0.10", "end": "0.90", "step": "0.01"},
            {"start": "0.90", "end": "1.00", "step": "0.001"},
        ]
        impl._validate_price_ranges(Decimal("0.001"), bands)
        impl._validate_price_ranges(Decimal("1.00"), bands)
        with pytest.raises(ValueError, match="not on a valid tick"):
            impl._validate_price_ranges(Decimal("0.0015"), bands)

    @pytest.mark.parametrize(
        "center,edge",
        [
            ("0.01", "0.005"),    # center_whole_edge_half_cent
            ("0.01", "0.002"),    # center_whole_edge_quint_cent
            ("0.005", "0.005"),   # center_half_edge_half_cent
            ("0.005", "0.002"),   # center_half_edge_quint_cent
            ("0.005", "0.001"),   # center_half_edge_deci_cent
            ("0.002", "0.002"),   # center_quint_edge_quint_cent
            ("0.002", "0.001"),   # center_quint_edge_deci_cent
        ],
    )
    def test_all_seven_new_structures(self, impl, center, edge):
        """Every new center_{c}_edge_{e}_cent grid validates through ranges —
        the label switch knows none of them."""
        c, e = Decimal(center), Decimal(edge)
        bands = [
            {"start": edge, "end": "0.10", "step": edge},
            {"start": "0.10", "end": "0.90", "step": center},
            {"start": "0.90", "end": str(Decimal("1.00") - e), "step": edge},
        ]
        # On-grid prices in each band.
        impl._validate_price_ranges(e * 3, bands)
        impl._validate_price_ranges(Decimal("0.10") + c * 7, bands)
        impl._validate_price_ranges(Decimal("0.90") + e * 4, bands)
        # Half a tick off the center grid is rejected.
        with pytest.raises(ValueError, match="not on a valid tick"):
            impl._validate_price_ranges(Decimal("0.10") + c * 7 + c / 2, bands)

    def test_malformed_band_raises_clear_error(self, impl):
        with pytest.raises(ValueError, match="Malformed price range"):
            impl._validate_price_ranges(
                Decimal("0.50"), [{"start": "0.01", "end": "0.99", "step": None}]
            )

    def test_malformed_band_missing_key_raises_clear_error(self, impl):
        """A band object missing a field errors clearly rather than blowing up
        with AttributeError/KeyError somewhere deeper."""
        with pytest.raises(ValueError, match="Malformed price range"):
            impl._validate_price_ranges(Decimal("0.50"), [{"start": "0.01"}])
        with pytest.raises(ValueError, match="Malformed price range"):
            impl._validate_price_ranges(Decimal("0.50"), ["not-a-band"])

    def test_legacy_labels_unchanged(self, impl):
        """The three original labels behave exactly as before, on both impls.

        price_ranges only ever adds a path; it must not perturb the label
        switch that markets still use until they are migrated.
        """
        for label, ok, bad in (
            ("linear_cent", ("0.50", "0.01", "1.00"), ("0.505", "0.001")),
            ("deci_cent", ("0.501", "0.001", "0.01"), ("0.5005",)),
            # tapered: $0.001 at/outside the 0.10 & 0.90 edges, $0.01 between.
            ("tapered_deci_cent", ("0.051", "0.100", "0.901", "0.999", "0.50"),
             ("0.501", "0.101", "0.899")),
        ):
            for p in ok:
                impl._validate_tick_size(Decimal(p), label)
            for p in bad:
                with pytest.raises(ValueError, match=label):
                    impl._validate_tick_size(Decimal(p), label)
        # Unknown labels are still unvalidated by the label switch.
        impl._validate_tick_size(Decimal("0.4525"), "center_half_edge_quint_cent")

    def test_legacy_grid_via_ranges_matches_label(self, impl):
        """The tapered_deci_cent grid gives the same verdicts through ranges."""
        for p in ("0.051", "0.45", "0.951"):
            impl._validate_price_ranges(Decimal(p), TAPERED_RANGES)
            impl._validate_tick_size(Decimal(p), "tapered_deci_cent")
        with pytest.raises(ValueError):
            impl._validate_price_ranges(Decimal("0.451"), TAPERED_RANGES)
        with pytest.raises(ValueError):
            impl._validate_tick_size(Decimal("0.451"), "tapered_deci_cent")

    def test_build_order_ranges_take_precedence_over_label(self, impl):
        """A price the label would reject passes when ranges allow it."""
        data = impl._build_order_data(
            "TICK",
            Action.BUY,
            Side.YES,
            "1",
            yes_price_dollars="0.455",  # off-grid for linear_cent
            price_level_structure="linear_cent",
            price_ranges=CENTER_HALF_EDGE_QUINT,
        )
        assert data["price"] == "0.4550"

    def test_build_order_ranges_reject_off_tick(self, impl):
        with pytest.raises(ValueError, match="not on a valid tick"):
            impl._build_order_data(
                "TICK",
                Action.BUY,
                Side.YES,
                "1",
                yes_price_dollars="0.4525",
                price_ranges=CENTER_HALF_EDGE_QUINT,
            )

    def test_build_order_ranges_reject_out_of_range(self, impl):
        with pytest.raises(ValueError, match="outside"):
            impl._build_order_data(
                "TICK",
                Action.BUY,
                Side.YES,
                "1",
                yes_price_dollars="0.999",
                price_ranges=CENTER_HALF_EDGE_QUINT,
            )

    def test_build_order_no_price_validates_yes_leg(self, impl):
        """no_price_dollars converts to the YES leg before range validation."""
        with pytest.raises(ValueError, match="not on a valid tick"):
            impl._build_order_data(
                "TICK",
                Action.BUY,
                Side.NO,
                "1",
                no_price_dollars="0.5475",  # yes = 0.4525, off the 0.005 grid
                price_ranges=CENTER_HALF_EDGE_QUINT,
            )

    def test_build_order_absent_ranges_falls_back_to_label(self, impl):
        """None or empty ranges fall back to the legacy label logic."""
        for absent in (None, []):
            with pytest.raises(ValueError, match="linear_cent"):
                impl._build_order_data(
                    "TICK",
                    Action.BUY,
                    Side.YES,
                    "1",
                    yes_price_dollars="0.451",
                    price_level_structure="linear_cent",
                    price_ranges=absent,
                )

    def test_build_order_unknown_label_without_ranges_unvalidated(self, impl):
        """Unknown labels without ranges still validate nothing (unchanged)."""
        data = impl._build_order_data(
            "TICK",
            Action.BUY,
            Side.YES,
            "1",
            yes_price_dollars="0.4525",
            price_level_structure="center_half_edge_quint_cent",
        )
        assert data["price"] == "0.4525"

    def test_build_order_non_list_ranges_ignored(self, impl):
        """Only a real sequence of bands engages range validation.

        Duck-typed market objects (a MagicMock in a caller's test suite, a
        stub with a sentinel attribute) hand back something truthy that is
        not a band list; that must not fail every price against zero bands.
        """
        for junk in (MagicMock(), object(), "0.10", 1):
            data = impl._build_order_data(
                "TICK",
                Action.BUY,
                Side.YES,
                "1",
                yes_price_dollars="0.50",
                price_ranges=junk,
            )
            assert data["price"] == "0.5000"


def test_place_order_validates_against_market_price_ranges(client, mock_response):
    """place_order with a Market object rejects off-tick prices client-side
    using the market's price_ranges, before any order request is sent."""
    client._session.request.return_value = mock_response({"market": MARKET_WITH_RANGES})
    market = client.get_market("KXTEST")
    assert client._session.request.call_count == 1

    with pytest.raises(ValueError, match="not on a valid tick"):
        client.portfolio.place_order(
            market,
            action=Action.BUY,
            side=Side.YES,
            count_fp="5.00",
            yes_price_dollars="0.4525",
        )
    # No order request was made; only the market fetch happened.
    assert client._session.request.call_count == 1


def test_place_order_accepts_on_tick_price_from_ranges(client, mock_response):
    """On-tick prices on a new structure pass validation and reach the API."""
    client._session.request.side_effect = [
        mock_response({"market": MARKET_WITH_RANGES}),
        mock_response(
            {"order_id": "ord-1", "fill_count": "0.00", "remaining_count": "5.00"}
        ),
    ]
    market = client.get_market("KXTEST")

    order = client.portfolio.place_order(
        market,
        action=Action.BUY,
        side=Side.YES,
        count_fp="5.00",
        yes_price_dollars="0.455",
    )
    assert order.status == OrderStatus.RESTING
    body = json.loads(client._session.request.call_args.kwargs["content"])
    assert body["price"] == "0.4550"


def test_place_order_without_ranges_falls_back_to_label(client, mock_response):
    """A market that has not yet been migrated (label, no price_ranges) keeps
    the legacy label validation."""
    client._session.request.return_value = mock_response(
        {"market": MARKET_WITHOUT_RANGES}
    )
    market = client.get_market("KXTEST")
    assert market.price_ranges is None

    with pytest.raises(ValueError, match="linear_cent"):
        client.portfolio.place_order(
            market,
            action=Action.BUY,
            side=Side.YES,
            count_fp="5.00",
            yes_price_dollars="0.505",
        )
    assert client._session.request.call_count == 1


# --- Async parity: the same three place_order paths on AsyncPortfolio ---


@pytest.fixture
def async_client(mocker):
    """AsyncKalshiClient with mocked auth and HTTP session."""
    mocker.patch("pykalshi._base._BaseKalshiClient._load_private_key")
    mocker.patch(
        "pykalshi._base._BaseKalshiClient._sign_request",
        return_value=("1234567890", "fake_sig"),
    )
    mocker.patch("httpx.AsyncClient")
    c = AsyncKalshiClient(api_key_id="fake_key", private_key_path="fake_path", demo=True)
    c._session.request = AsyncMock()
    return c


async def test_async_place_order_validates_against_market_price_ranges(
    async_client, mock_response
):
    """AsyncPortfolio rejects off-tick prices before sending the order."""
    async_client._session.request.return_value = mock_response(
        {"market": MARKET_WITH_RANGES}
    )
    market = await async_client.get_market("KXTEST")
    assert async_client._session.request.call_count == 1

    with pytest.raises(ValueError, match="not on a valid tick"):
        await async_client.portfolio.place_order(
            market,
            action=Action.BUY,
            side=Side.YES,
            count_fp="5.00",
            yes_price_dollars="0.4525",
        )
    assert async_client._session.request.call_count == 1


async def test_async_place_order_accepts_on_tick_price_from_ranges(
    async_client, mock_response
):
    """On-tick prices on a new structure reach the API on the async path too."""
    async_client._session.request.side_effect = [
        mock_response({"market": MARKET_WITH_RANGES}),
        mock_response(
            {"order_id": "ord-1", "fill_count": "0.00", "remaining_count": "5.00"}
        ),
    ]
    market = await async_client.get_market("KXTEST")

    order = await async_client.portfolio.place_order(
        market,
        action=Action.BUY,
        side=Side.YES,
        count_fp="5.00",
        yes_price_dollars="0.455",
    )
    assert order.status == OrderStatus.RESTING
    body = json.loads(async_client._session.request.call_args.kwargs["content"])
    assert body["price"] == "0.4550"


async def test_async_place_order_without_ranges_falls_back_to_label(
    async_client, mock_response
):
    """Absent price_ranges, the async path keeps the legacy label validation."""
    async_client._session.request.return_value = mock_response(
        {"market": MARKET_WITHOUT_RANGES}
    )
    market = await async_client.get_market("KXTEST")
    assert market.price_ranges is None

    with pytest.raises(ValueError, match="linear_cent"):
        await async_client.portfolio.place_order(
            market,
            action=Action.BUY,
            side=Side.YES,
            count_fp="5.00",
            yes_price_dollars="0.505",
        )
    assert async_client._session.request.call_count == 1
