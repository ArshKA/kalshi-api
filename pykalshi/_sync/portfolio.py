# AUTO-GENERATED from pykalshi/_async/portfolio.py — do not edit manually.
# Re-run: python scripts/generate_sync.py
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from .orders import Order
from ..enums import Action, Side, OrderStatus, TimeInForce, SelfTradePrevention, PositionCountFilter, BookSide
from ..dataframe import DataFrameList
from .._utils import (
    book_side_from_order_legacy,
    normalize_ticker,
    normalize_tickers,
    outcome_side_from_book_side,
)
from ..models import (
    OrderModel, BalanceModel, PositionModel, FillModel,
    SettlementModel, QueuePositionModel, OrderGroupModel,
    SubaccountModel, SubaccountBalanceModel, SubaccountTransferModel,
    SubaccountNettingModel,
)

if TYPE_CHECKING:
    from .client import KalshiClient
    from .markets import Market


class Portfolio:
    """Authenticated user's portfolio and trading operations."""

    def __init__(self, client: KalshiClient) -> None:
        self._client = client

    def get_balance(self) -> BalanceModel:
        """Get portfolio balance. Values are dollar strings."""
        data = self._client.get("/portfolio/balance")
        return BalanceModel.model_validate(data)

    def place_order(
        self,
        ticker: str | Market,
        action: Action | None = None,
        side: Side | None = None,
        count_fp: str | None = None,
        *,
        book_side: BookSide | str | None = None,
        price_dollars: str | None = None,
        yes_price_dollars: str | None = None,
        no_price_dollars: str | None = None,
        client_order_id: str | None = None,
        time_in_force: TimeInForce | None = TimeInForce.GTC,
        post_only: bool = False,
        reduce_only: bool = False,
        expiration_ts: int | None = None,
        buy_max_cost_dollars: str | None = None,
        self_trade_prevention: SelfTradePrevention | None = SelfTradePrevention.CANCEL_RESTING,
        order_group_id: str | None = None,
        subaccount: int | None = None,
        cancel_order_on_pause: bool | None = None,
    ) -> Order:
        """Place an order on a market.

        Args:
            ticker: Market ticker string or Market object.
            action: BUY or SELL.
            side: YES or NO.
            count_fp: Number of contracts (fixed-point string, e.g. "10.00").
            yes_price_dollars: Price as dollar string (e.g. "0.45").
            no_price_dollars: Price as dollar string. Converted to
                yes_price_dollars internally (yes = 1.00 - no).
            client_order_id: Idempotency key. Resubmitting returns existing order.
            time_in_force: GTC (default), IOC (immediate-or-cancel), FOK (fill-or-kill).
            post_only: If True, reject order if it would take liquidity.
            reduce_only: If True, only reduce existing position, never increase.
            expiration_ts: Unix timestamp when order auto-cancels.
            buy_max_cost_dollars: Maximum total cost (dollar string). Protects against slippage.
            self_trade_prevention: Behavior on self-cross (CANCEL_RESTING or CANCEL_INCOMING).
            order_group_id: Link to an order group for OCO/bracket strategies.
            subaccount: Subaccount number (0 for primary, 1-63 for subaccounts).
            cancel_order_on_pause: If True, cancel order if market is paused.
        """
        # Canonical form: book_side + price_dollars, both YES-denominated. The
        # legacy (action, side) + yes/no price remains supported and is mapped
        # onto the same wire body.
        if book_side is not None:
            if action is not None or side is not None:
                raise ValueError(
                    "Specify book_side or action/side, not both")
            bs = getattr(book_side, "value", book_side)
            if bs not in ("bid", "ask"):
                raise ValueError(f"book_side must be 'bid' or 'ask', got {book_side!r}")
            # bid == long yes == buy YES; ask == long no == buy NO at 1-price.
            action = Action.BUY
            side = Side.YES if bs == "bid" else Side.NO
            if price_dollars is not None:
                if yes_price_dollars is not None or no_price_dollars is not None:
                    raise ValueError(
                        "Specify price_dollars or yes/no_price_dollars, not both")
                # price_dollars is always the YES-leg price.
                yes_price_dollars = price_dollars
        elif price_dollars is not None:
            raise ValueError("price_dollars requires book_side")
        if action is None or side is None:
            raise ValueError("place_order requires either book_side or action+side")
        if count_fp is None:
            raise ValueError("place_order requires count_fp")

        # Extract market structure for validation when a Market object is passed
        pls = None
        fte = None
        if not isinstance(ticker, str):
            pls = getattr(ticker, 'price_level_structure', None)
            fte = getattr(ticker, 'fractional_trading_enabled', None)

        order_data = self._build_order_data(
            ticker, action, side, count_fp,
            yes_price_dollars=yes_price_dollars, no_price_dollars=no_price_dollars,
            client_order_id=client_order_id, time_in_force=time_in_force,
            post_only=post_only, reduce_only=reduce_only,
            expiration_ts=expiration_ts, buy_max_cost_dollars=buy_max_cost_dollars,
            self_trade_prevention=self_trade_prevention,
            order_group_id=order_group_id, subaccount=subaccount,
            cancel_order_on_pause=cancel_order_on_pause,
            price_level_structure=pls,
            fractional_trading_enabled=fte,
        )
        response = self._client.post("/portfolio/events/orders", order_data)
        model = self._order_from_v2_ack(
            response,
            ticker=order_data.get("ticker"),
            status=self._v2_status_from_ack(response),
            book_side=order_data.get("side"),
            action=action,
            side=side,
            yes_price_dollars=order_data.get("price"),
        )
        return Order(self._client, model)

    def cancel_order(self, order_id: str, *, subaccount: int | None = None) -> Order:
        """Cancel a resting order.

        Args:
            order_id: ID of the order to cancel.
            subaccount: Subaccount number (0 for primary, 1-63 for subaccounts).

        Returns:
            The canceled Order with updated status.
        """
        endpoint = f"/portfolio/events/orders/{order_id}"
        if subaccount is not None:
            endpoint += f"?subaccount={subaccount}"
        response = self._client.delete(endpoint)
        model = self._order_from_v2_ack(
            response, ticker=response.get("ticker"), status=OrderStatus.CANCELED
        )
        return Order(self._client, model)

    def amend_order(
        self,
        order_id: str,
        *,
        count_fp: str | None = None,
        price_dollars: str | None = None,
        yes_price_dollars: str | None = None,
        no_price_dollars: str | None = None,
        subaccount: int | None = None,
        # Required by the API but fetched from the existing order if omitted
        ticker: str | None = None,
        book_side: BookSide | str | None = None,
        action: Action | None = None,
        side: Side | None = None,
    ) -> Order:
        """Amend a resting order's price or count.

        Args:
            order_id: ID of the order to amend.
            price_dollars: New price, YES-denominated (canonical form).
            count_fp: New TOTAL contract count -- already-filled plus the
                remaining size you want resting afterwards. This is the API's
                semantics, not "the new resting size"; passing the remaining
                size alone silently shrinks a partially filled order.
            yes_price_dollars: New YES price (dollar string).
            no_price_dollars: New NO price (dollar string). Converted internally.
            subaccount: Subaccount number (0 for primary, 1-63 for subaccounts).
            ticker: Market ticker (fetched from the order if not provided).
            book_side: ``bid``/``ask``. Preferred over action/side; fetched
                from the order if not provided.
            action: Deprecated. Legacy order action.
            side: Deprecated. Legacy order side.
        """
        # price_dollars is the canonical, YES-denominated price.
        if price_dollars is not None:
            if yes_price_dollars is not None or no_price_dollars is not None:
                raise ValueError(
                    "Specify price_dollars or yes/no_price_dollars, not both")
            yes_price_dollars = price_dollars

        if count_fp is None and yes_price_dollars is None and no_price_dollars is None:
            raise ValueError("Must specify at least one amend field")

        if yes_price_dollars is not None and no_price_dollars is not None:
            raise ValueError("Specify yes_price_dollars or no_price_dollars, not both")

        if no_price_dollars is not None:
            yes_price_dollars = str(Decimal("1") - Decimal(no_price_dollars))

        ticker = normalize_ticker(ticker)

        # AmendOrderV2Request requires ticker, side, price and count, so fetch
        # the original order for anything the caller left out (including price,
        # which the v1 body did not need).
        # Resolve book_side locally when the caller supplied the legacy pair --
        # fetching the order just to recompute something we can derive costs a
        # round-trip, and races query-exchange right after a place.
        if book_side is None:
            book_side = book_side_from_order_legacy(action, side)

        if (ticker is None or book_side is None
                or count_fp is None or yes_price_dollars is None):
            original = self.get_order(order_id)
            ticker = ticker or original.ticker
            book_side = book_side or original.data.book_side
            if book_side is None:
                # Only reached on a payload with no canonical field.
                book_side = book_side_from_order_legacy(
                    action or original.action, side or original.side)
            if count_fp is None:
                # `count` is the TOTAL, so preserve what has already filled --
                # sending the bare remaining count cancels the filled portion.
                filled = Decimal(original.data.fill_count_fp or "0")
                remaining = Decimal(original.data.remaining_count_fp or "0")
                count_fp = str(filled + remaining)
            if yes_price_dollars is None:
                yes_price_dollars = original.data.yes_price_dollars
                if yes_price_dollars is None and original.data.no_price_dollars is not None:
                    yes_price_dollars = str(
                        Decimal("1") - Decimal(original.data.no_price_dollars)
                    )

        if yes_price_dollars is None:
            raise ValueError(
                "amend requires a price; none was supplied and none could be "
                "resolved from the existing order"
            )
        if book_side is None:
            book_side = book_side_from_order_legacy(action, side)
        if book_side is None:
            raise ValueError(
                "amend requires a book_side; none was supplied and none could "
                "be resolved from the existing order"
            )

        body: dict = {
            "ticker": ticker,
            "side": getattr(book_side, "value", book_side),
            "price": f"{Decimal(yes_price_dollars):.4f}",
            "count": count_fp,
        }
        # Per the AmendOrderV2 spec, subaccount rides as a query parameter,
        # not a body field (matching cancel/decrease).
        endpoint = f"/portfolio/events/orders/{order_id}/amend"
        if subaccount is not None:
            endpoint += f"?subaccount={subaccount}"

        response = self._client.post(endpoint, body)
        model = self._order_from_v2_ack(
            response,
            ticker=ticker,
            status=self._v2_status_from_ack(response),
            book_side=body["side"],
            yes_price_dollars=body["price"],
        )
        return Order(self._client, model)

    def decrease_order(
        self, order_id: str, reduce_by_fp: str, *, subaccount: int | None = None
    ) -> Order:
        """Decrease the remaining count of a resting order.

        Args:
            order_id: ID of the order to decrease.
            reduce_by_fp: Number of contracts to reduce by (fixed-point string).
            subaccount: Subaccount number (0 for primary, 1-63 for subaccounts).
        """
        endpoint = f"/portfolio/events/orders/{order_id}/decrease"
        if subaccount is not None:
            endpoint += f"?subaccount={subaccount}"
        response = self._client.post(endpoint, {"reduce_by": reduce_by_fp})
        model = self._order_from_v2_ack(
            response,
            ticker=response.get("ticker"),
            status=self._v2_status_from_ack(response),
        )
        return Order(self._client, model)

    def get_orders(
        self,
        *,
        status: OrderStatus | None = None,
        ticker: str | None = None,
        event_ticker: str | None = None,
        min_ts: int | None = None,
        max_ts: int | None = None,
        limit: int = 100,
        cursor: str | None = None,
        fetch_all: bool = False,
        **extra_params,
    ) -> DataFrameList[Order]:
        """Get list of orders.

        Args:
            status: Filter by order status (resting, canceled, executed).
            ticker: Filter by market ticker.
            event_ticker: Filter by event ticker (supports comma-separated, max 10).
            min_ts: Filter orders after this Unix timestamp.
            max_ts: Filter orders before this Unix timestamp.
            limit: Maximum results per page (default 100, max 200).
            cursor: Pagination cursor for fetching next page.
            fetch_all: If True, automatically fetch all pages.
            **extra_params: Additional API parameters (e.g., subaccount).
        """
        params = {
            "limit": limit,
            "status": status.value if status is not None else None,
            "ticker": normalize_ticker(ticker),
            "event_ticker": normalize_ticker(event_ticker),
            "min_ts": min_ts,
            "max_ts": max_ts,
            "cursor": cursor,
            **extra_params,
        }
        data = self._client.paginated_get("/portfolio/orders", "orders", params, fetch_all)
        return DataFrameList(Order(self._client, OrderModel.model_validate(d)) for d in data)

    def get_order(self, order_id: str) -> Order:
        """Get a single order by ID."""
        response = self._client.get(f"/portfolio/orders/{order_id}")
        model = OrderModel.model_validate(response["order"])
        return Order(self._client, model)

    def get_positions(
        self,
        *,
        ticker: str | None = None,
        event_ticker: str | None = None,
        count_filter: PositionCountFilter | None = None,
        limit: int = 100,
        cursor: str | None = None,
        fetch_all: bool = False,
        **extra_params,
    ) -> DataFrameList[PositionModel]:
        """Get portfolio positions.

        Args:
            ticker: Filter by specific market ticker.
            event_ticker: Filter by event ticker (supports comma-separated, max 10).
            count_filter: Filter positions with non-zero values (POSITION or TOTAL_TRADED).
            limit: Maximum positions per page (default 100, max 1000).
            cursor: Pagination cursor for fetching next page.
            fetch_all: If True, automatically fetch all pages.
            **extra_params: Additional API parameters (e.g., subaccount).
        """
        params = {
            "limit": limit,
            "ticker": normalize_ticker(ticker),
            "event_ticker": normalize_ticker(event_ticker),
            "count_filter": count_filter.value if count_filter is not None else None,
            "cursor": cursor,
            **extra_params,
        }
        data = self._client.paginated_get("/portfolio/positions", "market_positions", params, fetch_all)
        return DataFrameList(PositionModel.model_validate(p) for p in data)

    def get_fills(
        self,
        *,
        ticker: str | None = None,
        order_id: str | None = None,
        min_ts: int | None = None,
        max_ts: int | None = None,
        limit: int = 100,
        cursor: str | None = None,
        fetch_all: bool = False,
        **extra_params,
    ) -> DataFrameList[FillModel]:
        """Get trade fills (executed trades).

        Args:
            ticker: Filter by market ticker.
            order_id: Filter by specific order ID.
            min_ts: Minimum timestamp (Unix seconds).
            max_ts: Maximum timestamp (Unix seconds).
            limit: Maximum fills per page (default 100, max 200).
            cursor: Pagination cursor for fetching next page.
            fetch_all: If True, automatically fetch all pages.
            **extra_params: Additional API parameters (e.g., subaccount).
        """
        params = {
            "limit": limit,
            "ticker": normalize_ticker(ticker),
            "order_id": order_id,
            "min_ts": min_ts,
            "max_ts": max_ts,
            "cursor": cursor,
            **extra_params,
        }
        data = self._client.paginated_get("/portfolio/fills", "fills", params, fetch_all)
        return DataFrameList(FillModel.model_validate(f) for f in data)

    # --- Batch Operations ---

    def batch_place_orders(self, orders: list[dict]) -> DataFrameList[Order]:
        """Place multiple orders atomically.

        Args:
            orders: List of order dicts with keys: ticker, action, side, count_fp,
                    yes_price_dollars/no_price_dollars, and optional advanced params.

        Example:
            orders = [
                {"ticker": "KXBTC", "action": "buy", "side": "yes", "count_fp": "10.00", "yes_price_dollars": "0.45"},
                {"ticker": "KXBTC", "action": "buy", "side": "no", "count_fp": "10.00", "no_price_dollars": "0.45"},
            ]
            results = portfolio.batch_place_orders(orders)
        """
        prepared = self._build_batch_orders(orders)
        response = self._client.post("/portfolio/events/orders/batched", {"orders": prepared})
        return DataFrameList(
            Order(self._client, m)
            for m in self._orders_from_v2_batch(response, prepared, orders)
        )

    def batch_cancel_orders(self, order_ids: list[str]) -> DataFrameList[Order]:
        """Cancel multiple orders atomically.

        Args:
            order_ids: List of order IDs to cancel (max 20).

        Returns:
            The canceled Orders with updated status.
        """
        orders = [{"order_id": oid} for oid in order_ids]
        response = self._client.delete("/portfolio/events/orders/batched", {"orders": orders})
        return DataFrameList(
            Order(self._client, m) for m in self._orders_from_v2_batch(response)
        )

    # --- Queue Position ---

    def get_queue_position(self, order_id: str) -> QueuePositionModel:
        """Get queue position for a single resting order."""
        response = self._client.get(f"/portfolio/orders/{order_id}/queue_position")
        return QueuePositionModel(
            order_id=order_id,
            queue_position_fp=response.get("queue_position_fp", "0.00"),
        )

    def get_queue_positions(
        self,
        *,
        market_tickers: list[str] | None = None,
        event_ticker: str | None = None,
    ) -> DataFrameList[QueuePositionModel]:
        """Get queue positions for all resting orders."""
        params: dict = {}
        if market_tickers:
            params["market_tickers"] = ",".join(normalize_tickers(market_tickers))
        if event_ticker:
            params["event_ticker"] = normalize_ticker(event_ticker)

        endpoint = "/portfolio/orders/queue_positions"
        if params:
            endpoint = f"{endpoint}?{urlencode(params)}"

        response = self._client.get(endpoint)
        return DataFrameList(
            QueuePositionModel.model_validate(qp)
            for qp in (response.get("queue_positions") or [])
        )

    # --- Settlements ---

    def get_settlements(
        self,
        *,
        ticker: str | None = None,
        event_ticker: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
        fetch_all: bool = False,
        **extra_params,
    ) -> DataFrameList[SettlementModel]:
        """Get settlement records for resolved positions."""
        params = {
            "limit": limit,
            "ticker": normalize_ticker(ticker),
            "event_ticker": normalize_ticker(event_ticker),
            "cursor": cursor,
            **extra_params,
        }
        data = self._client.paginated_get("/portfolio/settlements", "settlements", params, fetch_all)
        return DataFrameList(SettlementModel.model_validate(s) for s in data)

    def get_resting_order_value(self) -> str:
        """Get total value of all resting orders as dollar string.

        NOTE: This endpoint is FCM-only (institutional accounts).
        """
        response = self._client.get("/portfolio/summary/total_resting_order_value")
        return response.get("total_resting_order_value_dollars", "0")

    # --- Order Groups (Contract Rate Limiting) ---

    def create_order_group(self, contracts_limit_fp: str) -> OrderGroupModel:
        """Create an order group for rate-limiting contract matches.

        Args:
            contracts_limit_fp: Maximum contracts (fixed-point string) that can be
                matched in a rolling 15-second window.

        Returns:
            Created OrderGroupModel.
        """
        body: dict = {"contracts_limit_fp": contracts_limit_fp}
        response = self._client.post("/portfolio/order_groups/create", body)
        return OrderGroupModel.model_validate(response)

    def get_order_group(self, order_group_id: str) -> OrderGroupModel:
        """Get an order group by ID."""
        response = self._client.get(f"/portfolio/order_groups/{order_group_id}")
        response["id"] = order_group_id
        return OrderGroupModel.model_validate(response)

    def trigger_order_group(self, order_group_id: str) -> None:
        """Manually trigger an order group, cancelling all orders in it."""
        self._client.put(f"/portfolio/order_groups/{order_group_id}/trigger", {})

    def get_order_groups(self) -> DataFrameList[OrderGroupModel]:
        """List all order groups."""
        response = self._client.get("/portfolio/order_groups")
        return DataFrameList(
            OrderGroupModel.model_validate(og)
            for og in (response.get("order_groups") or [])
        )

    def reset_order_group(self, order_group_id: str) -> None:
        """Reset matched contract counter for an order group."""
        self._client.put(f"/portfolio/order_groups/{order_group_id}/reset", {})

    def update_order_group_limit(self, order_group_id: str, contracts_limit_fp: str) -> None:
        """Update the contracts limit for an order group.

        Args:
            order_group_id: ID of the order group.
            contracts_limit_fp: New maximum contracts (fixed-point string).
        """
        body: dict = {"contracts_limit_fp": contracts_limit_fp}
        self._client.put(f"/portfolio/order_groups/{order_group_id}/limit", body)

    # --- Subaccounts ---

    def create_subaccount(
        self, *, exchange_index: int | None = None
    ) -> SubaccountModel:
        """Create a new numbered subaccount.

        Requires the Advanced API tier or above; without it the API returns
        403 ``subaccount_creation_requires_advanced_api_usage_level``.
        Subaccounts are numbered sequentially starting from 1, with a maximum
        of 63 numbered subaccounts (64 including the primary account 0).

        Args:
            exchange_index: Exchange shard to create the subaccount on.
                Defaults to 0 (currently the only supported value).

        Returns:
            SubaccountModel with the assigned ``subaccount_number``.
        """
        body: dict = {}
        if exchange_index is not None:
            body["exchange_index"] = exchange_index
        response = self._client.post("/portfolio/subaccounts", body)
        return SubaccountModel.model_validate(response)

    def transfer_between_subaccounts(
        self,
        from_subaccount: int,
        to_subaccount: int,
        amount_cents: int,
        *,
        client_transfer_id: str | None = None,
        exchange_index: int | None = None,
    ) -> str:
        """Transfer funds between your own subaccounts.

        Transfers are idempotent on ``client_transfer_id``: retrying with the
        same ID returns HTTP 409 instead of applying the transfer twice. Pass
        an explicit ID when you need safe retries; otherwise a fresh UUID4 is
        generated for each call.

        Args:
            from_subaccount: Source subaccount number (0 for primary,
                1-63 for numbered subaccounts).
            to_subaccount: Destination subaccount number (0 for primary,
                1-63 for numbered subaccounts).
            amount_cents: Amount to transfer in cents.
            client_transfer_id: Idempotency key (UUID string). Auto-generated
                if not supplied.
            exchange_index: Exchange shard to apply the transfer on.
                Defaults to 0 (currently the only supported value).

        Returns:
            The ``client_transfer_id`` used, for idempotent retries and
            matching against get_subaccount_transfers().
        """
        if client_transfer_id is None:
            client_transfer_id = str(uuid.uuid4())
        body: dict = {
            "client_transfer_id": client_transfer_id,
            "from_subaccount": from_subaccount,
            "to_subaccount": to_subaccount,
            "amount_cents": amount_cents,
        }
        if exchange_index is not None:
            body["exchange_index"] = exchange_index
        # Success response body is empty per the spec.
        self._client.post("/portfolio/subaccounts/transfer", body)
        return client_transfer_id

    def get_subaccount_balances(self) -> DataFrameList[SubaccountBalanceModel]:
        """Get balances for all subaccounts, including the primary account (0)."""
        response = self._client.get("/portfolio/subaccounts/balances")
        return DataFrameList(
            SubaccountBalanceModel.model_validate(b)
            for b in (response.get("subaccount_balances") or [])
        )

    def get_subaccount_transfers(
        self,
        *,
        limit: int = 100,
        cursor: str | None = None,
        fetch_all: bool = False,
        **extra_params,
    ) -> DataFrameList[SubaccountTransferModel]:
        """Get transfer history between subaccounts (paginated)."""
        params = {"limit": limit, "cursor": cursor, **extra_params}
        data = self._client.paginated_get(
            "/portfolio/subaccounts/transfers", "transfers", params, fetch_all
        )
        return DataFrameList(SubaccountTransferModel.model_validate(t) for t in data)

    def get_subaccount_netting(self) -> DataFrameList[SubaccountNettingModel]:
        """Get the netting-enabled settings for all subaccounts."""
        response = self._client.get("/portfolio/subaccounts/netting")
        return DataFrameList(
            SubaccountNettingModel.model_validate(c)
            for c in (response.get("netting_configs") or [])
        )

    def update_subaccount_netting(
        self, subaccount_number: int, enabled: bool
    ) -> None:
        """Update the netting-enabled setting for a specific subaccount.

        Args:
            subaccount_number: Subaccount number (0 for primary, 1-63 for
                subaccounts).
            enabled: Whether netting is enabled for this subaccount.
        """
        self._client.put(
            "/portfolio/subaccounts/netting",
            {"subaccount_number": subaccount_number, "enabled": enabled},
        )

    # --- Shared validation helpers ---

    @staticmethod
    def _validate_tick_size(price: Decimal, price_level_structure: str) -> None:
        """Validate that price aligns to the market's tick size.

        Raises ValueError if the price is not on a valid tick boundary.
        """
        if price_level_structure == "linear_cent":
            # $0.00-$1.00, tick $0.01
            tick = Decimal("0.01")
            if price % tick != 0:
                raise ValueError(
                    f"Price {price} is not on a valid tick for linear_cent "
                    f"(tick size $0.01)"
                )
        elif price_level_structure == "deci_cent":
            # $0.00-$1.00, tick $0.001
            tick = Decimal("0.001")
            if price % tick != 0:
                raise ValueError(
                    f"Price {price} is not on a valid tick for deci_cent "
                    f"(tick size $0.001)"
                )
        elif price_level_structure == "tapered_deci_cent":
            # $0.00-$0.10: tick $0.001, $0.10-$0.90: tick $0.01, $0.90-$1.00: tick $0.001
            if price <= Decimal("0.10") or price >= Decimal("0.90"):
                tick = Decimal("0.001")
            else:
                tick = Decimal("0.01")
            if price % tick != 0:
                raise ValueError(
                    f"Price {price} is not on a valid tick for tapered_deci_cent "
                    f"(tick size ${tick} in this price range)"
                )

    @staticmethod
    def _validate_fractional(count_fp: str, fractional_enabled: bool) -> None:
        """Validate count_fp is whole when fractional trading is disabled."""
        if not fractional_enabled:
            d = Decimal(count_fp)
            if d != int(d):
                raise ValueError(
                    f"Fractional trading is not enabled for this market. "
                    f"count_fp must be a whole number, got {count_fp}"
                )

    @staticmethod
    def _v2_book_side(action: Action | str | None, side: Side | str | None) -> str:
        """Map an ORDER's legacy (action, side) onto the V2 single-book side.

        The V2 book is YES-denominated, so buying NO is the same as selling YES.
        Accepts enums or their raw string values (batch payloads use strings).

        ORDER SURFACE ONLY. Fills use a different convention -- there ``side``
        is the outcome acquired and ``action`` carries no sign -- so applying
        this to a fill inverts every ``sell`` row. Use ``FillModel.book_side``,
        which the server supplies directly.
        """
        a = action.value if isinstance(action, Action) else action
        sd = side.value if isinstance(side, Side) else side
        if sd == Side.YES.value:
            return "bid" if a == Action.BUY.value else "ask"
        if sd == Side.NO.value:
            return "ask" if a == Action.BUY.value else "bid"
        raise ValueError(f"Unsupported action/side combination: {action!r}/{side!r}")

    @staticmethod
    def _v2_status_from_ack(response: dict) -> OrderStatus:
        remaining = response.get("remaining_count")
        try:
            if remaining is not None and Decimal(str(remaining)) <= 0:
                return OrderStatus.EXECUTED
        except (ArithmeticError, ValueError):
            pass
        return OrderStatus.RESTING

    @staticmethod
    def _order_from_v2_ack(
        response: dict,
        *,
        ticker: str | None,
        status: OrderStatus,
        book_side: BookSide | str | None = None,
        action: Action | None = None,
        side: Side | None = None,
        yes_price_dollars: str | None = None,
    ) -> OrderModel:
        """Build an OrderModel from a V2 write acknowledgement.

        V2 write endpoints return a thin ack, not the full order object the v1
        endpoints nested under a top-level "order" key. CreateOrderV2Response is
        {order_id, client_order_id?, fill_count, remaining_count, ts_ms,
        average_fill_price?}; cancel and amend return even less.

        Rather than spend a round-trip re-fetching the order -- unacceptable for
        latency-sensitive callers that requote continuously -- reconstruct the
        model from the ack plus the request context the caller already supplied.
        This preserves the documented `-> Order` return contract. Fields that
        neither the ack nor the caller provides are left unset.

        action/side echo what the caller asked for. The V2 book is
        YES-denominated, so the exchange normalises a buy of NO into a sell of
        YES: an order placed as (buy, NO, no_price 0.01) reads back from
        GET /portfolio/orders/{id} as (sell, YES, yes_price 0.99). Both describe
        the same resting order at the same price.
        """
        data: dict = {
            "order_id": response["order_id"],
            "ticker": ticker or "",
            "status": status,
        }
        if response.get("client_order_id") is not None:
            data["client_order_id"] = response["client_order_id"]
        if response.get("fill_count") is not None:
            data["fill_count_fp"] = response["fill_count"]
        if response.get("remaining_count") is not None:
            data["remaining_count_fp"] = response["remaining_count"]
        # Canonical direction: the caller always knows it -- it is exactly what
        # went on the wire -- so a synthesised order carries the same fields a
        # fetched one does.
        bs = getattr(book_side, "value", book_side)
        if bs is None:
            bs = book_side_from_order_legacy(action, side)
        if bs is not None:
            data["book_side"] = bs
            data["outcome_side"] = outcome_side_from_book_side(bs)
        if action is not None:
            data["action"] = action.value if isinstance(action, Action) else action
        if side is not None:
            data["side"] = side.value if isinstance(side, Side) else side
        if yes_price_dollars is not None:
            data["yes_price_dollars"] = yes_price_dollars
        return OrderModel.model_validate(data)

    @staticmethod
    def _orders_from_v2_batch(
        response: dict,
        prepared: list[dict] | None = None,
        originals: list[dict] | None = None,
    ) -> list[OrderModel]:
        """Parse a batched response, tolerating the thin-ack item shape as well
        as the legacy {"order": {...}} wrapper.

        Like the single-order acks, batch acks carry no ticker/price/side, so the
        request that produced each one is folded back in. Items are matched by
        client_order_id where the caller supplied one, else positionally.
        """
        items = response.get("orders") or []
        prepared = prepared or []
        originals = originals or []
        by_coid = {
            p.get("client_order_id"): i
            for i, p in enumerate(prepared)
            if p.get("client_order_id")
        }

        models: list[OrderModel] = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            legacy = item.get("order")
            if isinstance(legacy, dict):
                models.append(OrderModel.model_validate(legacy))
                continue
            if item.get("order_id") is None:
                continue

            i = by_coid.get(item.get("client_order_id"), idx)
            req = prepared[i] if i < len(prepared) else {}
            orig = originals[i] if i < len(originals) else {}

            entry: dict = {
                "order_id": item["order_id"],
                "ticker": item.get("ticker") or req.get("ticker") or "",
                "status": item.get("status")
                or Portfolio._v2_status_from_ack(item),
            }
            bs = item.get("book_side") or req.get("side")
            if bs:
                entry["book_side"] = bs
                entry["outcome_side"] = outcome_side_from_book_side(bs)
            # The V2 request price is already YES-denominated.
            if req.get("price") is not None:
                entry["yes_price_dollars"] = req["price"]
            if orig.get("action") is not None:
                entry["action"] = orig["action"]
            if orig.get("side") is not None:
                entry["side"] = orig["side"]
            if item.get("client_order_id") is not None:
                entry["client_order_id"] = item["client_order_id"]
            if item.get("remaining_count") is not None:
                entry["remaining_count_fp"] = item["remaining_count"]
            if item.get("fill_count") is not None:
                entry["fill_count_fp"] = item["fill_count"]
            models.append(OrderModel.model_validate(entry))
        return models

    @staticmethod
    def _build_order_data(
        ticker,
        action: Action,
        side: Side,
        count_fp: str,
        *,
        yes_price_dollars=None,
        no_price_dollars=None,
        client_order_id=None,
        time_in_force=None,
        post_only=False,
        reduce_only=False,
        expiration_ts=None,
        buy_max_cost_dollars=None,
        self_trade_prevention=None,
        order_group_id=None,
        subaccount=None,
        cancel_order_on_pause=None,
        price_level_structure=None,
        fractional_trading_enabled=None,
    ) -> dict:
        """Build and validate order data dict. No I/O.

        If price_level_structure is provided, validates tick size alignment.
        If fractional_trading_enabled is provided (False), validates count_fp is whole.
        """
        if yes_price_dollars is not None and no_price_dollars is not None:
            raise ValueError("Specify yes_price_dollars or no_price_dollars, not both")

        if yes_price_dollars is None and no_price_dollars is None:
            raise ValueError("Limit orders require yes_price_dollars or no_price_dollars")

        if no_price_dollars is not None:
            yes_price = Decimal("1") - Decimal(no_price_dollars)
        else:
            yes_price = Decimal(yes_price_dollars)

        # Validate tick size if market structure is known
        if price_level_structure:
            Portfolio._validate_tick_size(yes_price, price_level_structure)

        # Validate fractional trading
        if fractional_trading_enabled is not None:
            Portfolio._validate_fractional(count_fp, fractional_trading_enabled)

        ticker_str = ticker.upper() if isinstance(ticker, str) else ticker.ticker

        order_data: dict = {
            "ticker": ticker_str,
            "side": Portfolio._v2_book_side(action, side),
            "count": count_fp,
            "price": f"{yes_price:.4f}",
        }
        # time_in_force and self_trade_prevention_type are REQUIRED by
        # CreateOrderV2Request; fall back to the documented defaults rather than
        # omitting them and getting a 400 missing_parameters.
        order_data["time_in_force"] = (
            time_in_force.value if time_in_force is not None else TimeInForce.GTC.value
        )
        order_data["self_trade_prevention_type"] = (
            self_trade_prevention.value
            if self_trade_prevention is not None
            else SelfTradePrevention.CANCEL_RESTING.value
        )
        if client_order_id is not None:
            order_data["client_order_id"] = client_order_id
        if post_only:
            order_data["post_only"] = True
        if reduce_only:
            order_data["reduce_only"] = True
        if expiration_ts is not None:
            order_data["expiration_time"] = expiration_ts
        if buy_max_cost_dollars is not None:
            order_data["buy_max_cost_dollars"] = buy_max_cost_dollars
        if order_group_id is not None:
            order_data["order_group_id"] = order_group_id
        if subaccount is not None:
            order_data["subaccount"] = subaccount
        if cancel_order_on_pause is not None:
            order_data["cancel_order_on_pause"] = cancel_order_on_pause
        return order_data

    @staticmethod
    def _build_batch_orders(orders: list[dict]) -> list[dict]:
        """Validate and prepare batch orders for BatchCreateOrdersV2Request. No I/O.

        Accepts either shape per item:

          canonical -- {"ticker", "book_side": "bid"|"ask", "price_dollars",
                        "count_fp"|"count"}
          legacy    -- {"ticker", "action", "side", "yes_price_dollars" or
                        "no_price_dollars", "count_fp"}

        Both convert to the same V2 item (single-book bid/ask side,
        YES-denominated price, count).
        """
        prepared = []
        for order in orders:
            o = dict(order)

            # Canonical item: normalise into the legacy names the rest of this
            # function already understands, then let it flow through.
            if "book_side" in o:
                if "action" in o or "side" in o:
                    raise ValueError(
                        "Batch item: specify book_side or action/side, not both")
                bs = o.pop("book_side")
                bs = getattr(bs, "value", bs)
                if bs not in ("bid", "ask"):
                    raise ValueError(
                        f"Batch item: book_side must be 'bid' or 'ask', got {bs!r}")
                o["action"] = "buy"
                o["side"] = "yes" if bs == "bid" else "no"
                if "price_dollars" in o:
                    if "yes_price_dollars" in o or "no_price_dollars" in o:
                        raise ValueError(
                            "Batch item: specify price_dollars or yes/no_price_dollars,"
                            " not both")
                    # price_dollars is the YES leg; for an ask the legacy path
                    # expects the NO leg, so convert.
                    px = Decimal(o.pop("price_dollars"))
                    if bs == "bid":
                        o["yes_price_dollars"] = str(px)
                    else:
                        o["no_price_dollars"] = str(Decimal("1") - px)
            elif "price_dollars" in o:
                raise ValueError("Batch item: price_dollars requires book_side")

            if "yes_price_dollars" in o and "no_price_dollars" in o:
                raise ValueError("Specify yes_price_dollars or no_price_dollars, not both")
            if "yes_price_dollars" not in o and "no_price_dollars" not in o:
                raise ValueError("Limit orders require yes_price_dollars or no_price_dollars")
            if "no_price_dollars" in o:
                yes_price = Decimal("1") - Decimal(o.pop("no_price_dollars"))
            else:
                yes_price = Decimal(o.pop("yes_price_dollars"))
            # "type" is not part of the V2 request shape
            o.pop("type", None)

            item: dict = {
                "ticker": o.pop("ticker"),
                "side": Portfolio._v2_book_side(o.pop("action", None), o.pop("side", None)),
                "count": o.pop("count_fp", None) or o.pop("count", None),
                "price": f"{yes_price:.4f}",
            }
            item.setdefault("time_in_force", TimeInForce.GTC.value)
            item.setdefault("self_trade_prevention_type",
                            SelfTradePrevention.CANCEL_RESTING.value)
            if "expiration_ts" in o:
                o["expiration_time"] = o.pop("expiration_ts")
            # pass through any remaining V2-valid fields (client_order_id,
            # time_in_force, self_trade_prevention_type, exchange_index, ...)
            item.update(o)
            prepared.append(item)
        return prepared
