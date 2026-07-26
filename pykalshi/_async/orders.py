from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from ..models import OrderModel
from ..enums import OrderStatus, Action, Side, OrderType

if TYPE_CHECKING:
    from .client import AsyncKalshiClient

TERMINAL_STATUSES = frozenset({OrderStatus.CANCELED, OrderStatus.EXECUTED})


class AsyncOrder:
    """Represents a Kalshi order.

    Key fields are exposed as typed properties for IDE support.
    All other OrderModel fields are accessible via attribute delegation.
    """

    def __init__(self, client: AsyncKalshiClient, data: OrderModel) -> None:
        self._client = client
        self.data = data

    # --- Typed properties for core fields ---

    @property
    def order_id(self) -> str:
        return self.data.order_id

    @property
    def ticker(self) -> str:
        return self.data.ticker

    @property
    def status(self) -> OrderStatus:
        return self.data.status

    @property
    def action(self) -> Action | None:
        return self.data.action

    @property
    def side(self) -> Side | None:
        return self.data.side

    @property
    def type(self) -> OrderType | None:
        return self.data.type

    @property
    def yes_price_dollars(self) -> str | None:
        return self.data.yes_price_dollars

    @property
    def no_price_dollars(self) -> str | None:
        return self.data.no_price_dollars

    @property
    def initial_count_fp(self) -> str | None:
        return self.data.initial_count_fp

    @property
    def fill_count_fp(self) -> str | None:
        return self.data.fill_count_fp

    @property
    def remaining_count_fp(self) -> str | None:
        return self.data.remaining_count_fp

    @property
    def created_time(self) -> str | None:
        return self.data.created_time

    # --- Domain logic ---

    def _merge(self, updated: OrderModel) -> None:
        """Overlay a server response onto the current model.

        The V2 write endpoints return a thin acknowledgement (order_id, counts,
        ts_ms) rather than a full order, so a wholesale replacement would drop
        ticker/side/price from an object that already knew them. Only fields the
        response actually carries are overwritten.
        """
        merged = self.data.model_dump()
        for key, value in updated.model_dump().items():
            if value is not None and not (key == "ticker" and value == ""):
                merged[key] = value
        self.data = OrderModel.model_validate(merged)

    async def cancel(self) -> AsyncOrder:
        """Cancel this order.

        Returns:
            Self with updated data (status will be CANCELED).
        """
        updated = await self._client.portfolio.cancel_order(self.order_id)
        self._merge(updated.data)
        return self

    async def amend(
        self,
        *,
        count_fp: str | None = None,
        yes_price_dollars: str | None = None,
        no_price_dollars: str | None = None,
    ) -> AsyncOrder:
        """Amend this order's price or count.

        Args:
            count_fp: New total contract count (fixed-point string).
            yes_price_dollars: New YES price (dollar string).
            no_price_dollars: New NO price (dollar string, converted to yes internally).

        Returns:
            Self with updated data.
        """
        updated = await self._client.portfolio.amend_order(
            self.order_id,
            count_fp=count_fp or self.remaining_count_fp,
            yes_price_dollars=yes_price_dollars,
            no_price_dollars=no_price_dollars,
            ticker=self.ticker,
            action=self.action,
            side=self.side,
        )
        self._merge(updated.data)
        return self

    async def decrease(self, reduce_by_fp: str) -> AsyncOrder:
        """Decrease the remaining count of this order.

        Args:
            reduce_by_fp: Number of contracts to reduce by (fixed-point string).

        Returns:
            Self with updated data.
        """
        updated = await self._client.portfolio.decrease_order(self.order_id, reduce_by_fp)
        self._merge(updated.data)
        return self

    async def refresh(self) -> AsyncOrder:
        """Re-fetch this order's current state from the API.

        Returns:
            Self with updated data.
        """
        updated = await self._client.portfolio.get_order(self.order_id)
        self.data = updated.data
        return self

    async def wait_until_terminal(
        self, timeout: float = 30.0, poll_interval: float = 0.5
    ) -> AsyncOrder:
        """Block until order reaches a terminal state.

        Terminal states are: CANCELED, EXECUTED.

        Args:
            timeout: Maximum seconds to wait before raising TimeoutError.
            poll_interval: Seconds between refresh calls.

        Returns:
            Self with updated data.

        Raises:
            TimeoutError: If timeout is reached before terminal state.
        """
        deadline = time.monotonic() + timeout
        while self.status not in TERMINAL_STATUSES:
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Order {self.order_id} still {self.status.value} after {timeout}s"
                )
            await asyncio.sleep(poll_interval)
            await self.refresh()
        return self

    def __getattr__(self, name: str):
        return getattr(self.data, name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AsyncOrder):
            return NotImplemented
        return self.data.order_id == other.data.order_id

    def __hash__(self) -> int:
        return hash(self.data.order_id)

    def __repr__(self) -> str:
        action = self.action.value.upper() if self.action else "?"
        side = self.side.value.upper() if self.side else "?"
        price = self.yes_price_dollars if self.yes_price_dollars is not None else self.no_price_dollars
        filled = self.fill_count_fp or "0"
        total = self.initial_count_fp or "0"
        return f"<Order {self.ticker} | {action} {side} @${price} | {filled}/{total} | {self.status.value}>"

    def _repr_html_(self) -> str:
        from .._repr import order_html
        return order_html(self)
