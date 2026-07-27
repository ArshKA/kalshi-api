from __future__ import annotations
from decimal import Decimal
from functools import cached_property
from typing import Annotated
from pydantic import (
    AliasChoices, BaseModel, BeforeValidator, ConfigDict, Field, model_validator,
)
from .enums import (
    OrderStatus, Side, Action, OrderType, MarketStatus, BookSide, OutcomeSide,
)
from ._utils import (
    blank_to_none,
    book_side_from_fill_legacy,
    book_side_from_order_legacy,
    book_side_from_outcome_side,
    outcome_side_from_book_side,
)

# Legacy direction fields may arrive as "" once Kalshi retires them; "" is not
# a valid enum member, so coerce it away before validation.
_LegacySide = Annotated[Side | None, BeforeValidator(blank_to_none)]
_LegacyAction = Annotated[Action | None, BeforeValidator(blank_to_none)]
_OptBookSide = Annotated[BookSide | None, BeforeValidator(blank_to_none)]
_OptOutcomeSide = Annotated[OutcomeSide | None, BeforeValidator(blank_to_none)]


class HistoricalCutoffResponse(BaseModel):
    """Boundary timestamps separating live from historical data."""
    market_settled_ts: str
    trades_created_ts: str
    orders_updated_ts: str

    model_config = ConfigDict(extra="ignore")


class HistoricalBidAsk(BaseModel):
    """OHLC for bid/ask levels in historical candlesticks."""
    open: str | None = None
    high: str | None = None
    low: str | None = None
    close: str | None = None

    model_config = ConfigDict(extra="ignore")


class HistoricalPrice(BaseModel):
    """OHLC + mean/previous for trade prices in historical candlesticks."""
    open: str | None = None
    high: str | None = None
    low: str | None = None
    close: str | None = None
    mean: str | None = None
    previous: str | None = None

    model_config = ConfigDict(extra="ignore")


class HistoricalCandlestick(BaseModel):
    """A single candlestick from the historical candlesticks endpoint."""
    end_period_ts: int
    yes_bid: HistoricalBidAsk | None = None
    yes_ask: HistoricalBidAsk | None = None
    price: HistoricalPrice | None = None
    volume: str | None = None
    open_interest: str | None = None

    model_config = ConfigDict(extra="ignore")


class MveSelectedLeg(BaseModel):
    """A single leg in a multivariate event combo."""
    event_ticker: str
    market_ticker: str
    side: str  # "yes" or "no"
    yes_settlement_value_dollars: str | None = None


    model_config = ConfigDict(extra="ignore")


class MarketModel(BaseModel):
    """Pydantic model for Market data."""

    ticker: str
    event_ticker: str | None = None
    series_ticker: str | None = None
    market_type: str | None = None
    title: str | None = None
    subtitle: str | None = None
    yes_sub_title: str | None = None
    no_sub_title: str | None = None

    # Timing
    open_time: str | None = None
    close_time: str | None = None
    expiration_time: str | None = None
    expected_expiration_time: str | None = None
    latest_expiration_time: str | None = None
    created_time: str | None = None
    updated_time: str | None = None

    # Status & Result
    status: MarketStatus | None = None
    result: str | None = None
    settlement_value_dollars: str | None = None

    # Pricing (dollar strings, e.g. "0.45")
    yes_bid_dollars: str | None = None
    yes_ask_dollars: str | None = None
    no_bid_dollars: str | None = None
    no_ask_dollars: str | None = None
    last_price_dollars: str | None = None
    previous_yes_bid_dollars: str | None = None
    previous_yes_ask_dollars: str | None = None
    previous_price_dollars: str | None = None
    notional_value_dollars: str | None = None

    # Volume & Liquidity (fixed-point strings, e.g. "100.00")
    volume_fp: str | None = None
    volume_24h_fp: str | None = None
    open_interest_fp: str | None = None
    liquidity_dollars: str | None = None
    yes_bid_size_fp: str | None = None
    yes_ask_size_fp: str | None = None

    # Market structure
    tick_size: int | None = None
    price_level_structure: str | None = None
    fractional_trading_enabled: bool | None = None
    strike_type: str | None = None
    floor_strike: float | None = None
    cap_strike: float | None = None
    can_close_early: bool | None = None
    expiration_value: str | None = None
    settlement_timer_seconds: int | None = None
    rules_primary: str | None = None
    rules_secondary: str | None = None

    # Multivariate event (combo) fields
    mve_collection_ticker: str | None = None
    mve_selected_legs: list[MveSelectedLeg] | None = None
    is_provisional: bool | None = None


    model_config = ConfigDict(extra="ignore")


