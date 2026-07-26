"""Direction semantics: book_side / outcome_side vs the deprecated action/side.

Kalshi deprecated `action`, `side`, `is_yes`, `purchased_side` and `taker_side`
on Order/Fill/Trade (https://docs.kalshi.com/getting_started/order_direction),
with a stated removal floor of 2026-05-28. The canonical replacements are
`outcome_side` (yes|no) and `book_side` (bid|ask), where bid == yes.

The subtlety these tests exist to pin: the legacy pair does NOT mean the same
thing on every surface.

  Orders -- direction is the (action, side) PAIR, per Kalshi's published table.
            sell/yes is long no  -> ask.
  Fills  -- `side` alone is the outcome acquired; `action` carries no sign.
            sell/yes is long yes -> bid. The OPPOSITE of the order rule, and
            not what the published table says. Verified against 1,685 live
            fills, where side == outcome_side in every single one.

So a mapper written for orders inverts every `sell` fill. `book_side` is
identical on both surfaces, which is why it is the one thing to branch on.
"""
import pytest

from pykalshi.enums import BookSide, OutcomeSide
from pykalshi.models import FillModel, OrderModel, TradeModel
from pykalshi._utils import (
    book_side_from_fill_legacy,
    book_side_from_order_legacy,
)


# (action, side) -> book_side, from Kalshi's published table. Orders only.
ORDER_TABLE = [
    ("buy", "yes", "bid"),
    ("sell", "no", "bid"),
    ("buy", "no", "ask"),
    ("sell", "yes", "ask"),
]

# Observed on 1,685 live fills. `action` is orthogonal; `side` is the outcome.
FILL_TABLE = [
    ("buy", "yes", "bid"),
    ("sell", "yes", "bid"),
    ("buy", "no", "ask"),
    ("sell", "no", "ask"),
]


class TestLegacyMappers:
    @pytest.mark.parametrize("action,side,expected", ORDER_TABLE)
    def test_order_mapper(self, action, side, expected):
        assert book_side_from_order_legacy(action, side) == expected

    @pytest.mark.parametrize("action,side,expected", FILL_TABLE)
    def test_fill_mapper_ignores_action(self, action, side, expected):
        assert book_side_from_fill_legacy(side) == expected

    def test_the_two_surfaces_genuinely_disagree(self):
        """The reason a single shared mapper cannot exist."""
        assert book_side_from_order_legacy("sell", "yes") == "ask"
        assert book_side_from_fill_legacy("yes") == "bid"

    def test_mappers_return_none_rather_than_guessing(self):
        assert book_side_from_order_legacy(None, None) is None
        assert book_side_from_order_legacy("buy", None) is None
        assert book_side_from_fill_legacy(None) is None


class TestOrderModelDirection:
    @pytest.mark.parametrize("action,side,expected", ORDER_TABLE)
    def test_derived_from_legacy_pair(self, action, side, expected):
        m = OrderModel.model_validate(
            {"order_id": "o", "ticker": "T", "status": "resting",
             "action": action, "side": side})
        assert m.book_side == BookSide(expected)
        assert m.outcome_side == OutcomeSide("yes" if expected == "bid" else "no")

    def test_server_value_wins_over_derivation(self):
        """Never let a local guess override what the server said."""
        m = OrderModel.model_validate(
            {"order_id": "o", "ticker": "T", "status": "resting",
             "action": "sell", "side": "no",   # table would say bid
             "book_side": "ask"})
        assert m.book_side == BookSide.ASK

    def test_survives_legacy_fields_disappearing(self):
        m = OrderModel.model_validate(
            {"order_id": "o", "ticker": "T", "status": "resting",
             "book_side": "ask", "outcome_side": "no"})
        assert m.is_ask and not m.is_bid
        assert m.action is None and m.side is None

    def test_survives_legacy_fields_blanked(self):
        """Kalshi's Go services emit "" for absent optional strings."""
        m = OrderModel.model_validate(
            {"order_id": "o", "ticker": "T", "status": "resting",
             "action": "", "side": "", "book_side": "bid"})
        assert m.book_side == BookSide.BID
        assert m.action is None and m.side is None


