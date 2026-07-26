import pytest
from pykalshi.models import (
    BalanceModel,
    OrderModel,
    MarketModel,
    FillModel,
    ExchangeStatus,
    APILimits,
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


def test_api_limits_model():
    """Test APILimits model validation."""
    data = {
        "usage_tier": "standard",
        "read_limit": 20,
        "write_limit": 10,
    }
    model = APILimits.model_validate(data)
    assert model.usage_tier == "standard"
    assert model.read_limit == 20
    assert model.write_limit == 10


def test_api_limits_model_minimal():
    """Test APILimits with minimal data."""
    data = {}
    model = APILimits.model_validate(data)
    assert model.usage_tier is None
    assert model.read_limit is None


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