class EventModel(BaseModel):
    """Pydantic model for Event data."""

    event_ticker: str
    series_ticker: str
    title: str | None = None
    sub_title: str | None = None
    category: str | None = None

    # Event properties
    mutually_exclusive: bool = False
    collateral_return_type: str | None = None

    # Timing
    strike_date: str | None = None
    strike_period: str | None = None

    # Availability
    available_on_brokers: bool = False

    model_config = ConfigDict(extra="ignore")


class OrderModel(BaseModel):
    """Pydantic model for Order data."""

    order_id: str
    ticker: str
    status: OrderStatus

    # Canonical direction. Prefer these; see pykalshi.enums.BookSide.
    book_side: _OptBookSide = None
    outcome_side: _OptOutcomeSide = None

    # Deprecated by Kalshi -- read book_side instead. Retained because the
    # server still sends them and callers still read them.
    action: _LegacyAction = None
    side: _LegacySide = None

    type: OrderType | None = None

    # Pricing (dollar strings)
    yes_price_dollars: str | None = None
    no_price_dollars: str | None = None

    # Counts (fixed-point strings)
    initial_count_fp: str | None = None
    fill_count_fp: str | None = None
    remaining_count_fp: str | None = None

    # Fees & costs (dollar strings)
    taker_fees_dollars: str | None = None
    maker_fees_dollars: str | None = None
    taker_fill_cost_dollars: str | None = None
    maker_fill_cost_dollars: str | None = None

    # V2 write-ack only: what the immediate fill actually cost. The read
    # endpoints do not send these; the create/amend ack does, and it is the
    # only place a caller sees the realised price and fee without a separate
    # /portfolio/fills round-trip.
    average_fill_price_dollars: str | None = None
    average_fee_paid_dollars: str | None = None

    # V2 cancel/batch-cancel receipt: contracts actually pulled off the book.
    # A cancel that reduced nothing reports "0.00" rather than erroring.
    reduced_by_fp: str | None = None

    # Metadata
    user_id: str | None = None
    client_order_id: str | None = None
    created_time: str | None = None
    last_update_time: str | None = None
    expiration_time: str | None = None
    subaccount_number: int | None = None
    exchange_index: int | None = None
    self_trade_prevention_type: str | None = None
    order_group_id: str | None = None


    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="after")
    def _fill_canonical_direction(self):
        """Back-fill canonical direction when the server omits it.

        The server supplies book_side/outcome_side today and they win outright.
        This only covers older payloads and hand-built models, and uses the
        ORDER mapping -- correct here, wrong for fills.
        """
        if self.book_side is None and self.outcome_side is not None:
            object.__setattr__(
                self, "book_side",
                BookSide(book_side_from_outcome_side(self.outcome_side)),
            )
        if self.book_side is None:
            derived = book_side_from_order_legacy(self.action, self.side)
            if derived:
                object.__setattr__(self, "book_side", BookSide(derived))
        if self.outcome_side is None and self.book_side is not None:
            object.__setattr__(
                self, "outcome_side",
                OutcomeSide(outcome_side_from_book_side(self.book_side)),
            )
        return self

    @property
    def is_bid(self) -> bool:
        """True when this order is long yes (``book_side == bid``)."""
        return self.book_side == BookSide.BID

    @property
    def is_ask(self) -> bool:
        """True when this order is long no (``book_side == ask``)."""
        return self.book_side == BookSide.ASK