class TestFillModelDirection:
    @pytest.mark.parametrize("action,side,expected", FILL_TABLE)
    def test_uses_the_fill_rule_not_the_order_rule(self, action, side, expected):
        m = FillModel.model_validate(
            {"trade_id": "t", "ticker": "T", "order_id": "o",
             "action": action, "side": side, "count_fp": "10",
             "yes_price_dollars": "0.50"})
        assert m.book_side == BookSide(expected), (
            f"fill {action}/{side} must be {expected}; the order mapper would "
            f"give {book_side_from_order_legacy(action, side)}"
        )

    def test_legacy_fields_no_longer_required(self):
        """These were required, so every get_fills() row raised at cutover."""
        m = FillModel.model_validate(
            {"trade_id": "t", "ticker": "T", "order_id": "o", "count_fp": "10",
             "yes_price_dollars": "0.50", "book_side": "ask", "outcome_side": "no"})
        assert m.is_ask
        assert m.action is None and m.side is None

    @pytest.mark.parametrize("book_side,expected", [("bid", 10), ("ask", -10)])
    def test_yes_delta_sign(self, book_side, expected):
        m = FillModel.model_validate(
            {"trade_id": "t", "ticker": "T", "order_id": "o", "count_fp": "10",
             "yes_price_dollars": "0.50", "book_side": book_side})
        assert m.yes_delta_fp == expected

    def test_no_price_is_optional(self):
        """WS fills carry only yes_price_dollars."""
        m = FillModel.model_validate(
            {"trade_id": "t", "ticker": "T", "order_id": "o", "count_fp": "1",
             "yes_price_dollars": "0.50", "book_side": "bid"})
        assert m.no_price_dollars is None


class TestTradeModelDirection:
    @pytest.mark.parametrize("taker,expected", [("yes", "bid"), ("no", "ask")])
    def test_legacy_taker_side_maps_one_to_one(self, taker, expected):
        """A public trade has no action, so the alias is safe here."""
        m = TradeModel.model_validate(
            {"trade_id": "t", "ticker": "T", "count_fp": "1",
             "yes_price_dollars": "0.5", "no_price_dollars": "0.5",
             "taker_side": taker})
        assert m.taker_outcome_side == OutcomeSide(taker)
        assert m.taker_book_side == BookSide(expected)

    def test_survives_taker_side_disappearing(self):
        m = TradeModel.model_validate(
            {"trade_id": "t", "ticker": "T", "count_fp": "1",
             "yes_price_dollars": "0.5", "no_price_dollars": "0.5",
             "taker_outcome_side": "no", "taker_book_side": "ask"})
        assert m.taker_book_side == BookSide.ASK


class TestRealWireShapes:
    """Authentic REST payload shapes, captured from the live API.

    Field names, types and value formats are verbatim from production
    responses; tickers and identifiers are anonymised. Hand-written mocks are
    what let the previous migration ship broken -- they asserted the parser
    against a payload shape the server had stopped sending.
    """

    ORDER_BUY_NO = {
        "action": "buy", "book_side": "ask", "outcome_side": "no", "side": "no",
        "client_order_id": "", "created_time": "2026-03-17T10:39:25.879377Z",
        "exchange_index": 0, "fill_count_fp": "82.00", "initial_count_fp": "198.00",
        "last_update_time": "2026-07-03T21:31:32.658318Z",
        "maker_fees_dollars": "0.000000", "maker_fill_cost_dollars": "62.320000",
        "no_price_dollars": "0.7600", "order_id": "00000000-0000-0000-0000-000000000001",
        "remaining_count_fp": "116.00", "status": "resting", "subaccount_number": 0,
        "taker_fees_dollars": "0.000000", "taker_fill_cost_dollars": "0.000000",
        "ticker": "KXTEST-26-A", "type": "limit",
        "user_id": "00000000-0000-0000-0000-000000000000", "yes_price_dollars": "0.2400",
    }

    ORDER_SELL_YES = {
        **ORDER_BUY_NO,
        "action": "sell", "side": "yes", "book_side": "ask", "outcome_side": "no",
        "order_id": "00000000-0000-0000-0000-000000000002",
    }

    FILL_SELL_NO = {
        "action": "sell", "book_side": "ask", "outcome_side": "no", "side": "no",
        "count_fp": "10.50", "created_time": "2026-05-02T18:02:11.101Z",
        "fee_cost": "0.010000", "fill_id": "00000000-0000-0000-0000-000000000003",
        "is_taker": False, "market_ticker": "KXTEST-26-A",
        "no_price_dollars": "0.8200", "order_id": "00000000-0000-0000-0000-000000000001",
        "subaccount_number": 0, "ticker": "KXTEST-26-A",
        "trade_id": "00000000-0000-0000-0000-000000000004",
        "ts": 1777827731, "yes_price_dollars": "0.1800",
    }

    TRADE = {
        "count_fp": "25.00", "created_time": "2026-07-25T22:10:03.1Z",
        "is_block_trade": False, "no_price_dollars": "0.8300",
        "taker_book_side": "bid", "taker_outcome_side": "yes", "taker_side": "yes",
        "ticker": "KXTEST-26-A", "trade_id": "00000000-0000-0000-0000-000000000005",
        "yes_price_dollars": "0.1700",
    }

    def test_order_buy_no_is_an_ask(self):
        m = OrderModel.model_validate(self.ORDER_BUY_NO)
        assert m.book_side == BookSide.ASK and m.is_ask
        assert m.subaccount_number == 0 and m.exchange_index == 0

    def test_order_sell_yes_is_also_an_ask(self):
        """Same resting order, opposite legacy representation."""
        m = OrderModel.model_validate(self.ORDER_SELL_YES)
        assert m.book_side == BookSide.ASK

    def test_fill_sell_no_is_an_ask_contradicting_the_published_table(self):
        """The published table says sell/no -> bid. Live fills say ask."""
        m = FillModel.model_validate(self.FILL_SELL_NO)
        assert m.book_side == BookSide.ASK
        assert m.yes_delta_fp < 0
        assert book_side_from_order_legacy("sell", "no") == "bid"  # the trap
        assert m.fee_cost_dollars == "0.010000"

    def test_trade_canonical_fields(self):
        m = TradeModel.model_validate(self.TRADE)
        assert m.taker_book_side == BookSide.BID
        assert m.is_block_trade is False

    def test_partially_filled_order_exposes_both_counts(self):
        """Needed to compute the amend `count` total correctly."""
        m = OrderModel.model_validate(self.ORDER_BUY_NO)
        assert m.fill_count_fp == "82.00" and m.remaining_count_fp == "116.00"
        assert m.initial_count_fp == "198.00"


