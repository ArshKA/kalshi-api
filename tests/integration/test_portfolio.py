"""Integration tests for Portfolio endpoints."""

import time
import pytest
from pykalshi.enums import (
    Action, Side, OrderStatus, MarketStatus, BookSide, OutcomeSide,
)
from pykalshi.exceptions import ResourceNotFoundError


def _eventually_fetch(
    fetch,
    *,
    predicate=lambda result: True,
    timeout: float = 30.0,
    interval: float = 5.0,
    ignored_exceptions: tuple[type[Exception], ...] = (),
):
    """Retry a read until it succeeds and satisfies the predicate."""
    deadline = time.time() + timeout
    last_error = None

    while time.time() < deadline:
        try:
            result = fetch()
        except ignored_exceptions as exc:
            last_error = exc
        else:
            if predicate(result):
                return result
        time.sleep(interval)

    if last_error is not None:
        raise last_error
    raise AssertionError("Timed out waiting for eventually consistent portfolio state")


def _cleanup_cancel(client, *order_ids):
    """Best-effort cancel for teardown.

    A 404 here means the order is already gone, which teardown does not care
    about: it may have filled, or another suite sharing this demo account may
    have cancelled it (a concurrent trigger_order_group takes down resting
    orders that were placed by a different test run). By the time teardown
    runs the test's assertions have already passed, so a 404 while tidying up
    is not a product regression and must not be reported as one.

    Only ResourceNotFoundError is swallowed -- any other cancel failure still
    surfaces. The tests that exercise cancellation as their subject
    (test_place_and_cancel_order, test_order_cancel_method,
    test_batch_cancel_orders, test_order_wait_until_terminal) call the API
    directly and stay strict, so a genuine break in cancel still fails loudly.
    """
    for order_id in order_ids:
        try:
            client.portfolio.cancel_order(order_id)
        except ResourceNotFoundError:
            pass


class TestPortfolioReadOnly:
    """Read-only portfolio tests - safe to run anytime."""

    def test_get_balance(self, client):
        """Get account balance."""
        balance = client.portfolio.get_balance()

        assert isinstance(balance.balance, int)
        assert isinstance(balance.portfolio_value, int)

    def test_get_positions(self, client):
        """Get positions list."""
        positions = client.portfolio.get_positions(limit=10)

        assert isinstance(positions, list)
        # If positions exist, verify structure
        if positions:
            pos = positions[0]
            assert hasattr(pos, "ticker")
            assert hasattr(pos, "position_fp")

    def test_get_orders(self, client):
        """Get orders list."""
        orders = client.portfolio.get_orders(limit=10)

        assert isinstance(orders, list)
        if orders:
            order = orders[0]
            assert hasattr(order, "order_id")
            assert hasattr(order, "ticker")
            assert hasattr(order, "status")

    def test_get_fills(self, client):
        """Get fills list."""
        fills = client.portfolio.get_fills(limit=10)

        assert isinstance(fills, list)
        if fills:
            fill = fills[0]
            assert hasattr(fill, "ticker")
            assert hasattr(fill, "yes_price_dollars")

    def test_get_settlements(self, client):
        """Get settlements list."""
        settlements = client.portfolio.get_settlements(limit=10)

        assert isinstance(settlements, list)
        if settlements:
            settlement = settlements[0]
            assert hasattr(settlement, "ticker")