class BalanceModel(BaseModel):
    """Pydantic model for Balance data. Values are cents integers."""

    balance: int
    portfolio_value: int
    updated_ts: int | None = None


    model_config = ConfigDict(extra="ignore")

    def _repr_html_(self) -> str:
        from ._repr import balance_html
        return balance_html(self)


class PositionModel(BaseModel):
    """Pydantic model for a portfolio position."""

    ticker: str
    position_fp: str  # Net position (positive = yes, negative = no)
    market_exposure_dollars: str | None = None
    total_traded_dollars: str | None = None
    resting_orders_count: int | None = None
    fees_paid_dollars: str | None = None
    realized_pnl_dollars: str | None = None
    last_updated_ts: str | None = None


    model_config = ConfigDict(extra="ignore")

    def _repr_html_(self) -> str:
        from ._repr import position_html
        return position_html(self)


class FillModel(BaseModel):
    """Pydantic model for a trade fill/execution."""

    trade_id: str
    ticker: str
    order_id: str

    # Canonical direction. On a fill, book_side == bid means the fill made you
    # longer yes; ask means longer no.
    book_side: _OptBookSide = None
    outcome_side: _OptOutcomeSide = None

    # Deprecated by Kalshi. These were previously REQUIRED here, which made
    # every get_fills() call raise the moment the server stopped sending them.
    #
    # Note the fill convention differs from the order convention: on a fill
    # `side` is the outcome acquired and `action` carries no sign, so a
    # sell/yes fill is long YES. Do not feed these to the order-side mapper.
    action: _LegacyAction = None
    side: _LegacySide = None

    count_fp: str
    yes_price_dollars: str = Field(validation_alias=AliasChoices('yes_price_dollars', 'yes_price_fixed'))
    no_price_dollars: str | None = Field(default=None, validation_alias=AliasChoices('no_price_dollars', 'no_price_fixed'))
    is_taker: bool | None = None
    fill_id: str | None = None
    market_ticker: str | None = None
    fee_cost_dollars: str | None = Field(default=None, validation_alias=AliasChoices('fee_cost_dollars', 'fee_cost'))
    created_time: str | None = None
    subaccount_number: int | None = None
    ts: int | None = None


    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @model_validator(mode="after")
    def _fill_canonical_direction(self):
        """Back-fill canonical direction using the FILL mapping.

        Deliberately ignores ``action``: on a fill it carries no sign, and
        feeding the pair to the order-side mapper inverts every sell row.
        """
        if self.book_side is None and self.outcome_side is not None:
            object.__setattr__(
                self, "book_side",
                BookSide(book_side_from_outcome_side(self.outcome_side)),
            )
        if self.book_side is None:
            derived = book_side_from_fill_legacy(self.side)
            if derived:
                object.__setattr__(self, "book_side", BookSide(derived))
        if self.outcome_side is None and self.book_side is not None:
            object.__setattr__(
                self, "outcome_side",
                OutcomeSide(outcome_side_from_book_side(self.book_side)),
            )
        return self

    @property
    def is_bid(self) -> bool:
        """True when this fill increased the yes position."""
        return self.book_side == BookSide.BID

    @property
    def is_ask(self) -> bool:
        """True when this fill decreased the yes position."""
        return self.book_side == BookSide.ASK

    @property
    def yes_delta_fp(self) -> Decimal:
        """Signed change to the YES position from this fill."""
        n = Decimal(self.count_fp)
        return n if self.book_side == BookSide.BID else -n

    def _repr_html_(self) -> str:
        from ._repr import fill_html
        return fill_html(self)


class OHLCData(BaseModel):
    """OHLC price data (dollar strings)."""

    open_dollars: str | None = None
    high_dollars: str | None = None
    low_dollars: str | None = None
    close_dollars: str | None = None


    model_config = ConfigDict(extra="ignore")


class PriceData(BaseModel):
    """Price data with additional fields (dollar strings)."""

    open_dollars: str | None = None
    high_dollars: str | None = None
    low_dollars: str | None = None
    close_dollars: str | None = None
    max_dollars: str | None = None
    min_dollars: str | None = None
    mean_dollars: str | None = None
    previous_dollars: str | None = None


    model_config = ConfigDict(extra="ignore")


