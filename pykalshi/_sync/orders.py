# AUTO-GENERATED from pykalshi/_async/orders.py — do not edit manually.
# Re-run: python scripts/generate_sync.py
from __future__ import annotations

import time
from decimal import Decimal
from typing import TYPE_CHECKING

from ..models import OrderModel
from ..enums import OrderStatus, Action, Side, OrderType, BookSide, OutcomeSide

if TYPE_CHECKING:
    from .client import KalshiClient

TERMINAL_STATUSES = frozenset({OrderStatus.CANCELED, OrderStatus.EXECUTED})


class Order:
    """Represents a Kalshi order.

    Key fields are exposed as typed properties for IDE support.
    All other OrderModel fields are accessible via attribute delegation.
    """

    def __init__(self, client: KalshiClient, data: OrderModel) -> None:
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
    def book_side(self) -> BookSide | None:
        """Canonical direction: ``bid`` is long yes, ``ask`` is long no."""
        return self.data.book_side

    @property
    def outcome_side(self) -> OutcomeSide | None:
        """Canonical direction as an outcome. Equivalent to :attr:`book_side`."""
        return self.data.outcome_side

    @property
    def is_bid(self) -> bool:
        return self.data.is_bid

    @property
    def is_ask(self) -> bool:
        return self.data.is_ask

    @property
    def action(self) -> Action | None:
        """Deprecated by Kalshi. Use :attr:`book_side`."""
        return self.data.action

    @property
    def side(self) -> Side | None:
        """Deprecated by Kalshi. Use :attr:`book_side`."""
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

    @property
    def average_fill_price_dollars(self) -> str | None:
        """Realised price of the fill this write ack reported, if any.

        Set from the create/amend ack only -- the read endpoints do not send it.
        """
        return self.data.average_fill_price_dollars

    @property
    def average_fee_paid_dollars(self) -> str | None:
        """Volume-weighted fee **per contract** on the fill this ack reported.

        Per the V2 spec this is an average per contract, not the total charged:
        multiply by fill_count_fp for the total. Present only when
        fill_count > 0.
        """
        return self.data.average_fee_paid_dollars

    @property
    def reduced_by_fp(self) -> str | None:
        """Contracts a cancel actually pulled off the book, if this came from one."""
        return self.data.reduced_by_fp

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

    def cancel(self) -> Order:
        """Cancel this order.

        Returns:
            Self with updated data (status will be CANCELED).
        """
        updated = self._client.portfolio.cancel_order(self.order_id)
        self._merge(updated.data)
        return self

    def amend(
        self,
        *,
        count_fp: str | None = None,
        price_dollars: str | None = None,
        yes_price_dollars: str | None = None,
        no_price_dollars: str | None = None,
    ) -> Order:
        """Amend this order's price or count.

        Args:
            count_fp: New total contract count (fixed-point string).
            price_dollars: New price, YES-denominated (canonical form).
            yes_price_dollars: New YES price (dollar string).
            no_price_dollars: New NO price (dollar string, converted to yes internally).

        Returns:
            Self with updated data.
        """
        # V2 amend requires a price. We already hold one, so pass it rather than
        # let amend_order re-fetch the order -- that is an extra round-trip on
        # every count-only amend, and it 404s if query-exchange has not yet
        # indexed a freshly placed order.
        if price_dollars is not None:
            if yes_price_dollars is not None or no_price_dollars is not None:
                raise ValueError(
                    "Specify price_dollars or yes/no_price_dollars, not both")
            yes_price_dollars = price_dollars

        if yes_price_dollars is None and no_price_dollars is None:
            yes_price_dollars = self.data.yes_price_dollars

        if count_fp is None:
            # `count` is the TOTAL (filled + desired remaining). Sending the
            # bare remaining count cancels whatever has already filled.
            filled = Decimal(self.data.fill_count_fp or "0")
            remaining = Decimal(self.data.remaining_count_fp or "0")
            count_fp = str(filled + remaining)

        updated = self._client.portfolio.amend_order(
            self.order_id,
            count_fp=count_fp,
            yes_price_dollars=yes_price_dollars,
            no_price_dollars=no_price_dollars,
            ticker=self.ticker,
            book_side=self.data.book_side,
            action=self.action,
            side=self.side,
        )
        self._merge(updated.data)
        return self

    def decrease(self, reduce_by_fp: str) -> Order:
        """Decrease the remaining count of this order.

        Args:
            reduce_by_fp: Number of contracts to reduce by (fixed-point string).

        Returns:
            Self with updated data.
        """
        updated = self._client.portfolio.decrease_order(self.order_id, reduce_by_fp)
        self._merge(updated.data)
        return self

    def refresh(self) -> Order:
        """Re-fetch this order's current state from the API.

        Returns:
            Self with updated data.
        """
        updated = self._client.portfolio.get_order(self.order_id)
        self.data = updated.data
        return self

    def wait_until_terminal(
        self, timeout: float = 30.0, poll_interval: float = 0.5
    ) -> Order:
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
            time.sleep(poll_interval)
            self.refresh()
        return self

    def __getattr__(self, name: str):
        return getattr(self.data, name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Order):
            return NotImplemented
        return self.data.order_id == other.data.order_id

    def __hash__(self) -> int:
        return hash(self.data.order_id)

    def __repr__(self) -> str:
        # Render the canonical direction. The legacy action/side pair flips
        # representation for one unchanged order (buy NO reads back as sell
        # YES), so a repr built from it appears to change on refresh.
        if self.book_side is not None:
            direction = self.book_side.value.upper()
        elif self.action and self.side:
            direction = f"{self.action.value.upper()} {self.side.value.upper()}"
        else:
            direction = "?"
        price = self.yes_price_dollars if self.yes_price_dollars is not None else self.no_price_dollars
        filled = self.fill_count_fp or "0"
        total = self.initial_count_fp or "0"
        return f"<Order {self.ticker} | {direction} @${price} | {filled}/{total} | {self.status.value}>"

    def _repr_html_(self) -> str:
        from .._repr import order_html
        return order_html(self)