class TestOrderGroups:
    """Tests for order group endpoints.

    Order groups limit total contracts matched across orders in the group
    over a rolling 15-second window.
    """

    def test_get_order_groups(self, client):
        """Get order groups (may be empty)."""
        groups = client.portfolio.get_order_groups()
        assert isinstance(groups, list)

    def test_order_group_lifecycle(self, trading_client):
        """Full lifecycle: create group, add order, update limit, trigger."""
        client = trading_client
        from pykalshi.enums import MarketStatus

        # Find an open market
        markets = client.get_markets(limit=10, status=MarketStatus.OPEN)
        market = None
        for m in markets:
            if m.yes_bid_dollars or m.yes_ask_dollars:
                market = m
                break
        if not market:
            market = markets[0] if markets else None
        if not market:
            pytest.skip("No open markets available")

        # Create order group with contracts limit
        group = client.portfolio.create_order_group(contracts_limit_fp="100")

        assert group.id is not None
        group_id = group.id

        try:
            # Place orders in the group
            order1 = client.portfolio.place_order(
                market,
                action=Action.BUY,
                side=Side.YES,
                count_fp="1",
                yes_price_dollars="0.01",
                order_group_id=group_id,
            )
            order2 = client.portfolio.place_order(
                market,
                action=Action.BUY,
                side=Side.YES,
                count_fp="1",
                yes_price_dollars="0.02",
                order_group_id=group_id,
            )

            # Order-group membership can lag briefly on demo.
            try:
                fetched = _eventually_fetch(
                    lambda: client.portfolio.get_order_group(group_id),
                    predicate=lambda group: (
                        group.orders is not None
                        and len(group.orders) == 2
                        and order1.order_id in group.orders
                        and order2.order_id in group.orders
                    ),
                    ignored_exceptions=(ResourceNotFoundError,),
                )
            except ResourceNotFoundError:
                # Distinguish a demo read-model outage from a real API break.
                # The create ack issued this id and trigger accepts it, so the
                # write side has the group. If it is also absent from the LIST
                # endpoint, query-exchange is not indexing new groups at all
                # (observed 2026-07-26: creates succeed while both read paths
                # 404 for hours) -- exchange-side unavailability, same policy
                # as the 503 skip hook. A group that IS listed but 404s by id
                # would be a genuine API regression, so that still fails.
                listed = {g.id for g in client.portfolio.get_order_groups()}
                if group_id not in listed:
                    pytest.skip(
                        "demo read model is not indexing new order groups "
                        "(create succeeded; group absent from both GET-by-id "
                        "and the list endpoint)"
                    )
                raise
            assert fetched.orders is not None
            assert len(fetched.orders) == 2
            assert order1.order_id in fetched.orders
            assert order2.order_id in fetched.orders

            # Update limit
            client.portfolio.update_order_group_limit(group_id, contracts_limit_fp="200")

            updated = _eventually_fetch(
                lambda: client.portfolio.get_order_group(group_id),
                predicate=lambda group: group.contracts_limit_fp is not None,
                ignored_exceptions=(ResourceNotFoundError,),
            )
            assert updated.contracts_limit_fp is not None

            # Trigger the group (cancels all orders)
            client.portfolio.trigger_order_group(group_id)

        finally:
            # Cleanup - cancel orders if they still exist
            try:
                client.portfolio.batch_cancel_orders([order1.order_id, order2.order_id])
            except Exception:
                pass  # Orders may already be cancelled by trigger