class Candlestick(BaseModel):
    """Pydantic model for a single Candlestick."""

    end_period_ts: int
    volume_fp: str | None = None
    open_interest_fp: str | None = None
    price: PriceData
    yes_bid: OHLCData | None = None
    yes_ask: OHLCData | None = None


    model_config = ConfigDict(extra="ignore")


class CandlestickResponse(BaseModel):
    """Pydantic model for Candlestick API response."""

    candlesticks: list[Candlestick]
    ticker: str = Field(validation_alias="market_ticker")

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    def to_dataframe(self):
        """Convert candlesticks to a pandas DataFrame.

        Requires pandas: pip install pykalshi[dataframe]

        Returns:
            DataFrame with columns: ticker, end_period_ts, timestamp,
            volume_fp, open_interest_fp, open_dollars, high_dollars,
            low_dollars, close_dollars, mean_dollars.
        """
        from .dataframe import to_dataframe
        return to_dataframe(self)


# Orderbook Models
class Orderbook(BaseModel):
    """Orderbook with yes/no price levels (dollar strings)."""

    yes_dollars: list[tuple[str, str]] | None = None  # [(price_dollars, quantity_fp), ...]
    no_dollars: list[tuple[str, str]] | None = None


    model_config = ConfigDict(extra="ignore")


class OrderbookResponse(BaseModel):
    """Pydantic model for the orderbook API response."""

    orderbook: Orderbook = Field(validation_alias=AliasChoices('orderbook', 'orderbook_fp'))

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @cached_property
    def best_yes_bid(self) -> str | None:
        """Highest YES bid price (dollar string), or None if no bids."""
        if not self.orderbook.yes_dollars:
            return None
        return str(max(Decimal(p) for p, _ in self.orderbook.yes_dollars))

    @cached_property
    def best_no_bid(self) -> str | None:
        """Highest NO bid price (dollar string), or None if no bids."""
        if not self.orderbook.no_dollars:
            return None
        return str(max(Decimal(p) for p, _ in self.orderbook.no_dollars))

    @cached_property
    def best_yes_ask(self) -> str | None:
        """Lowest YES ask (= 1.00 - best NO bid), dollar string."""
        if self.best_no_bid is None:
            return None
        return str(Decimal("1") - Decimal(self.best_no_bid))

    @cached_property
    def spread(self) -> str | None:
        """Bid-ask spread in dollars. None if no two-sided market."""
        if self.best_yes_bid is None or self.best_yes_ask is None:
            return None
        return str(Decimal(self.best_yes_ask) - Decimal(self.best_yes_bid))

    @cached_property
    def mid(self) -> str | None:
        """Mid price (dollar string). None if no two-sided market."""
        if self.best_yes_bid is None or self.best_yes_ask is None:
            return None
        return str((Decimal(self.best_yes_bid) + Decimal(self.best_yes_ask)) / 2)

    @cached_property
    def spread_bps(self) -> float | None:
        """Spread as basis points of mid. None if no two-sided market."""
        if self.spread is None or self.mid is None:
            return None
        mid_d = Decimal(self.mid)
        if mid_d == 0:
            return None
        return float(Decimal(self.spread) / mid_d * 10000)

    def yes_depth(self, through_price: str) -> str:
        """Total YES bid quantity at or above `through_price` (dollar string)."""
        if not self.orderbook.yes_dollars:
            return "0"
        threshold = Decimal(through_price)
        total = sum(Decimal(q) for p, q in self.orderbook.yes_dollars if Decimal(p) >= threshold)
        return str(total)

    def no_depth(self, through_price: str) -> str:
        """Total NO bid quantity at or above `through_price` (dollar string)."""
        if not self.orderbook.no_dollars:
            return "0"
        threshold = Decimal(through_price)
        total = sum(Decimal(q) for p, q in self.orderbook.no_dollars if Decimal(p) >= threshold)
        return str(total)

    @cached_property
    def imbalance(self) -> float | None:
        """Order imbalance: (yes_depth - no_depth) / (yes_depth + no_depth). Range [-1, 1]."""
        yes_total = sum(Decimal(q) for _, q in self.orderbook.yes_dollars) if self.orderbook.yes_dollars else Decimal(0)
        no_total = sum(Decimal(q) for _, q in self.orderbook.no_dollars) if self.orderbook.no_dollars else Decimal(0)
        total = yes_total + no_total
        if total == 0:
            return None
        return float((yes_total - no_total) / total)

    def vwap_to_fill(self, side: str, size: str) -> str | None:
        """Volume-weighted average price to fill `size` contracts.

        Args:
            side: "yes" or "no" - the side you're buying
            size: Number of contracts to fill (fixed-point string)

        Returns:
            VWAP as dollar string, or None if insufficient liquidity.
        """
        # To buy YES, you lift NO offers (sorted by price descending = best first)
        # To buy NO, you lift YES offers (sorted by price descending = best first)
        levels = self.orderbook.no_dollars if side == "yes" else self.orderbook.yes_dollars
        if not levels:
            return None

        sorted_levels = sorted(levels, key=lambda x: Decimal(x[0]), reverse=True)

        remaining = Decimal(size)
        cost = Decimal(0)
        for price_str, qty_str in sorted_levels:
            price = Decimal(price_str)
            qty = Decimal(qty_str)
            take = min(remaining, qty)
            fill_price = Decimal("1") - price
            cost += take * fill_price
            remaining -= take
            if remaining <= 0:
                break

        if remaining > 0:
            return None
        return str(cost / Decimal(size))

    def to_dataframe(self):
        """Convert orderbook to a pandas DataFrame with price levels.

        Requires pandas: pip install pykalshi[dataframe]

        Returns:
            DataFrame with columns: side, price_dollars, quantity_fp.
            Sorted by side (yes first), then price descending.
        """
        from .dataframe import to_dataframe
        return to_dataframe(self)

    def _repr_html_(self) -> str:
        from ._repr import orderbook_html
        return orderbook_html(self)


