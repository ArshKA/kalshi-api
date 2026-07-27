"""
Kalshi API Client Library

A clean, modular interface for the Kalshi trading API.
"""

__version__ = "2.0.0"

import logging

from .client import KalshiClient
from .aclient import AsyncKalshiClient
from .events import Event, AsyncEvent
from .markets import Market, Series, AsyncMarket, AsyncSeries
from .mve import MveCollection, AsyncMveCollection
from .orders import Order, AsyncOrder
from .portfolio import Portfolio, AsyncPortfolio
from .exchange import Exchange, AsyncExchange
from .history import History, AsyncHistory
from .api_keys import APIKeys, AsyncAPIKeys
from .communications import Communications, AsyncCommunications
from .feed import (
    Feed,
    TickerMessage,
    OrderbookSnapshotMessage,
    OrderbookDeltaMessage,
    OrderbookMessage,
    TradeMessage,
    FillMessage,
    PositionMessage,
    MarketLifecycleMessage,
    OrderGroupUpdateMessage,
    UserOrderMessage,
    ErrorMessage,
)
from .afeed import AsyncFeed
from .enums import (
    Side,
    Action,
    OrderType,
    BookSide,
    OutcomeSide,
    OrderStatus,
    MarketStatus,
    CandlestickPeriod,
    TimeInForce,
    SelfTradePrevention,
    PositionCountFilter,
)
from .models import (
    PositionModel,
    FillModel,
    OrderModel,
    BalanceModel,
    MarketModel,
    EventModel,
    OrderbookResponse,
    CandlestickResponse,
    ExchangeStatus,
    APILimits,
    APIKey,
    GeneratedAPIKey,
    SeriesModel,
    TradeModel,
    SettlementModel,
    QueuePositionModel,
    OrderGroupModel,
    SubaccountModel,
    SubaccountBalanceModel,
    SubaccountTransferModel,
    SubaccountNettingModel,
    ForecastPercentileHistory,
    MveSelectedLeg,
    MveCollectionModel,
    AssociatedEventModel,
    RfqModel,
    QuoteModel,
    HistoricalCutoffResponse,
    HistoricalCandlestick,
    HistoricalBidAsk,
    HistoricalPrice,
)
from .orderbook import OrderbookManager
from .rate_limiter import RateLimiter, NoOpRateLimiter, AsyncRateLimiter, AsyncNoOpRateLimiter
from .dataframe import to_dataframe, DataFrameList
from .exceptions import (
    KalshiError,
    KalshiAPIError,
    AuthenticationError,
    InsufficientFundsError,
    ResourceNotFoundError,
    RateLimitError,
    OrderRejectedError,
)

# Set up logging to NullHandler by default to avoid "No handler found" warnings.
logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    # Client
    "KalshiClient",
    "AsyncKalshiClient",
    # Domain objects
    "Event",
    "AsyncEvent",
    "Market",
    "AsyncMarket",
    "Series",
    "AsyncSeries",
    "MveCollection",
    "AsyncMveCollection",
    "Order",
    "AsyncOrder",
    "Portfolio",
    "AsyncPortfolio",
    "Exchange",
    "AsyncExchange",
    "History",
    "AsyncHistory",
    "APIKeys",
    "AsyncAPIKeys",
    "Communications",
    "AsyncCommunications",
    # Feed (WebSocket)
    "Feed",
    "AsyncFeed",
    "TickerMessage",
    "OrderbookSnapshotMessage",
    "OrderbookDeltaMessage",
    "OrderbookMessage",
    "TradeMessage",
    "FillMessage",
    "PositionMessage",
    "MarketLifecycleMessage",
    "OrderGroupUpdateMessage",
    "UserOrderMessage",
    "ErrorMessage",
    # Enums
    "Side",
    "Action",
    "OrderType",
    "BookSide",
    "OutcomeSide",
    "OrderStatus",
    "MarketStatus",
    "CandlestickPeriod",
    "TimeInForce",
    "SelfTradePrevention",
    "PositionCountFilter",
    # Models
    "PositionModel",
    "FillModel",
    "OrderModel",
    "BalanceModel",
    "MarketModel",
    "EventModel",
    "OrderbookResponse",
    "CandlestickResponse",
    "ExchangeStatus",
    "APILimits",
    "APIKey",
    "GeneratedAPIKey",
    "SeriesModel",
    "TradeModel",
    "SettlementModel",
    "QueuePositionModel",
    "OrderGroupModel",
    "ForecastPercentileHistory",
    # Historical Models
    "HistoricalCutoffResponse",
    "HistoricalCandlestick",
    "HistoricalBidAsk",
    "HistoricalPrice",
    # MVE & Communications Models
    "MveSelectedLeg",
    "MveCollectionModel",
    "AssociatedEventModel",
    "RfqModel",
    "QuoteModel",
    # Utilities
    "OrderbookManager",
    "RateLimiter",
    "NoOpRateLimiter",
    "AsyncRateLimiter",
    "AsyncNoOpRateLimiter",
    "to_dataframe",
    "DataFrameList",
    # Subaccount Models
    "SubaccountModel",
    "SubaccountBalanceModel",
    "SubaccountTransferModel",
    "SubaccountNettingModel",
    # Exceptions
    "KalshiError",
    "KalshiAPIError",
    "AuthenticationError",
    "InsufficientFundsError",
    "ResourceNotFoundError",
    "RateLimitError",
    "OrderRejectedError",
]
