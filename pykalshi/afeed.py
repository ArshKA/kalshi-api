"""Native async WebSocket feed — no threads, no background loops."""

from __future__ import annotations

import asyncio
import itertools
import json
import logging
import time
from typing import Any, AsyncIterator, Callable, TYPE_CHECKING

from ._utils import normalize_tickers
from .feed import (
    _parse_message,
    _parse_ts,
    _WS_SIGN_PATH,
    DEFAULT_WS_BASE,
    DEMO_WS_BASE,
)

if TYPE_CHECKING:
    from .aclient import AsyncKalshiClient

logger = logging.getLogger(__name__)


class AsyncFeed:
    """Native async WebSocket feed for real-time market data.

    No threads, no background loops — just async/await.

    Usage:
        async with client.feed() as feed:
            @feed.on("ticker")
            def handle(msg):
                print(msg.market_ticker, msg.yes_bid_dollars)

            feed.subscribe("ticker", market_ticker="KXBTC-26JAN")

            async for msg in feed:
                pass  # handlers are called automatically

    Supports the same channels as Feed:
        ticker, trade, orderbook_delta, fill, market_positions,
        market_lifecycle_v2, order_group_updates

    Handlers may be sync or async — async handlers are awaited.
    """

    def __init__(self, client: AsyncKalshiClient) -> None:
        self._client = client
        self._handlers: dict[str, list[Callable]] = {}
        self._active_subs: list[dict] = []
        self._sids: dict[int, dict] = {}
        self._pending_subs: dict[int, dict] = {}
        self._ws: Any = None
        self._cmd_id_counter = itertools.count(1)
        self._connected = False

        self._connected_at: float | None = None
        self._last_message_at: float | None = None
        self._last_server_ts: int | None = None
        self._message_count: int = 0
        self._reconnect_count: int = 0

        self._ws_url = DEMO_WS_BASE if "demo" in client.api_base else DEFAULT_WS_BASE

    # --- Handler registration ---

    def on(self, channel: str, handler: Callable | None = None) -> Callable:
        """Register a handler for a channel. Works as decorator or direct call."""
        if handler is not None:
            self._handlers.setdefault(channel, []).append(handler)
            return handler

        def decorator(fn: Callable) -> Callable:
            self._handlers.setdefault(channel, []).append(fn)
            return fn

        return decorator

    # --- Subscription management ---

    def subscribe(
        self,
        channel: str,
        *,
        market_ticker: str | None = None,
        market_tickers: list[str] | None = None,
    ) -> None:
        """Subscribe to a channel. Sent on connect; replayed on reconnect."""
        params: dict[str, Any] = {"channels": [channel]}
        if market_ticker is not None:
            params["market_ticker"] = market_ticker.upper()
        if market_tickers is not None:
            params["market_tickers"] = normalize_tickers(market_tickers)
        if params in self._active_subs:
            return

        self._active_subs.append(params)

        if self._connected and self._ws:
            asyncio.create_task(self._subscribe_and_track(params))

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

        sids_to_remove = [sid for sid, p in self._sids.items() if p == target]
        for sid in sids_to_remove:
            del self._sids[sid]
        self._active_subs = [s for s in self._active_subs if s != target]

        if sids_to_remove and self._ws:
            asyncio.ensure_future(
                self._send_cmd("unsubscribe", {"sids": sids_to_remove})
            )

    # --- Connection lifecycle ---

    async def connect(self) -> None:
        """Connect to the WebSocket and replay subscriptions."""
        try:
            import websockets
        except ImportError:
            raise ImportError(
                "websockets is required for AsyncFeed. "
                "Install with: pip install websockets"
            )

        headers = self._auth_headers()
        self._ws = await websockets.connect(
            self._ws_url,
            additional_headers=headers,
            ping_interval=20,
            ping_timeout=10,
        )

        if self._connected_at is not None:
            self._reconnect_count += 1
        self._connected_at = time.time()
        self._connected = True

        self._sids.clear()
        self._pending_subs.clear()
        for params in self._active_subs:
            await self._subscribe_and_track(params)

        logger.info("AsyncFeed connected to %s", self._ws_url)

    async def disconnect(self) -> None:
        """Disconnect from the WebSocket."""
        self._connected = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

    # --- Async iteration with auto-reconnect ---

    async def __aiter__(self) -> AsyncIterator:
        """Iterate over messages with auto-reconnect.

        Yields parsed, typed messages. Handlers registered via .on()
        are called before each yield. Async handlers are awaited.
        """
        backoff = 0.5
        max_backoff = 30

        while True:
            try:
                if not self._connected or self._ws is None:
                    await self.connect()
                    backoff = 0.5

                async for raw in self._ws:
                    self._last_message_at = time.time()
                    self._message_count += 1

                    msg_type, channel, parsed, data = _parse_message(raw)
                    if msg_type is None:
                        continue

                    # Track subscription confirmations
                    if msg_type == "subscribed":
                        inner = data.get("msg", {})
                        sid = inner.get("sid") if isinstance(inner, dict) else None
                        if sid is not None:
                            params = self._pending_subs.pop(data.get("id"), None)
                            if params is not None:
                                self._sids[sid] = params
                        continue

                    # Extract server timestamp
                    payload = data.get("msg", data)
                    if isinstance(payload, dict):
                        parsed_ts = _parse_ts(payload.get("ts"))
                        if parsed_ts is not None:
                            self._last_server_ts = parsed_ts

                    # Call registered handlers
                    for handler in self._handlers.get(channel, []):
                        try:
                            result = handler(parsed)
                            if asyncio.iscoroutine(result):
                                await result
                        except Exception:
                            logger.exception(
                                "Handler error on channel %s", channel
                            )

                    yield parsed

            except asyncio.CancelledError:
                await self.disconnect()
                return
            except Exception as e:
                self._connected = False
                self._ws = None
                logger.warning(
                    "AsyncFeed disconnected (%s), reconnecting in %.1fs",
                    type(e).__name__,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

    # --- Context manager ---

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()

    # --- Properties ---

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def latency_ms(self) -> float | None:
        if self._last_server_ts is None or self._last_message_at is None:
            return None
        return self._last_message_at * 1000 - self._last_server_ts

    @property
    def messages_received(self) -> int:
        return self._message_count

    @property
    def uptime_seconds(self) -> float | None:
        if self._connected_at is None or not self._connected:
            return None
        return time.time() - self._connected_at

    @property
    def seconds_since_last_message(self) -> float | None:
        if self._last_message_at is None:
            return None
        return time.time() - self._last_message_at

    @property
    def reconnect_count(self) -> int:
        return self._reconnect_count

    # --- Internal helpers ---

    def _auth_headers(self) -> dict[str, str]:
        timestamp, signature = self._client._sign_request("GET", _WS_SIGN_PATH)
        return {
            "KALSHI-ACCESS-KEY": self._client.api_key_id,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
        }

    async def _send_cmd(self, cmd: str, params: dict) -> int:
        cmd_id = next(self._cmd_id_counter)
        if self._ws:
            msg = json.dumps({"id": cmd_id, "cmd": cmd, "params": params})
            await self._ws.send(msg)
            logger.debug("Sent %s: %s", cmd, msg)
        return cmd_id

    async def _subscribe_and_track(self, params: dict) -> None:
        cmd_id = await self._send_cmd("subscribe", params)
        self._pending_subs[cmd_id] = params

    def __repr__(self) -> str:
        status = "connected" if self._connected else "disconnected"
        n = len(self._active_subs)
        latency = self.latency_ms
        latency_str = f" latency={latency:.1f}ms" if latency is not None else ""
        return f"<AsyncFeed {status} subs={n} msgs={self._message_count}{latency_str}>"
