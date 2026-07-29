import pytest
from decimal import Decimal
from pykalshi.models import (
    BalanceModel,
    OrderModel,
    MarketModel,
    PriceRange,
    FillModel,
    ExchangeStatus,
    APILimits,
    RateBucket,
    Grant,
    RateLimitTier,
    APIKey,
    GeneratedAPIKey,
    SeriesModel,
    TradeModel,
)
from pykalshi.enums import Action, Side, OrderStatus


def test_balance_model_validation():
    data = {"balance": 1000, "portfolio_value": 2000}
    model = BalanceModel.model_validate(data)
    assert model.balance == 1000
    assert model.portfolio_value == 2000


def test_order_model_parsing():
    data = {
        "order_id": "123",
        "ticker": "TEST",
        "action": "buy",
        "side": "yes",
        "initial_count_fp": "10.00",
        "yes_price_dollars": "0.50",
        "status": "resting",
        "created_time": "2023-01-01T00:00:00Z",
    }
    model = OrderModel.model_validate(data)
    # Check enum conversion
    assert model.action == Action.BUY
    assert model.side == Side.YES
    assert model.status == OrderStatus.RESTING


def test_market_model_validation():
    data = {
        "ticker": "TEST-1",
        "title": "Will it rain?",
        "status": "open",
        "yes_bid_dollars": "0.10",
        "yes_ask_dollars": "0.12",
        "expiration_time": "2023-12-31T23:59:59Z",
    }
    model = MarketModel.model_validate(data)
    assert model.ticker == "TEST-1"
    assert model.yes_bid_dollars == "0.10"


def test_market_model_price_ranges():
    """MarketModel carries price_ranges — Kalshi's canonical tick definition
    (required on the Market schema since the Jul 23 2026 changelog)."""
    data = {
        "ticker": "TEST-1",
        "status": "open",
        "price_level_structure": "center_half_edge_quint_cent",
        "price_ranges": [
            {"start": "0.002", "end": "0.10", "step": "0.002"},
            {"start": "0.10", "end": "0.90", "step": "0.005"},
            {"start": "0.90", "end": "0.998", "step": "0.002"},
        ],
    }
    model = MarketModel.model_validate(data)
    assert model.price_level_structure == "center_half_edge_quint_cent"
    assert len(model.price_ranges) == 3
    band = model.price_ranges[1]
    assert isinstance(band, PriceRange)
    assert (band.start, band.end, band.step) == ("0.10", "0.90", "0.005")
    # Decimal-safe accessors for tick arithmetic.
    assert band.step_decimal == Decimal("0.005")
    assert band.start_decimal == Decimal("0.10")
    assert band.end_decimal == Decimal("0.90")


def test_market_model_price_ranges_absent():
    """Older payloads without price_ranges still validate (field is None)."""
    model = MarketModel.model_validate({"ticker": "TEST-1", "status": "open"})
    assert model.price_ranges is None


def test_price_range_exported_at_top_level():
    import pykalshi

    assert pykalshi.PriceRange is PriceRange
    assert "PriceRange" in pykalshi.__all__


def test_invalid_data_raises_error():
    with pytest.raises(ValueError):
        BalanceModel.model_validate({"not_a_field": 0})


def test_fill_model_fee_cost_is_dollar_string():
    """Verify fee_cost_dollars is kept as dollar amount string."""
    data = {
        "trade_id": "t1",
        "ticker": "TEST",
        "order_id": "o1",
        "side": "yes",
        "action": "buy",
        "count_fp": "1.00",
        "yes_price_fixed": "0.50",
        "no_price_fixed": "0.50",
        "fee_cost": "0.3200",
    }
    model = FillModel.model_validate(data)
    assert model.fee_cost_dollars == "0.3200"
    assert isinstance(model.fee_cost_dollars, str)


# --- Exchange Models ---

def test_exchange_status_model():
    """Test ExchangeStatus model validation."""
    data = {"exchange_active": True, "trading_active": False}
    model = ExchangeStatus.model_validate(data)
    assert model.exchange_active is True
    assert model.trading_active is False


def test_rate_limit_tier_model():
    """Test RateLimitTier model validation."""
    data = {"max_requests": 100, "period_seconds": 60}
    model = RateLimitTier.model_validate(data)
    assert model.max_requests == 100
    assert model.period_seconds == 60


# Live-verified /account/limits payload (captured 2026-07-26 from production).
API_LIMITS_WIRE = {
    "usage_tier": "basic",
    "read": {"refill_rate": 200, "bucket_capacity": 400},
    "write": {"refill_rate": 100, "bucket_capacity": 100},
    "grants": [
        {"exchange_instance": "event_contract", "level": "advanced", "source": "manual"},
    ],
}


def test_api_limits_model():
    """Test APILimits against the live-verified nested wire shape."""
    model = APILimits.model_validate(API_LIMITS_WIRE)
    assert model.usage_tier == "basic"
    assert model.read.refill_rate == 200
    assert model.read.bucket_capacity == 400
    assert model.write.refill_rate == 100
    assert model.write.bucket_capacity == 100
    assert len(model.grants) == 1
    grant = model.grants[0]
    assert grant.exchange_instance == "event_contract"
    assert grant.level == "advanced"
    assert grant.source == "manual"
    assert grant.expires_ts is None  # no expires_ts => permanent grant


