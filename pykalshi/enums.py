from enum import Enum


class Side(str, Enum):
    """Legacy outcome side on Order/Fill.

    .. deprecated::
        Kalshi deprecated ``side`` on Order and Fill responses; see
        https://docs.kalshi.com/getting_started/order_direction. Read
        :class:`BookSide` instead. Still used as an *input* to
        ``place_order`` and as a live field on orderbook deltas and
        multivariate legs, so the enum itself is not going away.
    """

    YES = "yes"
    NO = "no"


class Action(str, Enum):
    """Legacy action on Order/Fill.

    .. deprecated::
        Deprecated alongside :class:`Side` on responses. Still an input to
        ``place_order``.
    """

    BUY = "buy"
    SELL = "sell"


class BookSide(str, Enum):
    """Side of the single YES-denominated book. The canonical direction field.

    ``bid`` is long yes, ``ask`` is long no. Present on Order, Fill and
    (as ``taker_book_side``) Trade, on both REST and WebSocket.

    Prefer this over :class:`Side`/:class:`Action` for every direction
    decision. It is the only direction field that means the same thing on
    orders and on fills -- the legacy ``side`` does not (see
    :class:`OutcomeSide`).
    """

    BID = "bid"
    ASK = "ask"


class OutcomeSide(str, Enum):
    """Which outcome the holder is long. Canonical, equivalent to :class:`BookSide`.

    ``yes`` is exactly ``BookSide.BID``; ``no`` is exactly ``BookSide.ASK``.

    A caveat worth knowing: on *orders* ``outcome_side`` is derived from the
    legacy ``(action, side)`` pair, so a ``sell``/``yes`` order reports
    ``outcome_side="no"``. On *fills* it equals the legacy ``side``. The two
    surfaces therefore disagree about what legacy ``side`` means, which is why
    :class:`BookSide` -- identical on both -- is the safer thing to branch on.
    """

    YES = "yes"
    NO = "no"


class OrderType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"


class OrderStatus(str, Enum):
    RESTING = "resting"
    CANCELED = "canceled"
    EXECUTED = "executed"  # Order has been fully filled


class MarketStatus(str, Enum):
    """Market status values.

    Query filter values: unopened, open, paused, closed, settled
    Lifecycle values: initialized, inactive, active, closed, determined, disputed, amended, finalized
    """
    # Query filter statuses
    UNOPENED = "unopened"
    OPEN = "open"
    PAUSED = "paused"
    CLOSED = "closed"
    SETTLED = "settled"
    # Lifecycle statuses
    INITIALIZED = "initialized"
    INACTIVE = "inactive"
    ACTIVE = "active"
    DETERMINED = "determined"
    DISPUTED = "disputed"
    AMENDED = "amended"
    FINALIZED = "finalized"


class CandlestickPeriod(int, Enum):
    """Candlestick period intervals in minutes."""

    ONE_MINUTE = 1
    ONE_HOUR = 60
    ONE_DAY = 1440


class TimeInForce(str, Enum):
    """Order time-in-force options."""

    GTC = "good_till_canceled"  # Good till canceled (default)
    IOC = "immediate_or_cancel"  # Immediate or cancel - fill what you can, cancel rest
    FOK = "fill_or_kill"  # Fill or kill - fill entirely or cancel entirely


class PositionCountFilter(str, Enum):
    """Filter for positions with non-zero values."""

    POSITION = "position"  # Non-zero contract holdings
    TOTAL_TRADED = "total_traded"  # Non-zero trading activity


class SelfTradePrevention(str, Enum):
    """Self-trade prevention behavior."""

    CANCEL_INCOMING = "taker_at_cross"  # Cancel the incoming (taker) order on self-cross
    CANCEL_RESTING = "maker"  # Cancel the resting (maker) order on self-cross