class TestAmendCountSemantics:
    """`count` on AmendOrderV2Request is the TOTAL, not the new resting size.

    Spec: "Updated total/max fillable count for the order. Set this to the
    order's already filled count plus the desired resting remaining count."

    Defaulting to `remaining_count_fp` alone therefore silently cancels
    everything that has already filled -- on a 198-lot order with 82 filled,
    a plain reprice would drop the resting size from 116 to 34.
    """
    import json as _json

    def _client(self, mocker, order_payload):
        from pykalshi import KalshiClient
        c = mocker.MagicMock(spec=KalshiClient)
        return c

    def test_order_amend_sends_filled_plus_remaining(self, client, mock_response):
        import json
        from pykalshi.orders import Order
        from pykalshi.models import OrderModel

        order = Order(client, OrderModel.model_validate({
            "order_id": "o1", "ticker": "KXTEST", "status": "resting",
            "book_side": "ask", "yes_price_dollars": "0.2400",
            "fill_count_fp": "82.00", "remaining_count_fp": "116.00",
            "initial_count_fp": "198.00",
        }))
        client._session.request.return_value = mock_response(
            {"order_id": "o1", "remaining_count": "116.00", "ts_ms": 1})

        order.amend(yes_price_dollars="0.30")   # price-only reprice

        body = json.loads(client._session.request.call_args.kwargs["content"])
        assert body["count"] == "198.00", (
            "a price-only amend must preserve the filled portion; sending the "
            "bare remaining count would cancel 82 already-filled contracts"
        )
        assert body["side"] == "ask"      # canonical, not derived from action
        assert body["price"] == "0.3000"

    def test_portfolio_amend_hydrates_total_from_the_order(self, client, mock_response):
        import json
        client._session.request.side_effect = [
            mock_response({"order": {
                "order_id": "o1", "ticker": "KXTEST", "status": "resting",
                "book_side": "ask", "yes_price_dollars": "0.2400",
                "fill_count_fp": "82.00", "remaining_count_fp": "116.00"}}),
            mock_response({"order_id": "o1", "ts_ms": 1}),
        ]

        client.portfolio.amend_order("o1", yes_price_dollars="0.30")

        body = json.loads(client._session.request.call_args.kwargs["content"])
        assert body["count"] == "198.00"
        assert body["side"] == "ask"

    def test_amend_uses_book_side_when_legacy_fields_are_gone(self, client, mock_response):
        """The post-deprecation path: no action/side anywhere."""
        import json
        client._session.request.side_effect = [
            mock_response({"order": {
                "order_id": "o1", "ticker": "KXTEST", "status": "resting",
                "book_side": "bid", "yes_price_dollars": "0.1600",
                "fill_count_fp": "0.00", "remaining_count_fp": "800.00"}}),
            mock_response({"order_id": "o1", "ts_ms": 1}),
        ]

        client.portfolio.amend_order("o1", count_fp="900.00")

        body = json.loads(client._session.request.call_args.kwargs["content"])
        assert body["side"] == "bid"
        assert body["count"] == "900.00"   # caller-supplied total passes through


