"""Real-time data feed via WebSocket.

This module provides streaming market data through Kalshi's WebSocket API.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import logging
import threading
import time
from datetime import datetime
from typing import Annotated, Any, Callable, Union, TYPE_CHECKING

from pydantic import AliasChoices, BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from ._utils import normalize_ticker, normalize_tickers

if TYPE_CHECKING:
    from .client import KalshiClient

logger = logging.getLogger(__name__)

# WebSocket endpoints
DEFAULT_WS_BASE = "wss://external-api-ws.kalshi.com/trade-api/ws/v2"
DEMO_WS_BASE = "wss://external-api-ws.demo.kalshi.co/trade-api/ws/v2"
_WS_SIGN_PATH = "/trade-api/ws/v2"


# --- Timestamp parsing ---


def _parse_ts(value: Any) -> int | None:
    """Coerce a Kalshi WebSocket ``ts`` to int milliseconds since epoch.

    Pre-April-2026 Kalshi sent int ms; since then it sends ISO 8601 strings
    (e.g. ``'2026-04-22T18:31:59.043421Z'``). Accept both; unrecognized
    values return None rather than raising.
    """
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
        except ValueError:
            return None
    return None


TsField = Annotated[int | None, BeforeValidator(_parse_ts)]


# --- WebSocket Message Models ---


class TickerMessage(BaseModel):
    """Real-time market ticker update.

    Sent when price, volume, or open interest changes for a subscribed market.
    """


    market_ticker: str
    market_id: str | None = None
    price_dollars: str | None = None
    yes_bid_dollars: str | None = None
    yes_ask_dollars: str | None = None
    yes_bid_size_fp: str | None = None
    yes_ask_size_fp: str | None = None
    last_trade_size_fp: str | None = None
    volume_fp: str | None = None
    open_interest_fp: str | None = None
    # Wire sends `dollar_volume` / `dollar_open_interest` as integers. The old
    # `*_dollars` string fields never matched and were always None.
    dollar_volume: int | None = Field(
        default=None,
        validation_alias=AliasChoices("dollar_volume", "dollar_volume_dollars"),
    )
    dollar_open_interest: int | None = Field(
        default=None,
        validation_alias=AliasChoices("dollar_open_interest", "dollar_open_interest_dollars"),
    )
    ts_ms: int | None = None
    ts: TsField = None  # deprecated by Kalshi; seconds, not ms -- prefer ts_ms

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class OrderbookSnapshotMessage(BaseModel):
    """Full orderbook state received on initial subscription.

    Contains all current price levels as dollar/fp strings.
    After this, you'll receive OrderbookDeltaMessage for incremental updates.
    """


    market_ticker: str
    market_id: str | None = None
    # The wire field names carry an `_fp` suffix. The model previously declared
    # them without it, so both were always None and OrderbookManager wiped the
    # book to empty on every snapshot. (The REST orderbook genuinely has no
    # suffix -- models.Orderbook is correct and must not be renamed.)
    yes_dollars_fp: list[tuple[str, str]] | None = Field(
        default=None, validation_alias=AliasChoices("yes_dollars_fp", "yes_dollars"),
    )
    no_dollars_fp: list[tuple[str, str]] | None = Field(
        default=None, validation_alias=AliasChoices("no_dollars_fp", "no_dollars"),
    )

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @property
    def yes_dollars(self) -> list[tuple[str, str]] | None:
        """Backwards-compatible alias for :attr:`yes_dollars_fp`."""
        return self.yes_dollars_fp

    @property
    def no_dollars(self) -> list[tuple[str, str]] | None:
        """Backwards-compatible alias for :attr:`no_dollars_fp`."""
        return self.no_dollars_fp


class OrderbookDeltaMessage(BaseModel):
    """Incremental orderbook update.

    Represents a change at a single price level. Apply to local orderbook state.
    """


    market_ticker: str
    market_id: str | None = None
    price_dollars: str
    delta_fp: str  # Positive = added, negative = removed
    side: str  # "yes" or "no" -- orderbook side, NOT the deprecated order side
    client_order_id: str | None = None
    subaccount: int | None = None
    ts_ms: int | None = None
    ts: TsField = None

    model_config = ConfigDict(extra="ignore")


class TradeMessage(BaseModel):
    """Public trade execution.

    Sent when any trade occurs on subscribed markets.
    """


    market_ticker: str | None = None
    trade_id: str | None = None
    count_fp: str | None = None
    yes_price_dollars: str | None = None
    no_price_dollars: str | None = None
    # Canonical direction. A public trade has no `action`, so the legacy
    # `taker_side` maps 1:1 and the alias is safe here (unlike on Fill).
    taker_outcome_side: str | None = Field(
        default=None,
        validation_alias=AliasChoices("taker_outcome_side", "taker_side"),
    )
    taker_book_side: str | None = None
    taker_side: str | None = None  # deprecated by Kalshi
    ts_ms: int | None = None
    ts: TsField = None

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @model_validator(mode="after")
    def _canonical_direction(self):
        if self.taker_book_side is None and self.taker_outcome_side:
            object.__setattr__(
                self, "taker_book_side",
                "bid" if self.taker_outcome_side == "yes" else "ask",
            )
        if self.taker_outcome_side is None and self.taker_book_side:
            object.__setattr__(
                self, "taker_outcome_side",
                "yes" if self.taker_book_side == "bid" else "no",
            )
        return self


class FillMessage(BaseModel):
    """User fill notification (private channel).

    Sent when your orders are filled.

    Branch on :attr:`book_side`: ``bid`` means the fill increased your yes
    position, ``ask`` means it decreased it. Do NOT derive direction from
    ``action``/``side`` -- on a fill ``side`` is the outcome acquired and
    ``action`` carries no sign, which is the opposite of the order convention.
    """


    trade_id: str | None = None
    # Wire sends `market_ticker`. The model previously declared only `ticker`,
    # so it was always None and `msg.market_ticker` raised AttributeError.
    market_ticker: str | None = Field(
        default=None, validation_alias=AliasChoices("market_ticker", "ticker"),
    )
    order_id: str | None = None

    # Canonical direction.
    book_side: str | None = None
    outcome_side: str | None = None

    # Deprecated by Kalshi.
    side: str | None = None
    action: str | None = None
    purchased_side: str | None = None

    count_fp: str | None = None
    yes_price_dollars: str | None = None
    fee_cost: str | None = None
    post_position_fp: str | None = None
    is_taker: bool | None = None
    client_order_id: str | None = None
    subaccount: int | None = None
    ts_ms: int | None = None
    ts: TsField = None

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @property
    def ticker(self) -> str | None:
        """Backwards-compatible alias for :attr:`market_ticker`."""
        return self.market_ticker

    @model_validator(mode="after")
    def _canonical_direction(self):
        if self.book_side is None and self.outcome_side:
            object.__setattr__(
                self, "book_side", "bid" if self.outcome_side == "yes" else "ask")
        # Fill mapping: `side` is the outcome acquired. `action` is ignored on
        # purpose -- including it inverts the sell rows.
        if self.book_side is None and self.side:
            object.__setattr__(
                self, "book_side", "bid" if self.side == "yes" else "ask")
        if self.outcome_side is None and self.book_side:
            object.__setattr__(
                self, "outcome_side", "yes" if self.book_side == "bid" else "no")
        return self


class UserOrderMessage(BaseModel):
    """Resting-order lifecycle update (private ``user_orders`` channel).

    Note this channel uses ``ticker``, not ``market_ticker``, and carries no
    ``action`` -- branch on :attr:`book_side`.
    """

    order_id: str | None = None
    user_id: str | None = None
    ticker: str | None = Field(
        default=None, validation_alias=AliasChoices("ticker", "market_ticker"),
    )
    status: str | None = None

    book_side: str | None = None
    outcome_side: str | None = None
    side: str | None = None      # deprecated
    is_yes: bool | None = None   # deprecated

    yes_price_dollars: str | None = None
    fill_count_fp: str | None = None
    remaining_count_fp: str | None = None
    initial_count_fp: str | None = None
    taker_fill_cost_dollars: str | None = None
    maker_fill_cost_dollars: str | None = None
    taker_fees_dollars: str | None = None
    maker_fees_dollars: str | None = None
    client_order_id: str | None = None
    order_group_id: str | None = None
    self_trade_prevention_type: str | None = None
    created_ts_ms: int | None = None
    last_updated_ts_ms: int | None = None
    expiration_ts_ms: int | None = None
    created_time: str | None = None      # deprecated
    last_update_time: str | None = None  # deprecated
    expiration_time: str | None = None   # deprecated
    subaccount_number: int | None = None

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @model_validator(mode="after")
    def _canonical_direction(self):
        if self.book_side is None and self.outcome_side:
            object.__setattr__(
                self, "book_side", "bid" if self.outcome_side == "yes" else "ask")
        if self.book_side is None and self.is_yes is not None:
            object.__setattr__(self, "book_side", "bid" if self.is_yes else "ask")
        if self.outcome_side is None and self.book_side:
            object.__setattr__(
                self, "outcome_side", "yes" if self.book_side == "bid" else "no")
        return self


class PositionMessage(BaseModel):
    """Real-time position update (private channel).

    Sent when your position in a market changes (after fills settle).
    """


    # Wire sends `market_ticker`. This was declared as a REQUIRED `ticker`,
    # so every frame failed validation and silently degraded to a raw dict.
    market_ticker: str | None = Field(
        default=None, validation_alias=AliasChoices("market_ticker", "ticker"),
    )
    user_id: str | None = None
    position_fp: str | None = None
    position_cost_dollars: str | None = None
    position_fee_cost_dollars: str | None = None
    realized_pnl_dollars: str | None = None
    fees_paid_dollars: str | None = None
    volume_fp: str | None = None
    subaccount: int | None = None

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @property
    def ticker(self) -> str | None:
        """Backwards-compatible alias for :attr:`market_ticker`."""
        return self.market_ticker


class MarketLifecycleMessage(BaseModel):
    """Market lifecycle state change (public channel)."""

    market_ticker: str
    # Wire sends `event_type`; the model declared `status`, always None.
    event_type: str | None = Field(
        default=None, validation_alias=AliasChoices("event_type", "status"),
    )
    result: str | None = None  # Settlement result ("yes" or "no")
    open_ts: int | None = None
    close_ts: int | None = None
    determination_ts: int | None = None
    settled_ts: int | None = None
    settlement_value: str | None = None
    is_deactivated: bool | None = None
    price_level_structure: str | None = None
    price_ranges: list[dict] | None = None
    event_ticker: str | None = None

    # Emitted on `metadata_updated` events (and `additional_metadata` on
    # `created`). Previously unmodelled, so extra="ignore" silently dropped the
    # entire payload of a metadata_updated frame -- the message arrived with
    # nothing on it but the ticker and event_type.
    #
    # strike_type governs how the strikes are read: "between" uses both,
    # "greater" floor only, "less" cap only.
    strike_type: str | None = None
    floor_strike: float | None = None
    cap_strike: float | None = None
    custom_strike: dict | None = None
    yes_sub_title: str | None = None
    additional_metadata: dict | None = None

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class OrderGroupUpdateMessage(BaseModel):
    """Order group lifecycle update (private channel)."""

    order_group_id: str
    # Wire sends `event_type`; the model declared `status`, always None.
    event_type: str | None = Field(
        default=None, validation_alias=AliasChoices("event_type", "status"),
    )
    contracts_limit_fp: str | None = None
    ts_ms: int | None = None

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


OrderbookMessage = Union[OrderbookSnapshotMessage, OrderbookDeltaMessage]


class ErrorMessage(BaseModel):
    """Server-side error frame. Previously swallowed with no log line."""

    code: int | None = None
    msg: str | None = None
    market_ticker: str | None = None
    market_id: str | None = None

    model_config = ConfigDict(extra="ignore")


_MESSAGE_MODELS: dict[str, type[BaseModel]] = {
    "ticker": TickerMessage,
    "orderbook_snapshot": OrderbookSnapshotMessage,
    "orderbook_delta": OrderbookDeltaMessage,
    "trade": TradeMessage,
    "fill": FillMessage,
    "market_position": PositionMessage,
    "market_lifecycle_v2": MarketLifecycleMessage,
    # Wire type is plural. The old singular key never matched, so these frames
    # fell through to a raw dict.
    "order_group_updates": OrderGroupUpdateMessage,
    "user_order": UserOrderMessage,
    "error": ErrorMessage,
}

# Maps message types to channel name for handler lookup
_TYPE_TO_CHANNEL: dict[str, str] = {
    "orderbook_snapshot": "orderbook_delta",
    "orderbook_delta": "orderbook_delta",
    "ticker": "ticker",
    "trade": "trade",
    "fill": "fill",
    "market_position": "market_positions",
    "market_lifecycle_v2": "market_lifecycle_v2",
    "order_group_updates": "order_group_updates",
    # Subscribers use the channel name `user_orders`; the frames say
    # `user_order`. Map it so feed.on("user_orders") actually fires.
    "user_order": "user_orders",
}


def _parse_message(raw: str | bytes) -> tuple[str | None, str | None, Any, dict]:
    """Parse a raw WebSocket message into components.

    Shared by Feed and AsyncFeed.

    Returns:
        (msg_type, channel, parsed_payload, raw_data)
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None, None, None, {}

    msg_type = data.get("type")
    if not msg_type:
        return None, None, None, data

    payload = data.get("msg", data)
    channel = _TYPE_TO_CHANNEL.get(msg_type, msg_type)

    model_cls = _MESSAGE_MODELS.get(msg_type)
    if model_cls and isinstance(payload, dict):
        try:
            parsed = model_cls.model_validate(payload)
        except Exception:
            # Degrading to a raw dict silently is how wire/model drift stays
            # invisible -- handlers typed for a model start seeing dicts.
            logger.warning(
                "Failed to validate %s payload against %s; passing raw dict",
                msg_type, model_cls.__name__, exc_info=True,
            )
            parsed = payload
    else:
        parsed = payload

    return msg_type, channel, parsed, data