# --- Exchange Models ---

class ExchangeStatus(BaseModel):
    """Exchange operational status."""
    exchange_active: bool
    trading_active: bool

    model_config = ConfigDict(extra="ignore")

    def _repr_html_(self) -> str:
        from ._repr import exchange_status_html
        return exchange_status_html(self)


# --- Account Models ---

class RateLimitTier(BaseModel):
    """Rate limit for a specific tier."""
    max_requests: int
    period_seconds: int

    model_config = ConfigDict(extra="ignore")


class APILimits(BaseModel):
    """API rate limits for the authenticated user."""
    usage_tier: str | None = None
    read_limit: int | None = None
    write_limit: int | None = None

    model_config = ConfigDict(extra="ignore")

    def _repr_html_(self) -> str:
        from ._repr import api_limits_html
        return api_limits_html(self)


# --- API Key Models ---

class APIKey(BaseModel):
    """API key information."""
    id: str = Field(validation_alias="api_key_id")
    name: str | None = None
    created_time: str | None = None
    last_used: str | None = None
    scopes: list[str] | None = None

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    def _repr_html_(self) -> str:
        from ._repr import api_key_html
        return api_key_html(self)


class GeneratedAPIKey(BaseModel):
    """Newly generated API key with private key (only returned once)."""
    id: str = Field(validation_alias="api_key_id")
    private_key: str
    name: str | None = None

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


# --- Series & Trade Models ---

class SeriesModel(BaseModel):
    """Pydantic model for Series data."""
    ticker: str
    title: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    settlement_timer_seconds: int | None = None
    frequency: str | None = None

    model_config = ConfigDict(extra="ignore")