def test_api_limits_model_no_grants():
    """Test APILimits tolerates a missing grants array."""
    data = {k: v for k, v in API_LIMITS_WIRE.items() if k != "grants"}
    model = APILimits.model_validate(data)
    assert model.grants == []


def test_api_limits_grant_with_expiry():
    """Test Grant parses an expiring grant."""
    grant = Grant.model_validate({
        "exchange_instance": "event_contract",
        "level": "expert",
        "source": "volume",
        "expires_ts": 1782518400,
    })
    assert grant.expires_ts == 1782518400


def test_rate_bucket_model():
    """Test RateBucket model validation."""
    bucket = RateBucket.model_validate({"refill_rate": 30, "bucket_capacity": 60})
    assert bucket.refill_rate == 30
    assert bucket.bucket_capacity == 60


def test_api_limits_deprecated_flat_properties():
    """read_limit/write_limit still work but warn and mirror refill_rate."""
    model = APILimits.model_validate(API_LIMITS_WIRE)
    with pytest.warns(DeprecationWarning):
        assert model.read_limit == 200
    with pytest.warns(DeprecationWarning):
        assert model.write_limit == 100


# --- API Key Models ---

def test_api_key_model():
    """Test APIKey model validation."""
    data = {
        "id": "key-001",
        "name": "Trading Bot",
        "created_time": "2024-01-01T00:00:00Z",
        "last_used": "2024-01-15T12:00:00Z",
        "scopes": ["read", "trade"],
    }
    model = APIKey.model_validate(data)
    assert model.id == "key-001"
    assert model.name == "Trading Bot"
    assert model.scopes == ["read", "trade"]


def test_api_key_model_minimal():
    """Test APIKey with only required fields."""
    data = {"id": "key-002"}
    model = APIKey.model_validate(data)
    assert model.id == "key-002"
    assert model.name is None
    assert model.scopes is None


def test_generated_api_key_model():
    """Test GeneratedAPIKey model validation."""
    data = {
        "id": "gen-001",
        "private_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIE...",
        "name": "Generated Key",
    }
    model = GeneratedAPIKey.model_validate(data)
    assert model.id == "gen-001"
    assert "PRIVATE KEY" in model.private_key
    assert model.name == "Generated Key"


# --- Series & Trade Models ---

def test_series_model():
    """Test SeriesModel validation."""
    data = {
        "ticker": "INXD",
        "title": "S&P 500 Daily",
        "category": "economics",
        "tags": ["stocks", "daily"],
        "frequency": "daily",
        "settlement_timer_seconds": 3600,
    }
    model = SeriesModel.model_validate(data)
    assert model.ticker == "INXD"
    assert model.title == "S&P 500 Daily"
    assert model.category == "economics"
    assert model.tags == ["stocks", "daily"]
    assert model.frequency == "daily"


def test_series_model_minimal():
    """Test SeriesModel with only required fields."""
    data = {"ticker": "TEST"}
    model = SeriesModel.model_validate(data)
    assert model.ticker == "TEST"
    assert model.title is None
    assert model.tags is None


def test_trade_model():
    """Test TradeModel validation."""
    data = {
        "trade_id": "t-001",
        "ticker": "KXTEST",
        "count_fp": "10.00",
        "yes_price_dollars": "0.55",
        "no_price_dollars": "0.45",
        "taker_side": "yes",
        "created_time": "2024-01-01T12:00:00Z",
        "ts": 1704067200,
    }
    model = TradeModel.model_validate(data)
    assert model.trade_id == "t-001"
    assert model.ticker == "KXTEST"
    assert model.count_fp == "10.00"
    assert model.yes_price_dollars == "0.55"
    assert model.no_price_dollars == "0.45"
    assert model.taker_side == "yes"


def test_trade_model_minimal():
    """Test TradeModel with only required fields."""
    data = {
        "trade_id": "t-002",
        "ticker": "TEST",
        "count_fp": "1.00",
        "yes_price_dollars": "0.50",
        "no_price_dollars": "0.50",
    }
    model = TradeModel.model_validate(data)
    assert model.trade_id == "t-002"
    assert model.taker_side is None
    assert model.ts is None


# --- Extra Fields Handling ---

def test_models_ignore_extra_fields():
    """Verify all new models ignore extra fields for forward compatibility."""
    # ExchangeStatus
    es = ExchangeStatus.model_validate({
        "exchange_active": True,
        "trading_active": True,
        "future_field": "ignored",
    })
    assert not hasattr(es, "future_field")

    # APIKey
    ak = APIKey.model_validate({
        "id": "key",
        "unknown_field": "ignored",
    })
    assert not hasattr(ak, "unknown_field")

    # SeriesModel
    sm = SeriesModel.model_validate({
        "ticker": "TEST",
        "new_api_field": "ignored",
    })
    assert not hasattr(sm, "new_api_field")

    # TradeModel
    tm = TradeModel.model_validate({
        "trade_id": "t",
        "ticker": "X",
        "count_fp": "1.00",
        "yes_price_dollars": "0.50",
        "no_price_dollars": "0.50",
        "extra": "ignored",
    })
    assert not hasattr(tm, "extra")