class TestWebSocketWireShapes:
    """WS models must match the wire. Several silently never populated.

    Payload shapes are from Kalshi's AsyncAPI examples plus the `required`
    lists on each channel.
    """

    def test_fill_exposes_market_ticker(self):
        """The wire sends market_ticker; the model only declared `ticker`, so
        it was always None and `msg.market_ticker` raised AttributeError --
        which meant every fill handler died on its first line."""
        from pykalshi.feed import FillMessage
        m = FillMessage.model_validate({
            "trade_id": "t", "order_id": "o", "market_ticker": "KXTEST",
            "is_taker": True, "side": "yes", "yes_price_dollars": "0.17",
            "count_fp": "10", "fee_cost": "0.01", "action": "buy",
            "outcome_side": "yes", "book_side": "bid", "ts": 1671899397,
            "ts_ms": 1671899397000, "post_position_fp": "5",
            "purchased_side": "yes",
        })
        assert m.market_ticker == "KXTEST"
        assert m.ticker == "KXTEST"            # alias kept for compatibility
        assert m.book_side == "bid"
        assert m.fee_cost == "0.01"            # required by spec, was missing
        assert m.post_position_fp == "5"       # required by spec, was missing
        assert m.ts_ms == 1671899397000

    def test_ws_fill_uses_the_fill_rule(self):
        from pykalshi.feed import FillMessage
        m = FillMessage.model_validate({
            "market_ticker": "KXTEST", "side": "yes", "action": "sell",
            "count_fp": "3"})
        assert m.book_side == "bid"   # order rule would wrongly say "ask"

    def test_orderbook_snapshot_field_names(self):
        """Wire uses *_fp. The model omitted the suffix, so both sides were
        None and OrderbookManager reset the book to empty on every snapshot."""
        from pykalshi.feed import OrderbookSnapshotMessage
        from pykalshi.orderbook import OrderbookManager
        snap = OrderbookSnapshotMessage.model_validate({
            "market_ticker": "KXTEST", "market_id": "m",
            "yes_dollars_fp": [["0.08", "300"], ["0.22", "333"]],
            "no_dollars_fp": [["0.54", "20"], ["0.56", "146"]],
        })
        assert snap.yes_dollars_fp and snap.no_dollars_fp
        assert snap.yes_dollars == snap.yes_dollars_fp   # alias

        mgr = OrderbookManager("KXTEST")
        mgr.apply_snapshot(snap.yes_dollars, snap.no_dollars)
        assert mgr.yes and mgr.no, "snapshot must not empty the book"
        assert mgr.best_bid == "0.22"

    def test_position_message_parses_instead_of_degrading_to_dict(self):
        """`ticker` was required but the wire sends `market_ticker`, so every
        frame raised ValidationError and fell back to a raw dict."""
        import json
        from pykalshi.feed import PositionMessage, _parse_message
        _, _, parsed, _ = _parse_message(json.dumps({
            "type": "market_position",
            "msg": {"user_id": "u", "market_ticker": "KXTEST",
                    "position_fp": "10", "position_cost_dollars": "1.70",
                    "realized_pnl_dollars": "0", "fees_paid_dollars": "0",
                    "position_fee_cost_dollars": "0", "volume_fp": "10"},
        }))
        assert isinstance(parsed, PositionMessage)
        assert parsed.market_ticker == "KXTEST"

    def test_order_group_updates_type_key_is_plural(self):
        import json
        from pykalshi.feed import OrderGroupUpdateMessage, _parse_message
        _, _, parsed, _ = _parse_message(json.dumps({
            "type": "order_group_updates",
            "msg": {"event_type": "triggered", "order_group_id": "g1",
                    "contracts_limit_fp": "100", "ts_ms": 5},
        }))
        assert isinstance(parsed, OrderGroupUpdateMessage)
        assert parsed.event_type == "triggered"

    def test_user_order_channel_is_modelled_and_routed(self):
        """Previously unmodelled: handlers got raw dicts, and the channel name
        you subscribe with (`user_orders`) never matched the frame type."""
        import json
        from pykalshi.feed import UserOrderMessage, _parse_message
        _, channel, parsed, _ = _parse_message(json.dumps({
            "type": "user_order",
            "msg": {"order_id": "o", "ticker": "KXTEST", "status": "resting",
                    "side": "yes", "is_yes": False, "outcome_side": "no",
                    "book_side": "ask", "yes_price_dollars": "0.17",
                    "remaining_count_fp": "800", "created_ts_ms": 1},
        }))
        assert isinstance(parsed, UserOrderMessage)
        assert channel == "user_orders"
        assert parsed.book_side == "ask"

    def test_ticker_dollar_fields_are_ints_under_the_wire_names(self):
        from pykalshi.feed import TickerMessage
        m = TickerMessage.model_validate({
            "market_ticker": "KXTEST", "market_id": "m",
            "dollar_volume": 12345, "dollar_open_interest": 999,
            "yes_bid_size_fp": "10", "yes_ask_size_fp": "12",
            "last_trade_size_fp": "3", "ts_ms": 7,
        })
        assert m.dollar_volume == 12345
        assert m.dollar_open_interest == 999
        assert m.yes_bid_size_fp == "10" and m.ts_ms == 7

    def test_legacy_pair_avoids_a_needless_fetch(self, client, mock_response):
        """Supplying action+side must not trigger a get_order.

        The V2 body needs book_side, but when the caller gives the legacy pair
        we can derive it locally. Fetching instead costs a round-trip on every
        amend and 404s against read-after-write lag right after a place.
        """
        import json
        from pykalshi.enums import Action, Side

        client._session.request.return_value = mock_response(
            {"order_id": "o1", "ts_ms": 1})

        client.portfolio.amend_order(
            "o1", count_fp="1", yes_price_dollars="0.02",
            ticker="KXTEST", action=Action.BUY, side=Side.NO,
        )

        assert client._session.request.call_count == 1, (
            "amend should not have fetched the order"
        )
        call = client._session.request.call_args
        assert call.args[0] == "POST"
        body = json.loads(call.kwargs["content"])
        assert body["side"] == "ask"       # buy NO -> ask, derived locally
        assert body["count"] == "1"