class TradeModel(BaseModel):
    """Public trade execution record."""
    trade_id: str
    ticker: str
    count_fp: str
    yes_price_dollars: str
    no_price_dollars: str

    # Canonical direction. Unlike Order/Fill, the legacy field maps 1:1 here
    # (a public trade has no action), so the alias is safe.
    taker_outcome_side: _OptOutcomeSide = Field(
        default=None,
        validation_alias=AliasChoices("taker_outcome_side", "taker_side"),
    )
    taker_book_side: _OptBookSide = None

    # Deprecated by Kalshi -- read taker_outcome_side / taker_book_side.
    taker_side: str | None = None

    is_block_trade: bool | None = None
    created_time: str | None = None
    ts: int | None = None


    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @model_validator(mode="after")
    def _fill_canonical_direction(self):
        if self.taker_book_side is None and self.taker_outcome_side is not None:
            object.__setattr__(
                self, "taker_book_side",
                BookSide(book_side_from_outcome_side(self.taker_outcome_side)),
            )
        if self.taker_outcome_side is None and self.taker_book_side is not None:
            object.__setattr__(
                self, "taker_outcome_side",
                OutcomeSide(outcome_side_from_book_side(self.taker_book_side)),
            )
        return self

    def _repr_html_(self) -> str:
        from ._repr import trade_html
        return trade_html(self)


class SettlementModel(BaseModel):
    """Settlement record for a resolved position."""
    ticker: str
    event_ticker: str | None = None
    market_result: str | None = None  # "yes" or "no"
    yes_count_fp: str = "0"
    no_count_fp: str = "0"
    # The API returns these as fixed-point dollar STRINGS named *_dollars. The
    # model previously declared `yes_total_cost`/`no_total_cost` as cents ints,
    # which never matched the wire, so extra="ignore" dropped them and they
    # stayed 0 -- silently removing cost from every pnl.
    yes_total_cost_dollars: str | None = Field(
        default=None,
        validation_alias=AliasChoices("yes_total_cost_dollars", "yes_total_cost"),
    )
    no_total_cost_dollars: str | None = Field(
        default=None,
        validation_alias=AliasChoices("no_total_cost_dollars", "no_total_cost"),
    )
    revenue: int = 0          # cents
    value: int | None = 0     # cents; nullable per spec
    fee_cost: str | None = None  # FixedPointDollars string (e.g. "0.3200")
    settled_time: str | None = None


    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @property
    def net_position(self) -> str:
        """Net position: positive = yes, negative = no (fixed-point string)."""
        return str(Decimal(self.yes_count_fp) - Decimal(self.no_count_fp))

    @property
    def total_cost_dollars(self) -> Decimal:
        """Combined yes+no cost basis, in dollars."""
        return (Decimal(self.yes_total_cost_dollars or "0")
                + Decimal(self.no_total_cost_dollars or "0"))

    @property
    def pnl_dollars(self) -> Decimal:
        """Net P&L in dollars (revenue - cost basis - fees)."""
        return (Decimal(self.revenue) / 100
                - self.total_cost_dollars
                - Decimal(self.fee_cost or "0"))

    @property
    def pnl(self) -> int:
        """Net P&L in cents, truncated. See :attr:`pnl_dollars` for exact."""
        return int(self.pnl_dollars * 100)

    def _repr_html_(self) -> str:
        from ._repr import settlement_html
        return settlement_html(self)


class QueuePositionModel(BaseModel):
    """Order's position in the queue at its price level."""
    order_id: str
    queue_position_fp: str  # 0-indexed, fixed-point string (e.g. "0.00")


    def _repr_html_(self) -> str:
        from ._repr import queue_position_html
        return queue_position_html(self)


class OrderGroupModel(BaseModel):
    """Order group for rate-limiting contract matches.

    Order groups limit total contracts matched across all orders in the group
    over a rolling 15-second window. When the limit is hit, all orders in the
    group are cancelled.
    """
    # API returns 'id' in list/get, but 'order_group_id' in create response
    id: str = Field(validation_alias=AliasChoices('id', 'order_group_id'))
    is_auto_cancel_enabled: bool | None = None
    contracts_limit_fp: str | None = None
    # Only returned from get_order_group (not list)
    orders: list[str] | None = None


    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    def _repr_html_(self) -> str:
        from ._repr import order_group_html
        return order_group_html(self)


# --- Subaccount Models ---

