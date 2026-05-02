from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from .orders import AsyncOrder
from ..enums import Action, Side, OrderStatus, TimeInForce, SelfTradePrevention, PositionCountFilter
from ..dataframe import DataFrameList
from .._utils import normalize_ticker, normalize_tickers
from ..models import (
    OrderModel, BalanceModel, PositionModel, FillModel,
    SettlementModel, QueuePositionModel, OrderGroupModel,
    SubaccountModel, SubaccountBalanceModel, SubaccountTransferModel,
)

if TYPE_CHECKING:
    from .client import AsyncKalshiClient
    from .markets import AsyncMarket


class AsyncPortfolio:
    """Authenticated user's portfolio and trading operations."""

    def __init__(self, client: AsyncKalshiClient) -> None:
        self._client = client

    async def get_balance(self) -> BalanceModel:
        """Get portfolio balance. Values are dollar strings."""
        data = await self._client.get("/portfolio/balance")
        return BalanceModel.model_validate(data)

    async def place_order(
        self,
        ticker: str | AsyncMarket,
        action: Action,
        side: Side,
        count_fp: str,
        *,
        yes_price_dollars: str | None = None,
        no_price_dollars: str | None = None,
        client_order_id: str | None = None,
        time_in_force: TimeInForce | None = None,
        post_only: bool = False,
        reduce_only: bool = False,
        expiration_ts: int | None = None,
        buy_max_cost_dollars: str | None = None,
        self_trade_prevention: SelfTradePrevention | None = None,
        order_group_id: str | None = None,
        subaccount: int | None = None,
        cancel_order_on_pause: bool | None = None,
    ) -> AsyncOrder:
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
            subaccount: Subaccount number (0 for primary, 1-32 for subaccounts).
            cancel_order_on_pause: If True, cancel order if market is paused.
        """
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
        response = await self._client.post("/portfolio/orders", order_data)
        model = OrderModel.model_validate(response["order"])
        return AsyncOrder(self._client, model)

    async def cancel_order(self, order_id: str, *, subaccount: int | None = None) -> AsyncOrder:
        """Cancel a resting order.

        Args:
            order_id: ID of the order to cancel.
            subaccount: Subaccount number (0 for primary, 1-32 for subaccounts).

        Returns:
            The canceled Order with updated status.
        """
        endpoint = f"/portfolio/orders/{order_id}"
        if subaccount is not None:
            endpoint += f"?subaccount={subaccount}"
        response = await self._client.delete(endpoint)
        model = OrderModel.model_validate(response["order"])
        return AsyncOrder(self._client, model)

    async def amend_order(
        self,
        order_id: str,
        *,
        count_fp: str | None = None,
        yes_price_dollars: str | None = None,
        no_price_dollars: str | None = None,
        subaccount: int | None = None,
        # Required by API but can be fetched from existing order
        ticker: str | None = None,
        action: Action | None = None,
        side: Side | None = None,
    ) -> AsyncOrder:
        """Amend a resting order's price or count.

        Args:
            order_id: ID of the order to amend.
            count_fp: New total contract count (fixed-point string).
            yes_price_dollars: New YES price (dollar string).
            no_price_dollars: New NO price (dollar string). Converted internally.
            subaccount: Subaccount number (0 for primary, 1-32 for subaccounts).
            ticker: Market ticker (fetched from order if not provided).
            action: Order action (fetched from order if not provided).
            side: Order side (fetched from order if not provided).
        """
        if count_fp is None and yes_price_dollars is None and no_price_dollars is None:
            raise ValueError("Must specify at least one amend field")

        if yes_price_dollars is not None and no_price_dollars is not None:
            raise ValueError("Specify yes_price_dollars or no_price_dollars, not both")

        if no_price_dollars is not None:
            yes_price_dollars = str(Decimal("1") - Decimal(no_price_dollars))

        ticker = normalize_ticker(ticker)

        # Fetch original order to get required fields if not provided
        if ticker is None or action is None or side is None or count_fp is None:
            original = await self.get_order(order_id)
            ticker = ticker or original.ticker
            action = action or original.action
            side = side or original.side
            if count_fp is None:
                count_fp = original.remaining_count_fp

        body: dict = {
            "ticker": ticker,
            "action": action.value if isinstance(action, Action) else action,
            "side": side.value if isinstance(side, Side) else side,
            "count_fp": count_fp,
        }
        if yes_price_dollars is not None:
            body["yes_price_dollars"] = yes_price_dollars
        if subaccount is not None:
            body["subaccount"] = subaccount

        response = await self._client.post(f"/portfolio/orders/{order_id}/amend", body)
        model = OrderModel.model_validate(response["order"])
        return AsyncOrder(self._client, model)

    async def decrease_order(self, order_id: str, reduce_by_fp: str) -> AsyncOrder:
        """Decrease the remaining count of a resting order.

        Args:
            order_id: ID of the order to decrease.
            reduce_by_fp: Number of contracts to reduce by (fixed-point string).
        """
        response = await self._client.post(
            f"/portfolio/orders/{order_id}/decrease", {"reduce_by_fp": reduce_by_fp}
        )
        model = OrderModel.model_validate(response["order"])
        return AsyncOrder(self._client, model)

    async def get_orders(
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
    ) -> DataFrameList[AsyncOrder]:
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
        data = await self._client.paginated_get("/portfolio/orders", "orders", params, fetch_all)
        return DataFrameList(AsyncOrder(self._client, OrderModel.model_validate(d)) for d in data)

    async def get_order(self, order_id: str) -> AsyncOrder:
        """Get a single order by ID."""
        response = await self._client.get(f"/portfolio/orders/{order_id}")
        model = OrderModel.model_validate(response["order"])
        return AsyncOrder(self._client, model)

    async def get_positions(
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
        data = await self._client.paginated_get("/portfolio/positions", "market_positions", params, fetch_all)
        return DataFrameList(PositionModel.model_validate(p) for p in data)

    async def get_fills(
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
        data = await self._client.paginated_get("/portfolio/fills", "fills", params, fetch_all)
        return DataFrameList(FillModel.model_validate(f) for f in data)

    # --- Batch Operations ---

    async def batch_place_orders(self, orders: list[dict]) -> DataFrameList[AsyncOrder]:
        """Place multiple orders atomically.

        Args:
            orders: List of order dicts with keys: ticker, action, side, count_fp,
                    yes_price_dollars/no_price_dollars, and optional advanced params.

        Example:
            orders = [
                {"ticker": "KXBTC", "action": "buy", "side": "yes", "count_fp": "10.00", "yes_price_dollars": "0.45"},
                {"ticker": "KXBTC", "action": "buy", "side": "no", "count_fp": "10.00", "no_price_dollars": "0.45"},
            ]
            results = await portfolio.batch_place_orders(orders)
        """
        prepared = self._build_batch_orders(orders)
        response = await self._client.post("/portfolio/orders/batched", {"orders": prepared})
        result = []
        for item in (response.get("orders") or []):
            order_data = item.get("order")
            if order_data is None:
                continue
            result.append(AsyncOrder(self._client, OrderModel.model_validate(order_data)))
        return DataFrameList(result)

    async def batch_cancel_orders(self, order_ids: list[str]) -> DataFrameList[AsyncOrder]:
        """Cancel multiple orders atomically.

        Args:
            order_ids: List of order IDs to cancel (max 20).

        Returns:
            The canceled Orders with updated status.
        """
        orders = [{"order_id": oid} for oid in order_ids]
        response = await self._client.delete("/portfolio/orders/batched", {"orders": orders})
        result = []
        for item in (response.get("orders") or []):
            order_data = item.get("order")
            if order_data is None:
                continue
            result.append(AsyncOrder(self._client, OrderModel.model_validate(order_data)))
        return DataFrameList(result)

    # --- Queue Position ---

    async def get_queue_position(self, order_id: str) -> QueuePositionModel:
        """Get queue position for a single resting order."""
        response = await self._client.get(f"/portfolio/orders/{order_id}/queue_position")
        return QueuePositionModel(
            order_id=order_id,
            queue_position_fp=response.get("queue_position_fp", "0.00"),
        )

    async def get_queue_positions(
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

        response = await self._client.get(endpoint)
        return DataFrameList(
            QueuePositionModel.model_validate(qp)
            for qp in (response.get("queue_positions") or [])
        )

    # --- Settlements ---

    async def get_settlements(
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
        data = await self._client.paginated_get("/portfolio/settlements", "settlements", params, fetch_all)
        return DataFrameList(SettlementModel.model_validate(s) for s in data)

    async def get_resting_order_value(self) -> str:
        """Get total value of all resting orders as dollar string.

        NOTE: This endpoint is FCM-only (institutional accounts).
        """
        response = await self._client.get("/portfolio/summary/total_resting_order_value")
        return response.get("total_resting_order_value_dollars", "0")

    # --- Order Groups (Contract Rate Limiting) ---

    async def create_order_group(self, contracts_limit_fp: str) -> OrderGroupModel:
        """Create an order group for rate-limiting contract matches.

        Args:
            contracts_limit_fp: Maximum contracts (fixed-point string) that can be
                matched in a rolling 15-second window.

        Returns:
            Created OrderGroupModel.
        """
        body: dict = {"contracts_limit_fp": contracts_limit_fp}
        response = await self._client.post("/portfolio/order_groups/create", body)
        return OrderGroupModel.model_validate(response)

    async def get_order_group(self, order_group_id: str) -> OrderGroupModel:
        """Get an order group by ID."""
        response = await self._client.get(f"/portfolio/order_groups/{order_group_id}")
        response["id"] = order_group_id
        return OrderGroupModel.model_validate(response)

    async def trigger_order_group(self, order_group_id: str) -> None:
        """Manually trigger an order group, cancelling all orders in it."""
        await self._client.put(f"/portfolio/order_groups/{order_group_id}/trigger", {})

    async def get_order_groups(self) -> DataFrameList[OrderGroupModel]:
        """List all order groups."""
        response = await self._client.get("/portfolio/order_groups")
        return DataFrameList(
            OrderGroupModel.model_validate(og)
            for og in (response.get("order_groups") or [])
        )

    async def reset_order_group(self, order_group_id: str) -> None:
        """Reset matched contract counter for an order group."""
        await self._client.put(f"/portfolio/order_groups/{order_group_id}/reset", {})

    async def update_order_group_limit(self, order_group_id: str, contracts_limit_fp: str) -> None:
        """Update the contracts limit for an order group.

        Args:
            order_group_id: ID of the order group.
            contracts_limit_fp: New maximum contracts (fixed-point string).
        """
        body: dict = {"contracts_limit_fp": contracts_limit_fp}
        await self._client.put(f"/portfolio/order_groups/{order_group_id}/limit", body)

    # --- Subaccounts ---

    async def create_subaccount(self) -> SubaccountModel:
        """Create a new numbered subaccount."""
        response = await self._client.post("/portfolio/subaccounts", {})
        return SubaccountModel.model_validate(response.get("subaccount", response))

    async def transfer_between_subaccounts(
        self,
        from_subaccount_id: str,
        to_subaccount_id: str,
        amount_dollars: str,
    ) -> SubaccountTransferModel:
        """Transfer funds between subaccounts.

        Args:
            from_subaccount_id: Source subaccount ID.
            to_subaccount_id: Destination subaccount ID.
            amount_dollars: Amount to transfer (dollar string).
        """
        body = {
            "from_subaccount_id": from_subaccount_id,
            "to_subaccount_id": to_subaccount_id,
            "amount_dollars": amount_dollars,
        }
        response = await self._client.post("/portfolio/subaccounts/transfer", body)
        return SubaccountTransferModel.model_validate(response.get("transfer", response))

    async def get_subaccount_balances(self) -> DataFrameList[SubaccountBalanceModel]:
        """Get balances for all subaccounts."""
        response = await self._client.get("/portfolio/subaccounts/balances")
        return DataFrameList(
            SubaccountBalanceModel.model_validate(b)
            for b in (response.get("balances") or [])
        )

    async def get_subaccount_transfers(
        self,
        *,
        limit: int = 100,
        cursor: str | None = None,
        fetch_all: bool = False,
        **extra_params,
    ) -> DataFrameList[SubaccountTransferModel]:
        """Get transfer history between subaccounts."""
        params = {"limit": limit, "cursor": cursor, **extra_params}
        data = await self._client.paginated_get(
            "/portfolio/subaccounts/transfers", "transfers", params, fetch_all
        )
        return DataFrameList(SubaccountTransferModel.model_validate(t) for t in data)

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
            yes_price_dollars = str(Decimal("1") - Decimal(no_price_dollars))

        # Validate tick size if market structure is known
        if price_level_structure and yes_price_dollars is not None:
            AsyncPortfolio._validate_tick_size(Decimal(yes_price_dollars), price_level_structure)

        # Validate fractional trading
        if fractional_trading_enabled is not None:
            AsyncPortfolio._validate_fractional(count_fp, fractional_trading_enabled)

        ticker_str = ticker.upper() if isinstance(ticker, str) else ticker.ticker

        order_data: dict = {
            "ticker": ticker_str,
            "action": action.value,
            "side": side.value,
            "count_fp": count_fp,
            "yes_price_dollars": yes_price_dollars,
        }
        if client_order_id is not None:
            order_data["client_order_id"] = client_order_id
        if time_in_force is not None:
            order_data["time_in_force"] = time_in_force.value
        if post_only:
            order_data["post_only"] = True
        if reduce_only:
            order_data["reduce_only"] = True
        if expiration_ts is not None:
            order_data["expiration_ts"] = expiration_ts
        if buy_max_cost_dollars is not None:
            order_data["buy_max_cost_dollars"] = buy_max_cost_dollars
        if self_trade_prevention is not None:
            order_data["self_trade_prevention_type"] = self_trade_prevention.value
        if order_group_id is not None:
            order_data["order_group_id"] = order_group_id
        if subaccount is not None:
            order_data["subaccount"] = subaccount
        if cancel_order_on_pause is not None:
            order_data["cancel_order_on_pause"] = cancel_order_on_pause
        return order_data

    @staticmethod
    def _build_batch_orders(orders: list[dict]) -> list[dict]:
        """Validate and prepare batch orders. No I/O."""
        prepared = []
        for order in orders:
            o = dict(order)

            if "yes_price_dollars" in o and "no_price_dollars" in o:
                raise ValueError("Specify yes_price_dollars or no_price_dollars, not both")
            if "yes_price_dollars" not in o and "no_price_dollars" not in o:
                raise ValueError("Limit orders require yes_price_dollars or no_price_dollars")
            if "no_price_dollars" in o:
                o["yes_price_dollars"] = str(Decimal("1") - Decimal(o.pop("no_price_dollars")))
            # Strip "type" -- Kalshi API no longer accepts it
            o.pop("type", None)
            prepared.append(o)
        return prepared
