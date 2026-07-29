from __future__ import annotations

import warnings
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from ..models import RfqModel, QuoteModel
from ..dataframe import DataFrameList
from .._utils import normalize_ticker

if TYPE_CHECKING:
    from .client import AsyncKalshiClient


class AsyncCommunications:
    """RFQ (Request for Quote) and quote operations for combo trading.

    Multivariate event combos trade via the RFQ system rather than
    standard limit orders. The flow is:

    1. Create an RFQ broadcasting your intent to trade a combo.
    2. Market makers respond with two-sided quotes.
    3. Accept a quote to execute the trade.

    Usage:
        # Create an RFQ for a combo market
        rfq = await client.communications.create_rfq(
            market_ticker="KXMVE-...",
            contracts_fp="10.00",
        )

        # List open RFQs
        rfqs = await client.communications.get_rfqs(status="open")

        # Respond to an RFQ as a market maker
        quote = await client.communications.create_quote(
            rfq_id=rfq.rfq_id,
            yes_bid="0.45",
            no_bid="0.55",
        )
    """

    def __init__(self, client: AsyncKalshiClient) -> None:
        self._client = client

    async def create_rfq(
        self,
        market_ticker: str,
        *,
        contracts_fp: str | None = None,
        target_cost_dollars: str | None = None,
        rest_remainder: bool = False,
    ) -> RfqModel:
        """Create a Request for Quote.

        Args:
            market_ticker: The combo market ticker to request quotes for.
            contracts_fp: Number of contracts to trade (fixed-point string, e.g. "10.00").
            target_cost_dollars: Target cost in dollars (e.g. "10.00").
                                 Use this OR contracts_fp, not both.
            rest_remainder: If True, rest any unfilled portion on the orderbook.
        """

        body: dict = {
            "market_ticker": market_ticker.upper(),
            "rest_remainder": rest_remainder,
        }
        if contracts_fp is not None:
            body["contracts_fp"] = contracts_fp
        if target_cost_dollars is not None:
            body["target_cost_dollars"] = target_cost_dollars

        response = await self._client.post("/communications/rfqs", body)
        return RfqModel.model_validate(response.get("rfq", response))

    async def get_rfqs(
        self,
        *,
        market_ticker: str | None = None,
        event_ticker: str | None = None,
        status: str | None = None,
        user_filter: str | None = None,
        subaccount: int | None = None,
        creator_user_id: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
        fetch_all: bool = False,
        **extra_params,
    ) -> DataFrameList[RfqModel]:
        """List RFQs.

        Args:
            market_ticker: Filter by combo market ticker.
            event_ticker: Filter by event ticker (a single ticker only).
            status: Filter by RFQ status ("open", "closed").
            user_filter: Pass ``"self"`` to return only RFQs created by the
                authenticated user. Omit to return all RFQs.
            subaccount: Subaccount number (0 for primary, 1-63 for
                subaccounts). If omitted, defaults to all subaccounts.
            creator_user_id: Filter by RFQ creator user ID. Deprecated by the
                Kalshi API — prefer ``user_filter="self"``.
            limit: Maximum results per page (default 100, max 100).
            cursor: Pagination cursor.
            fetch_all: If True, automatically fetch all pages.

        Note:
            The ``mve_collection_ticker`` keyword was removed in favor of
            client-side filtering: it is not a filter the API documents on
            GET /communications/rfqs.
        """
        if "mve_collection_ticker" in extra_params:
            raise TypeError(
                "get_rfqs() no longer supports 'mve_collection_ticker': it is not "
                "a filter the Kalshi API documents on GET /communications/rfqs, "
                "so the server would return unfiltered results. Filter the "
                "returned RFQs by their mve_collection_ticker field instead."
            )
        if creator_user_id is not None:
            warnings.warn(
                "The creator_user_id filter on GET /communications/rfqs is "
                'deprecated by the Kalshi API; use user_filter="self" to filter '
                "by the authenticated user.",
                DeprecationWarning,
                stacklevel=2,
            )

        params = {
            "market_ticker": normalize_ticker(market_ticker),
            "event_ticker": normalize_ticker(event_ticker),
            "status": status,
            "user_filter": user_filter,
            "subaccount": subaccount,
            "creator_user_id": creator_user_id,
            "limit": limit,
            "cursor": cursor,
            **extra_params,
        }
        data = await self._client.paginated_get("/communications/rfqs", "rfqs", params, fetch_all)
        return DataFrameList(RfqModel.model_validate(r) for r in data)

    async def get_rfq(self, rfq_id: str) -> RfqModel:
        """Get a single RFQ by ID."""
        response = await self._client.get(f"/communications/rfqs/{rfq_id}")
        return RfqModel.model_validate(response.get("rfq", response))

    async def create_quote(
        self,
        rfq_id: str,
        *,
        yes_bid: str,
        no_bid: str,
        rest_remainder: bool = False,
    ) -> QuoteModel:
        """Create a quote in response to an RFQ.

        Prices are in FixedPointDollars (e.g., "0.45").

        Args:
            rfq_id: ID of the RFQ to respond to.
            yes_bid: Your bid price for the YES side (FixedPointDollars).
            no_bid: Your bid price for the NO side (FixedPointDollars).
            rest_remainder: If True, rest any unfilled portion on the orderbook.
        """
        body: dict = {
            "rfq_id": rfq_id,
            "yes_bid": yes_bid,
            "no_bid": no_bid,
            "rest_remainder": rest_remainder,
        }

        response = await self._client.post("/communications/quotes", body)
        return QuoteModel.model_validate(response.get("quote", response))

    async def get_quotes(
        self,
        *,
        user_filter: str | None = None,
        rfq_user_filter: str | None = None,
        rfq_id: str | None = None,
        status: str | None = None,
        min_ts: int | None = None,
        max_ts: int | None = None,
        quote_creator_user_id: str | None = None,
        rfq_creator_user_id: str | None = None,
        rfq_creator_subtrader_id: str | None = None,
        limit: int = 500,
        cursor: str | None = None,
        fetch_all: bool = False,
        creator_user_id: str | None = None,
        **extra_params,
    ) -> DataFrameList[QuoteModel]:
        """List quotes.

        All filters are optional; with none set, returns all quotes visible
        to the authenticated user.

        Args:
            user_filter: Pass ``"self"`` to return only quotes created by the
                authenticated user. Omit to return all quotes.
            rfq_user_filter: Pass ``"self"`` to return only quotes responding
                to RFQs created by the authenticated user.
            rfq_id: Filter by RFQ ID.
            status: Filter by quote status
                (open, accepted, confirmed, executed, cancelled).
            min_ts: Only quotes last updated after this Unix timestamp.
            max_ts: Only quotes last updated before this Unix timestamp.
            quote_creator_user_id: Filter by quote creator user ID. Deprecated
                by the Kalshi API — prefer ``user_filter="self"``.
            rfq_creator_user_id: Filter by RFQ creator user ID. Deprecated by
                the Kalshi API — prefer ``rfq_user_filter="self"``.
            rfq_creator_subtrader_id: Filter by RFQ creator subtrader ID
                (FCM members only).
            limit: Maximum results per page (default 500, max 500).
            cursor: Pagination cursor.
            fetch_all: If True, automatically fetch all pages.
            creator_user_id: Deprecated alias for ``quote_creator_user_id``.

        Note:
            The ``market_ticker`` and ``event_ticker`` filters were removed
            from this endpoint by Kalshi on 2026-06-20 and are no longer
            accepted; filter the returned quotes by their ``market_ticker``
            field instead.
        """
        for removed in ("market_ticker", "event_ticker"):
            if removed in extra_params:
                raise TypeError(
                    f"get_quotes() no longer supports {removed!r}: Kalshi removed "
                    "the market and event filters from GET /communications/quotes "
                    "on 2026-06-20, so the server would return unfiltered results. "
                    "Filter the returned quotes by their market_ticker field "
                    "instead."
                )
        if creator_user_id is not None:
            warnings.warn(
                "get_quotes(creator_user_id=...) was renamed to "
                "quote_creator_user_id (itself deprecated by the Kalshi API); "
                'prefer user_filter="self" to filter by the authenticated user.',
                DeprecationWarning,
                stacklevel=2,
            )
            if quote_creator_user_id is None:
                quote_creator_user_id = creator_user_id
        elif quote_creator_user_id is not None:
            warnings.warn(
                "The quote_creator_user_id filter on GET /communications/quotes "
                'is deprecated by the Kalshi API; use user_filter="self" to '
                "filter by the authenticated user.",
                DeprecationWarning,
                stacklevel=2,
            )
        if rfq_creator_user_id is not None:
            warnings.warn(
                "The rfq_creator_user_id filter on GET /communications/quotes "
                'is deprecated by the Kalshi API; use rfq_user_filter="self" to '
                "filter by RFQs created by the authenticated user.",
                DeprecationWarning,
                stacklevel=2,
            )

        params = {
            "user_filter": user_filter,
            "rfq_user_filter": rfq_user_filter,
            "rfq_id": rfq_id,
            "status": status,
            "min_ts": min_ts,
            "max_ts": max_ts,
            "quote_creator_user_id": quote_creator_user_id,
            "rfq_creator_user_id": rfq_creator_user_id,
            "rfq_creator_subtrader_id": rfq_creator_subtrader_id,
            "limit": limit,
            "cursor": cursor,
            **extra_params,
        }
        data = await self._client.paginated_get("/communications/quotes", "quotes", params, fetch_all)
        return DataFrameList(QuoteModel.model_validate(q) for q in data)