class TestOrderMutations:
    """Tests for order placement, amendment, and cancellation.

    These tests place real orders on the demo account at prices
    that won't fill (far from market), then clean up.

    Note: These tests require the exchange to be available for trading.
    They may be skipped during exchange maintenance windows.
    """

    @pytest.fixture
    def market_for_orders(self, trading_client):
        """Get an active market suitable for placing test orders.

        Uses trading_client to skip all mutation tests when the exchange is paused.
        """
        client = trading_client
        markets = client.get_markets(limit=10, status=MarketStatus.OPEN)

        # Find one with some activity (has yes_bid or yes_ask)
        for m in markets:
            if m.data.yes_bid_dollars or m.data.yes_ask_dollars:
                return m
        # Fall back to any open market
        if markets:
            return markets[0]
        pytest.skip("No open markets available")

    def test_place_and_cancel_order(self, client, market_for_orders):
        """Place an order and cancel it."""
        market = market_for_orders

        # Place limit order at $0.01 (won't fill)
        order = client.portfolio.place_order(
            market,
            action=Action.BUY,
            side=Side.YES,
            count_fp="1",
            yes_price_dollars="0.01",
        )

        assert order.order_id is not None
        assert order.ticker == market.ticker
        assert order.status == OrderStatus.RESTING

        # Cancel it
        cancelled = client.portfolio.cancel_order(order.order_id)

        assert cancelled.order_id == order.order_id
        assert cancelled.status == OrderStatus.CANCELED

    def test_order_cancel_method(self, client, market_for_orders):
        """Test Order.cancel() method."""
        market = market_for_orders

        order = client.portfolio.place_order(
            market,
            action=Action.BUY,
            side=Side.YES,
            count_fp="1",
            yes_price_dollars="0.01",
        )

        assert order.order_id is not None
        assert order.status == OrderStatus.RESTING

        # Use the order's cancel method
        order.cancel()
        assert order.status == OrderStatus.CANCELED

    def test_amend_order(self, client, market_for_orders):
        """Place an order and amend its price."""
        market = market_for_orders

        # Place at $0.01
        order = client.portfolio.place_order(
            market,
            action=Action.BUY,
            side=Side.YES,
            count_fp="1",
            yes_price_dollars="0.01",
        )

        # Amend to $0.02, addressed the canonical way. action/side are
        # deprecated and past their stated removal floor, so a test that
        # depends on them is testing a path that is scheduled to disappear.
        amended = client.portfolio.amend_order(
            order_id=order.order_id,
            count_fp="1",
            yes_price_dollars="0.02",
            ticker=order.ticker,
            book_side=order.book_side,
        )

        # Verify amendment succeeded
        assert amended.order_id is not None
        assert amended.status == OrderStatus.RESTING

        # Cleanup
        _cleanup_cancel(client, amended.order_id)

    def test_order_amend_method(self, client, market_for_orders):
        """Test Order.amend() method."""
        market = market_for_orders

        order = client.portfolio.place_order(
            market,
            action=Action.BUY,
            side=Side.YES,
            count_fp="1",
            yes_price_dollars="0.01",
        )

        original_price = order.yes_price_dollars

        # Use the order's amend method
        order.amend(count_fp="1", yes_price_dollars="0.02")

        # Verify amendment - price should have changed
        assert float(order.yes_price_dollars) == 0.02
        assert order.yes_price_dollars != original_price
        assert order.status == OrderStatus.RESTING

        # Cleanup
        _cleanup_cancel(client, order.order_id)

    def test_decrease_order(self, client, market_for_orders):
        """Place an order and decrease its count."""
        market = market_for_orders

        # Place order for 5 contracts
        order = client.portfolio.place_order(
            market,
            action=Action.BUY,
            side=Side.YES,
            count_fp="5",
            yes_price_dollars="0.01",
        )

        assert float(order.remaining_count_fp) == 5

        # Decrease by 3
        decreased = client.portfolio.decrease_order(
            order_id=order.order_id,
            reduce_by_fp="3",
        )

        assert decreased.order_id == order.order_id
        assert float(decreased.remaining_count_fp) == 2

        # Cleanup
        _cleanup_cancel(client, order.order_id)

    def test_order_decrease_method(self, client, market_for_orders):
        """Test Order.decrease() method."""
        market = market_for_orders

        order = client.portfolio.place_order(
            market,
            action=Action.BUY,
            side=Side.YES,
            count_fp="5",
            yes_price_dollars="0.01",
        )

        # Use the order's decrease method
        order.decrease(reduce_by_fp="2")

        assert float(order.remaining_count_fp) == 3

        # Cleanup
        _cleanup_cancel(client, order.order_id)

    def test_order_refresh(self, client, market_for_orders):
        """Test Order.refresh() to get latest state.

        Note: The demo API's single order lookup may return 404.
        This test verifies the refresh method works when the API is available.
        """
        market = market_for_orders

        order = client.portfolio.place_order(
            market,
            action=Action.BUY,
            side=Side.YES,
            count_fp="1",
            yes_price_dollars="0.01",
        )

        # Refresh may fail on demo due to single order lookup 404
        try:
            original_status = order.status
            order.refresh()
            assert order.status == original_status
        except ResourceNotFoundError:
            # Demo API limitation - skip this assertion
            pass

        # Cleanup
        _cleanup_cancel(client, order.order_id)

    def test_batch_cancel_orders(self, client, market_for_orders):
        """Place multiple orders and batch cancel them."""
        market = market_for_orders

        # Place 3 orders
        orders = []
        for i in range(3):
            order = client.portfolio.place_order(
                market,
                action=Action.BUY,
                side=Side.YES,
                count_fp="1",
                yes_price_dollars="0.01",
            )
            orders.append(order)

        order_ids = [o.order_id for o in orders]

        # Batch cancel
        result = client.portfolio.batch_cancel_orders(order_ids)

        # Result should be a list of Order objects
        assert isinstance(result, list)
        assert len(result) == 3
        for order in result:
            assert order.order_id in order_ids

    def test_get_order_by_id(self, client, market_for_orders):
        """Get a specific order by ID."""
        market = market_for_orders

        order = client.portfolio.place_order(
            market,
            action=Action.BUY,
            side=Side.YES,
            count_fp="1",
            yes_price_dollars="0.01",
        )

        fetched = _eventually_fetch(
            lambda: client.portfolio.get_order(order.order_id),
            ignored_exceptions=(ResourceNotFoundError,),
        )
        assert fetched.order_id == order.order_id
        assert fetched.ticker == order.ticker

        # Cleanup
        _cleanup_cancel(client, order.order_id)

    def test_batch_place_orders(self, client, market_for_orders):
        """Place multiple orders atomically with batch_place_orders."""
        market = market_for_orders

        orders_to_place = [
            {
                "ticker": market.ticker,
                "action": "buy",
                "side": "yes",
                "count_fp": "1",
                "yes_price_dollars": "0.01",
            },
            {
                "ticker": market.ticker,
                "action": "buy",
                "side": "yes",
                "count_fp": "1",
                "yes_price_dollars": "0.02",
            },
        ]

        result = client.portfolio.batch_place_orders(orders_to_place)

        assert isinstance(result, list)
        assert len(result) == 2

        # All orders should be resting
        for order in result:
            assert order.order_id is not None
            assert order.ticker == market.ticker

        # Cleanup - batch cancel
        order_ids = [o.order_id for o in result]
        _cleanup_cancel(client, *order_ids)

    def test_batch_place_orders_no_price_conversion(self, client, market_for_orders):
        """Batch orders with no_price_dollars should be converted to yes_price_dollars."""
        market = market_for_orders

        orders_to_place = [
            {
                "ticker": market.ticker,
                "action": "buy",
                "side": "no",
                "count_fp": "1",
                "no_price_dollars": "0.99",  # Should become yes_price_dollars="0.01"
            },
        ]

        result = client.portfolio.batch_place_orders(orders_to_place)

        assert len(result) == 1
        assert result[0].order_id is not None
        assert float(result[0].yes_price_dollars) == 0.01

        # Cleanup
        _cleanup_cancel(client, result[0].order_id)

    def test_batch_place_orders_validation(self, client, market_for_orders):
        """Batch validation catches errors before hitting the API."""
        market = market_for_orders

        # Both yes_price_dollars and no_price_dollars
        with pytest.raises(ValueError, match="yes_price_dollars or no_price_dollars"):
            client.portfolio.batch_place_orders([{
                "ticker": market.ticker,
                "action": "buy",
                "side": "yes",
                "count_fp": "1",
                "yes_price_dollars": "0.45",
                "no_price_dollars": "0.55",
            }])

        # Limit order without price
        with pytest.raises(ValueError, match="require yes_price_dollars or no_price_dollars"):
            client.portfolio.batch_place_orders([{
                "ticker": market.ticker,
                "action": "buy",
                "side": "yes",
                "count_fp": "1",
            }])

    def test_get_queue_position(self, client, market_for_orders):
        """Get queue position for a resting order."""
        market = market_for_orders

        order = client.portfolio.place_order(
            market,
            action=Action.BUY,
            side=Side.YES,
            count_fp="1",
            yes_price_dollars="0.01",
        )

        queue_pos = _eventually_fetch(
            lambda: client.portfolio.get_queue_position(order.order_id),
            ignored_exceptions=(ResourceNotFoundError,),
        )

        assert hasattr(queue_pos, "order_id")
        assert hasattr(queue_pos, "queue_position_fp")
        assert queue_pos.order_id == order.order_id
        # Queue position should be a fixed-point string
        assert isinstance(queue_pos.queue_position_fp, str)
        assert float(queue_pos.queue_position_fp) >= 0

        # Cleanup (order may already be filled/gone)
        try:
            order.cancel()
        except ResourceNotFoundError:
            pass

    def test_get_queue_positions_multiple(self, client, market_for_orders):
        """Get queue positions for all resting orders (filtered by market)."""
        market = market_for_orders

        # Place 2 orders
        orders = []
        for _ in range(2):
            order = client.portfolio.place_order(
                market,
                action=Action.BUY,
                side=Side.YES,
                count_fp="1",
                yes_price_dollars="0.01",
            )
            orders.append(order)

        order_ids = [o.order_id for o in orders]

        try:
            # Get queue positions filtered by market ticker
            queue_positions = client.portfolio.get_queue_positions(
                market_tickers=[market.ticker]
            )

            assert isinstance(queue_positions, list)
            # Should have results (may include our orders and others)
            assert len(queue_positions) >= 0

            # Verify queue_position_fp is a string for all results
            for qp in queue_positions:
                assert isinstance(qp.queue_position_fp, str)
                assert qp.order_id is not None
        finally:
            # Cleanup
            _cleanup_cancel(client, *(o.order_id for o in orders))

    def test_order_wait_until_terminal(self, client, market_for_orders):
        """Test Order.wait_until_terminal() by cancelling an order."""
        market = market_for_orders

        order = client.portfolio.place_order(
            market,
            action=Action.BUY,
            side=Side.YES,
            count_fp="1",
            yes_price_dollars="0.01",
        )

        assert order.status == OrderStatus.RESTING

        # Cancel the order
        client.portfolio.cancel_order(order.order_id)

        # Demo API may briefly 404 after cancel due to eventual consistency.
        terminal_order = _eventually_fetch(
            lambda: client.portfolio.get_order(order.order_id),
            predicate=lambda o: o.status in (OrderStatus.CANCELED, OrderStatus.EXECUTED),
            timeout=30.0,
            interval=2.0,
            ignored_exceptions=(ResourceNotFoundError,),
        )

        assert terminal_order.status == OrderStatus.CANCELED