class Feed:
    """Real-time streaming data feed via WebSocket.

    Usage:
        feed = client.feed()

        @feed.on("ticker")
        def handle_ticker(msg: TickerMessage):
            print(f"{msg.market_ticker}: ${msg.yes_bid_dollars}/${msg.yes_ask_dollars}")

        @feed.on("orderbook_delta")
        def handle_orderbook(msg: OrderbookMessage):
            if isinstance(msg, OrderbookSnapshotMessage):
                # Initialize local orderbook
                pass
            else:
                # Apply delta
                pass

        feed.subscribe("ticker", market_ticker="KXBTC-26JAN")
        feed.subscribe("orderbook_delta", market_ticker="KXBTC-26JAN")

        feed.start()  # Runs in background thread
        # ... do other work ...
        feed.stop()

        # Or use as context manager:
        with client.feed() as feed:
            feed.on("ticker", my_handler)
            feed.subscribe("ticker", market_ticker="KXBTC-26JAN")
            time.sleep(60)

    Available channels:
        - "ticker": Market price/volume updates (public)
        - "trade": Public trade executions (public)
        - "orderbook_delta": Orderbook snapshots and deltas (requires auth)
        - "fill": Your order fills (requires auth, no market filter)
        - "market_positions": Real-time position updates with P&L (requires auth, no market filter)
        - "market_lifecycle_v2": Market state changes (public)
        - "order_group_updates": Order group lifecycle changes (requires auth)
    """

    def __init__(self, client: KalshiClient) -> None:
        self._client = client
        self._handlers: dict[str, list[Callable]] = {}
        self._active_subs: list[dict] = []
        self._sids: dict[int, dict] = {}
        self._pending_subs: dict[int, dict] = {}
        self._ws: Any = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._cmd_id_counter = itertools.count(1)
        self._connected = threading.Event()
        self._lock = threading.Lock()
        self._metrics_lock = threading.Lock()

        self._connected_at: float | None = None
        self._last_message_at: float | None = None
        self._last_server_ts: int | None = None
        self._message_count: int = 0
        self._reconnect_count: int = 0

        self._ws_url = DEMO_WS_BASE if "demo" in client.api_base else DEFAULT_WS_BASE

    def on(
        self, channel: str, handler: Callable | None = None
    ) -> Callable:
        """Register a handler for a channel. Can be used as decorator or called directly."""
        if handler is not None:
            self._handlers.setdefault(channel, []).append(handler)
            return handler

        def decorator(fn: Callable) -> Callable:
            self._handlers.setdefault(channel, []).append(fn)
            return fn

        return decorator

    def subscribe(
        self,
        channel: str,
        *,
        market_ticker: str | None = None,
        market_tickers: list[str] | None = None,
    ) -> None:
        """Subscribe to a channel."""
        params: dict[str, Any] = {"channels": [channel]}
        if market_ticker is not None:
            params["market_ticker"] = market_ticker.upper()
        if market_tickers is not None:
            params["market_tickers"] = normalize_tickers(market_tickers)

        with self._lock:
            if params not in self._active_subs:
                self._active_subs.append(params)

        if self._loop and self._connected.is_set():
            asyncio.run_coroutine_threadsafe(
                self._subscribe_and_track(params), self._loop
            )

    async def _subscribe_and_track(self, params: dict) -> None:
        cmd_id = await self._send_cmd("subscribe", params)
        with self._lock:
            self._pending_subs[cmd_id] = params

    def unsubscribe(
        self,
        channel: str,
        *,
        market_ticker: str | None = None,
        market_tickers: list[str] | None = None,
    ) -> None:
        """Unsubscribe from a channel."""
        target: dict[str, Any] = {"channels": [channel]}
        if market_ticker is not None:
            target["market_ticker"] = market_ticker.upper()
        if market_tickers is not None:
            target["market_tickers"] = normalize_tickers(market_tickers)

        sids_to_remove: list[int] = []
        with self._lock:
            for sid, params in list(self._sids.items()):
                if params == target:
                    sids_to_remove.append(sid)
                    del self._sids[sid]
            self._active_subs = [s for s in self._active_subs if s != target]

        if sids_to_remove and self._loop and self._connected.is_set():
            asyncio.run_coroutine_threadsafe(
                self._send_cmd("unsubscribe", {"sids": sids_to_remove}), self._loop
            )

    def start(self) -> None:
        """Start the feed in a background thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._connected.clear()
            self._thread = threading.Thread(
                target=self._run, name="kalshi-feed", daemon=True
            )
            self._thread.start()
        self._connected.wait(timeout=10)

    def stop(self) -> None:
        """Stop the feed and disconnect."""
        with self._lock:
            if not self._running:
                return
            self._running = False

        if self._ws and self._loop and self._loop.is_running():
            async def close_ws():
                try:
                    await self._ws.close()
                except Exception:
                    pass
            future = asyncio.run_coroutine_threadsafe(close_ws(), self._loop)
            try:
                future.result(timeout=2)
            except Exception:
                pass

        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        self._connected.clear()
        self._connected_at = None

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    @property
    def latency_ms(self) -> float | None:
        with self._metrics_lock:
            if self._last_server_ts is None or self._last_message_at is None:
                return None
            local_ms = self._last_message_at * 1000
            return local_ms - self._last_server_ts

    @property
    def messages_received(self) -> int:
        with self._metrics_lock:
            return self._message_count

    @property
    def uptime_seconds(self) -> float | None:
        with self._metrics_lock:
            if self._connected_at is None or not self.is_connected:
                return None
            return time.time() - self._connected_at

    @property
    def seconds_since_last_message(self) -> float | None:
        with self._metrics_lock:
            if self._last_message_at is None:
                return None
            return time.time() - self._last_message_at

    @property
    def reconnect_count(self) -> int:
        with self._metrics_lock:
            return self._reconnect_count

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect_loop())
        except Exception as e:
            logger.error("Feed loop crashed: %s", e)
        finally:
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            if pending:
                self._loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            self._loop.close()
            self._loop = None

    async def _connect_loop(self) -> None:
        try:
            import websockets
        except ImportError:
            raise ImportError(
                "websockets is required for Feed. Install with: pip install websockets"
            )

        backoff = 0.5
        max_backoff = 30

        while self._running:
            try:
                headers = self._auth_headers()
                async with websockets.connect(
                    self._ws_url,
                    additional_headers=headers,
                    ping_interval=20,
                    ping_timeout=10,
                ) as ws:
                    self._ws = ws
                    backoff = 0.5

                    with self._metrics_lock:
                        if self._connected_at is not None:
                            self._reconnect_count += 1
                        self._connected_at = time.time()

                    with self._lock:
                        self._sids.clear()
                        self._pending_subs.clear()
                        subs = list(self._active_subs)
                    for params in subs:
                        await self._subscribe_and_track(params)

                    self._connected.set()
                    logger.info("Feed connected to %s", self._ws_url)

                    async for raw_msg in ws:
                        self._dispatch(raw_msg)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._connected.clear()
                self._ws = None
                if not self._running:
                    break
                logger.warning(
                    "Feed disconnected (%s), reconnecting in %.1fs",
                    type(e).__name__,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

        self._connected.clear()
        self._ws = None

    def _auth_headers(self) -> dict[str, str]:
        timestamp, signature = self._client._sign_request("GET", _WS_SIGN_PATH)
        return {
            "KALSHI-ACCESS-KEY": self._client.api_key_id,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
        }

    def _next_id(self) -> int:
        return next(self._cmd_id_counter)

    async def _send_cmd(self, cmd: str, params: dict) -> int:
        cmd_id = self._next_id()
        if self._ws:
            msg = json.dumps({"id": cmd_id, "cmd": cmd, "params": params})
            await self._ws.send(msg)
            logger.debug("Sent %s: %s", cmd, msg)
        return cmd_id

    def _dispatch(self, raw: str | bytes) -> None:
        receive_time = time.time()
        with self._metrics_lock:
            self._last_message_at = receive_time
            self._message_count += 1

        msg_type, channel, parsed, data = _parse_message(raw)
        if msg_type is None:
            if not data:
                logger.warning("Malformed message: %.200s", raw)
            return

        if msg_type == "subscribed":
            inner = data.get("msg", {})
            sid = inner.get("sid") if isinstance(inner, dict) else None
            if sid is not None:
                with self._lock:
                    params = self._pending_subs.pop(data.get("id"), None)
                    if params is not None:
                        self._sids[sid] = params
            return

        payload = data.get("msg", data)
        if isinstance(payload, dict):
            parsed_ts = _parse_ts(payload.get("ts"))
            if parsed_ts is not None:
                with self._metrics_lock:
                    self._last_server_ts = parsed_ts

        handlers = self._handlers.get(channel)
        if not handlers:
            return

        for handler in handlers:
            try:
                handler(parsed)
            except Exception:
                logger.exception("Handler error on channel %s", channel)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

    def __repr__(self) -> str:
        status = "connected" if self.is_connected else "disconnected"
        n = len(self._active_subs)
        latency = self.latency_ms
        latency_str = f" latency={latency:.1f}ms" if latency is not None else ""
        return f"<Feed {status} subs={n} msgs={self._message_count}{latency_str}>"