class TestFillDirectionAgainstParentOrder:
    """The fill rule, justified by the order that produced the fill.

    An order's direction is unambiguous. Joining every sell fill in a live
    account to its parent order gives, 9 times out of 9:

        fill sell/no  (book_side=ask) <- order sell/yes (book_side=ask, long no)
        fill sell/yes (book_side=bid) <- order sell/no  (book_side=bid, long yes)

    The legacy pair is INVERTED between the two surfaces for one unchanged
    order, while book_side is identical. So a fill reporting `sell/yes` came
    from a long-YES order and increased the yes position -- the opposite of
    what the order table gives when misapplied to the fill's own fields.

    Corroborated by Kalshi's changelog: "Both BUY YES or SELL NO result in
    purchased_side = YES", and bid == yes by definition.
    """

    PAIRS = [
        # (fill action/side, fill book_side, parent action/side, parent book_side, yes delta)
        ("sell", "no",  "ask", "sell", "yes", -1),
        ("sell", "yes", "bid", "sell", "no",  +1),
        ("buy",  "no",  "ask", "buy",  "no",  -1),
        ("buy",  "yes", "bid", "buy",  "yes", +1),
    ]

    @pytest.mark.parametrize(
        "f_action,f_side,book,p_action,p_side,delta", PAIRS)
    def test_fill_and_parent_agree_on_book_side(
            self, f_action, f_side, book, p_action, p_side, delta):
        fill = FillModel.model_validate({
            "trade_id": "t", "ticker": "T", "order_id": "o",
            "action": f_action, "side": f_side, "count_fp": "1",
            "yes_price_dollars": "0.50"})
        parent = OrderModel.model_validate({
            "order_id": "o", "ticker": "T", "status": "executed",
            "action": p_action, "side": p_side})

        assert fill.book_side == BookSide(book)
        assert parent.book_side == BookSide(book), (
            "fill and its parent order must agree on book_side even though "
            "their legacy (action, side) pairs differ"
        )
        assert fill.yes_delta_fp == delta

    def test_order_rule_misapplied_to_a_fill_inverts_the_sells(self):
        """Guards against 'just use action and side' being reintroduced.

        Deriving a fill's direction with the order mapper flips exactly the two
        sell rows -- the failure this whole module exists to prevent.
        """
        for action, side in (("sell", "yes"), ("sell", "no")):
            correct = book_side_from_fill_legacy(side)
            misapplied = book_side_from_order_legacy(action, side)
            assert correct != misapplied, (
                f"expected the order mapper to disagree on fill {action}/{side}"
            )