class SubaccountModel(BaseModel):
    """Subaccount info (CreateSubaccountResponse)."""
    subaccount_number: int  # 1-63; 0 is the primary account

    model_config = ConfigDict(extra="ignore")


class SubaccountBalanceModel(BaseModel):
    """Balance for a single subaccount.

    ``balance`` is a fixed-point dollar string (e.g. ``"64876.8883"``).
    The settlement-advance fields are only present for accounts using that
    feature, so they are optional here.
    """
    subaccount_number: int  # 0 for primary, 1-63 for subaccounts
    balance: str  # fixed-point dollar string
    exchange_index: int = 0
    updated_ts: int | None = None  # Unix timestamp of last balance update
    voluntarily_locked: bool | None = None
    settlement_advance: str | None = None  # fixed-point dollar string
    settlement_advance_state: str | None = None

    model_config = ConfigDict(extra="ignore")


class SubaccountTransferModel(BaseModel):
    """Record of a transfer between subaccounts."""
    transfer_id: str
    from_subaccount: int  # 0 for primary, 1-63 for subaccounts
    to_subaccount: int  # 0 for primary, 1-63 for subaccounts
    amount_cents: int
    created_ts: int | None = None  # Unix timestamp
    exchange_index: int = 0

    model_config = ConfigDict(extra="ignore")


class SubaccountNettingModel(BaseModel):
    """Netting-enabled setting for a single subaccount."""
    subaccount_number: int  # 0 for primary, 1-63 for subaccounts
    enabled: bool
    exchange_index: int = 0

    model_config = ConfigDict(extra="ignore")


class ForecastPoint(BaseModel):
    """A single point in forecast percentile history."""
    ts: int  # Unix timestamp
    value_dollars: str  # Forecast value as dollar string


    model_config = ConfigDict(extra="ignore")


class ForecastPercentileHistory(BaseModel):
    """Historical forecast data at various percentiles for an event."""
    event_ticker: str
    percentiles: dict[str, list[ForecastPoint]]  # Maps percentile (e.g., "50") to history

    model_config = ConfigDict(extra="ignore")


# --- Multivariate Event Collection Models ---

class AssociatedEventModel(BaseModel):
    """An event available as a leg in a multivariate event collection."""
    ticker: str
    is_yes_only: bool = False
    size_min_fp: str | None = None
    size_max_fp: str | None = None
    active_quoters: list[str] | None = None


    model_config = ConfigDict(extra="ignore")


class MveCollectionModel(BaseModel):
    """Pydantic model for a multivariate event collection (combo container)."""
    collection_ticker: str
    series_ticker: str | None = None
    title: str | None = None
    description: str | None = None
    open_date: str | None = None
    close_date: str | None = None
    associated_events: list[AssociatedEventModel] | None = None
    is_ordered: bool = False
    size_min_fp: str | None = None
    size_max_fp: str | None = None
    functional_description: str | None = None


    model_config = ConfigDict(extra="ignore")


# --- Communications Models (RFQ / Quotes) ---

class RfqModel(BaseModel):
    """Request for Quote on a multivariate event combo."""
    rfq_id: str = Field(validation_alias=AliasChoices('rfq_id', 'id'))
    market_ticker: str | None = None
    status: str | None = None
    contracts_fp: str | None = None
    target_cost_dollars: str | None = None
    rest_remainder: bool | None = None
    mve_collection_ticker: str | None = None
    mve_selected_legs: list[MveSelectedLeg] | None = None
    created_ts: str | None = None
    expiration_time: str | None = None
    creator_id: str | None = None


    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class QuoteModel(BaseModel):
    """A quote in response to an RFQ."""
    quote_id: str = Field(validation_alias=AliasChoices('quote_id', 'id'))
    rfq_id: str | None = None
    market_ticker: str | None = None
    status: str | None = None
    yes_bid_dollars: str | None = None
    no_bid_dollars: str | None = None
    rest_remainder: bool | None = None
    created_ts: str | None = None
    expiration_time: str | None = None
    creator_id: str | None = None


    model_config = ConfigDict(extra="ignore", populate_by_name=True)