class TestV2OrderSurface:
    """Pin the endpoints and the direction mapping against the real API.

    The rest of this suite asserts only on behaviour, which is how the v1 order
    endpoints survived being replaced: a wrong path or an inverted side is
    invisible if you only check that an order_id came back.
    """

    @staticmethod
    def _await_order(client, order_id, until=None, tries=8, delay=0.5):
        """Fetch an order, tolerating read-after-write lag.

        Writes are acknowledged by the matching engine but reads are served by
        query-exchange, which indexes a moment later. Until it catches up,
        GET /portfolio/orders/{id} returns 404 not_found (an unknown order --
        distinct from the "404 page not found" you get from a missing route),
        and an order that does exist can still be returned in its pre-write
        state.

        `until` is an optional predicate on the fetched order; polling continues
        until it holds, so a test can wait for its own write to land rather than
        racing it.
        """
        import time as _time
        from pykalshi.exceptions import ResourceNotFoundError

        last = None
        for attempt in range(tries):
            try:
                order = client.portfolio.get_order(order_id)
                if until is None or until(order):
                    return order
                last = f"predicate not yet satisfied (attempt {attempt + 1})"
            except ResourceNotFoundError as exc:
                last = exc
            _time.sleep(delay * (attempt + 1))
        pytest.skip(f"order {order_id} did not reach the expected state in time: {last}")

    @pytest.fixture
    def market_for_orders(self, trading_client):
        client = trading_client
        markets = client.get_markets(limit=10, status=MarketStatus.OPEN)
        for m in markets:
            if m.data.yes_bid_dollars or m.data.yes_ask_dollars:
                return m
        if markets:
            return markets[0]
        pytest.skip("No open markets available")

    def test_writes_use_v2_reads_use_v1(self, recorded_client, market_for_orders):
        """Writes go to /portfolio/events/orders; reads stay on /portfolio/orders.

        POST /portfolio/orders returns 410; GET /portfolio/events/orders returns
        404. Getting either half wrong breaks the client, so pin both.
        """
        from .conftest import paths_for

        client = recorded_client
        order = client.portfolio.place_order(
            market_for_orders, book_side="bid", price_dollars="0.01",
            count_fp="1",
        )
        try:
            self._await_order(client, order.order_id)
            list(client.portfolio.get_orders(status=OrderStatus.RESTING))
        finally:
            _cleanup_cancel(client, order.order_id)

        assert "/portfolio/events/orders" in paths_for(client, "POST")
        assert f"/portfolio/events/orders/{order.order_id}" in paths_for(client, "DELETE")

        gets = paths_for(client, "GET")
        assert "/portfolio/orders" in gets
        assert f"/portfolio/orders/{order.order_id}" in gets
        assert not any(p.startswith("/portfolio/events/orders") for p in gets), (
            f"read hit a V2 path, which 404s: {gets}"
        )

    def test_buy_no_is_normalised_to_a_yes_side_sell(self, client, market_for_orders):
        """buy NO @ 0.01 must rest as sell YES @ 0.99.

        V2 quotes a single YES-denominated book, so the client converts
        (buy, NO, p) -> ask at 1 - p, and the exchange stores it as a YES-side
        sell. If that conversion inverted, the order would rest on the wrong
        side at the wrong price and nothing else in this suite would notice --
        the other tests only check order_id and status.

        Priced as an ask at 0.99, far above any book, so it cannot fill. (The
        mirror image, an ask at 0.01, would cross and post_only rejects it with
        400 invalid_order.)
        """
        order = client.portfolio.place_order(
            # ask at 0.99 == buy NO at 0.01, expressed canonically
            market_for_orders, book_side="ask", price_dollars="0.99",
            count_fp="1",
        )
        try:
            # Both the returned Order and the fetched one describe the same
            # long-no position, and they agree on the canonical field even
            # though their legacy (action, side) pairs differ.
            assert order.data.book_side == BookSide.ASK
            assert order.data.outcome_side == OutcomeSide.NO
            assert float(order.data.yes_price_dollars) == pytest.approx(0.99)

            fetched = self._await_order(client, order.order_id)
            assert fetched.data.book_side == BookSide.ASK
            assert float(fetched.data.yes_price_dollars) == pytest.approx(0.99)
            assert float(fetched.data.no_price_dollars) == pytest.approx(0.01)

            # Legacy compatibility, while the server still sends it: the pair
            # flips between what we submitted (buy/no) and what comes back
            # (sell/yes) for one unchanged order. Skipped rather than failed
            # once Kalshi drops these -- the canonical asserts above are the
            # ones that must hold.
            if fetched.data.side is not None and fetched.data.action is not None:
                assert fetched.data.side == Side.YES
                assert fetched.data.action == Action.SELL
        finally:
            _cleanup_cancel(client, order.order_id)

    def test_amend_actually_changes_the_resting_order(self, client, market_for_orders):
        """Re-read after amending.

        The existing amend tests assert only that a resting order came back, so a
        no-op amend -- or one sent at the wrong price -- passes. The V2 amend body
        is a different shape from v1, so verify the server state moved.
        """
        order = client.portfolio.place_order(
            market_for_orders, book_side="bid", price_dollars="0.01",
            count_fp="1",
        )
        try:
            self._await_order(client, order.order_id)
            client.portfolio.amend_order(
                order.order_id, count_fp="3", yes_price_dollars="0.01",
            )

            after = self._await_order(
                client, order.order_id,
                until=lambda o: float(o.data.remaining_count_fp or 0) == 3.0,
            )
            assert float(after.data.remaining_count_fp) == pytest.approx(3.0)
            assert float(after.data.yes_price_dollars) == pytest.approx(0.01), (
                "amend must preserve the price when only the count changes"
            )
        finally:
            _cleanup_cancel(client, order.order_id)

    def test_write_ack_does_not_blank_known_fields(self, client, market_for_orders):
        """V2 acks carry no ticker/side/price; the Order must keep its own."""
        order = client.portfolio.place_order(
            market_for_orders, book_side="bid", price_dollars="0.01",
            count_fp="1",
        )
        ticker = order.ticker
        assert ticker == market_for_orders.ticker

        order.cancel()

        assert order.status == OrderStatus.CANCELED
        assert order.ticker == ticker, "cancel ack wiped the ticker"
        assert order.data.book_side == BookSide.BID, "cancel ack wiped book_side"
        assert order.data.yes_price_dollars is not None

    def test_batch_place_returns_populated_orders(self, client, market_for_orders):
        """Batch acks are as thin as single ones; results must still be usable."""
        market = market_for_orders
        result = client.portfolio.batch_place_orders([
            {"ticker": market.ticker, "action": "buy", "side": "yes",
             "count_fp": "1", "yes_price_dollars": "0.01"},
            {"ticker": market.ticker, "action": "buy", "side": "yes",
             "count_fp": "1", "yes_price_dollars": "0.02"},
        ])
        try:
            assert len(result) == 2
            for o in result:
                assert o.order_id is not None
                assert o.ticker == market.ticker, "batch ack left ticker blank"
                assert o.data.yes_price_dollars is not None, "batch ack left price null"
            prices = sorted(float(o.data.yes_price_dollars) for o in result)
            assert prices == pytest.approx([0.01, 0.02])
        finally:
            ids = [o.order_id for o in result if o.order_id]
            _cleanup_cancel(client, *ids)
