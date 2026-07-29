"""Tests for multivariate event (MVE) collections, communications, and combo support."""

import pytest
from unittest.mock import ANY
from urllib.parse import parse_qsl, urlsplit

from pykalshi import (
    Market, Event, MveCollection, Communications,
    MveSelectedLeg, MveCollectionModel, AssociatedEventModel,
    RfqModel, QuoteModel, MarketModel,
)
from pykalshi.exceptions import ResourceNotFoundError


def _query_dict(client) -> dict:
    """Return the query params of the last requested URL as a dict."""
    call_url = client._session.request.call_args.args[1]
    return dict(parse_qsl(urlsplit(call_url).query))


# --- MarketModel MVE fields ---

class TestMarketModelMveFields:
    """Test that MarketModel correctly captures MVE fields."""

    def test_market_model_with_mve_fields(self):
        """Test MarketModel parses mve_collection_ticker, mve_selected_legs, is_provisional."""
        data = {
            "ticker": "KXMVE-COMBO-123",
            "event_ticker": "KXMVE-EVT",
            "status": "open",
            "mve_collection_ticker": "KXMVE-COL",
            "is_provisional": True,
            "mve_selected_legs": [
                {
                    "event_ticker": "EVT-A",
                    "market_ticker": "MKT-A",
                    "side": "yes",
                    "yes_settlement_value_dollars": "1.00",
                },
                {
                    "event_ticker": "EVT-B",
                    "market_ticker": "MKT-B",
                    "side": "no",
                },
            ],
        }
        model = MarketModel.model_validate(data)

        assert model.mve_collection_ticker == "KXMVE-COL"
        assert model.is_provisional is True
        assert model.mve_selected_legs is not None
        assert len(model.mve_selected_legs) == 2
        assert model.mve_selected_legs[0].event_ticker == "EVT-A"
        assert model.mve_selected_legs[0].market_ticker == "MKT-A"
        assert model.mve_selected_legs[0].side == "yes"
        assert model.mve_selected_legs[0].yes_settlement_value_dollars == "1.00"
        assert model.mve_selected_legs[1].yes_settlement_value_dollars is None

    def test_market_model_mve_fields_default_none(self):
        """Test MarketModel MVE fields default to None for non-MVE markets."""
        model = MarketModel(ticker="KXBTC-26JAN")
        assert model.mve_collection_ticker is None
        assert model.mve_selected_legs is None
        assert model.is_provisional is None

    def test_get_market_with_mve_data(self, client, mock_response):
        """Test fetching an MVE combo market returns MVE fields."""
        client._session.request.return_value = mock_response({
            "market": {
                "ticker": "KXMVE-COMBO",
                "event_ticker": "KXMVE-EVT",
                "status": "open",
                "mve_collection_ticker": "KXMVE-COL",
                "is_provisional": False,
                "mve_selected_legs": [
                    {"event_ticker": "E1", "market_ticker": "M1", "side": "yes"},
                ],
            }
        })

        market = client.get_market("KXMVE-COMBO")

        assert isinstance(market, Market)
        assert market.ticker == "KXMVE-COMBO"
        assert market.mve_collection_ticker == "KXMVE-COL"
        assert market.is_provisional is False
        assert market.mve_selected_legs is not None
        assert len(market.mve_selected_legs) == 1
        assert market.mve_selected_legs[0].side == "yes"


# --- MveSelectedLeg ---

class TestMveSelectedLeg:
    """Tests for MveSelectedLeg model."""

    def test_basic_fields(self):
        leg = MveSelectedLeg(event_ticker="E1", market_ticker="M1", side="yes")
        assert leg.event_ticker == "E1"
        assert leg.market_ticker == "M1"
        assert leg.side == "yes"
        assert leg.yes_settlement_value_dollars is None

    def test_with_settlement_value(self):
        leg = MveSelectedLeg(
            event_ticker="E1", market_ticker="M1", side="no",
            yes_settlement_value_dollars="0.70",
        )
        assert leg.yes_settlement_value_dollars == "0.70"

    def test_ignores_extra_fields(self):
        leg = MveSelectedLeg(
            event_ticker="E1", market_ticker="M1", side="yes",
            unknown_field="should_be_ignored",
        )
        assert leg.event_ticker == "E1"


# --- AssociatedEventModel ---

class TestAssociatedEventModel:
    """Tests for AssociatedEventModel."""

    def test_basic(self):
        ae = AssociatedEventModel(ticker="EVT-1")
        assert ae.ticker == "EVT-1"
        assert ae.is_yes_only is False
        assert ae.size_min_fp is None
        assert ae.size_max_fp is None
        assert ae.active_quoters is None

    def test_all_fields(self):
        ae = AssociatedEventModel(
            ticker="EVT-1", is_yes_only=True,
            size_min_fp="1.00", size_max_fp="3.00",
            active_quoters=["user-a", "user-b"],
        )
        assert ae.is_yes_only is True
        assert ae.size_min_fp == "1.00"
        assert ae.size_max_fp == "3.00"
        assert ae.active_quoters == ["user-a", "user-b"]


# --- MveCollectionModel ---

class TestMveCollectionModel:
    """Tests for MveCollectionModel."""

    def test_minimal(self):
        model = MveCollectionModel(collection_ticker="COL-1")
        assert model.collection_ticker == "COL-1"
        assert model.title is None
        assert model.associated_events is None
        assert model.is_ordered is False

    def test_full(self):
        model = MveCollectionModel(
            collection_ticker="COL-1",
            series_ticker="SER-1",
            title="Test Collection",
            description="A test combo collection",
            open_date="2026-01-01",
            close_date="2026-12-31",
            associated_events=[
                {"ticker": "E1", "is_yes_only": True, "size_min_fp": "1.00", "size_max_fp": "1.00"},
                {"ticker": "E2"},
            ],
            is_ordered=True,
            size_min_fp="2.00",
            size_max_fp="3.00",
            functional_description="Product of legs",
        )
        assert model.title == "Test Collection"
        assert len(model.associated_events) == 2
        assert model.associated_events[0].is_yes_only is True
        assert model.is_ordered is True
        assert model.size_min_fp == "2.00"


# --- RfqModel and QuoteModel ---

class TestRfqModel:
    """Tests for RfqModel."""

    def test_rfq_model_from_id_field(self):
        """Test RfqModel parses 'id' alias."""
        rfq = RfqModel.model_validate({"id": "rfq-abc", "market_ticker": "KXMVE-X"})
        assert rfq.rfq_id == "rfq-abc"
        assert rfq.market_ticker == "KXMVE-X"

    def test_rfq_model_from_rfq_id_field(self):
        """Test RfqModel parses 'rfq_id' field."""
        rfq = RfqModel.model_validate({"rfq_id": "rfq-abc"})
        assert rfq.rfq_id == "rfq-abc"

    def test_rfq_model_full_fields(self):
        rfq = RfqModel.model_validate({
            "rfq_id": "rfq-1",
            "market_ticker": "KXMVE-COMBO",
            "status": "active",
            "contracts_fp": "10.00",
            "rest_remainder": True,
            "mve_collection_ticker": "COL-1",
            "mve_selected_legs": [
                {"event_ticker": "E1", "market_ticker": "M1", "side": "yes"},
            ],
            "created_ts": "2026-01-15T10:00:00Z",
            "creator_id": "user-123",
        })
        assert rfq.status == "active"
        assert rfq.contracts_fp == "10.00"
        assert rfq.mve_collection_ticker == "COL-1"
        assert len(rfq.mve_selected_legs) == 1


class TestQuoteModel:
    """Tests for QuoteModel."""

    def test_quote_model_from_id_field(self):
        quote = QuoteModel.model_validate({"id": "q-1", "rfq_id": "rfq-1"})
        assert quote.quote_id == "q-1"

    def test_quote_model_from_quote_id_field(self):
        quote = QuoteModel.model_validate({"quote_id": "q-1"})
        assert quote.quote_id == "q-1"

    def test_quote_model_full_fields(self):
        quote = QuoteModel.model_validate({
            "quote_id": "q-1",
            "rfq_id": "rfq-1",
            "market_ticker": "KXMVE-COMBO",
            "status": "pending",
            "yes_bid_dollars": "0.45",
            "no_bid_dollars": "0.55",
            "rest_remainder": False,
            "created_ts": "2026-01-15T10:05:00Z",
        })
        assert quote.yes_bid_dollars == "0.45"
        assert quote.no_bid_dollars == "0.55"
        assert quote.status == "pending"


# --- MveCollection domain class ---

class TestGetMveCollection:
    """Tests for fetching a single MVE collection."""

    def test_get_mve_collection(self, client, mock_response):
        """Test fetching a collection by ticker."""
        client._session.request.return_value = mock_response({
            "multivariate_contract": {
                "collection_ticker": "COL-PRES",
                "series_ticker": "KXPRES",
                "title": "Presidential Combo",
                "associated_events": [
                    {"ticker": "EVT-A", "is_yes_only": True},
                    {"ticker": "EVT-B"},
                ],
                "size_min_fp": "2.00",
                "size_max_fp": "5.00",
            }
        })

        col = client.get_mve_collection("COL-PRES")

        assert isinstance(col, MveCollection)
        assert col.collection_ticker == "COL-PRES"
        assert col.title == "Presidential Combo"
        assert col.series_ticker == "KXPRES"
        assert len(col.data.associated_events) == 2

    def test_get_mve_collection_not_found(self, client, mock_response):
        """Test fetching non-existent collection raises error."""
        client._session.request.return_value = mock_response(
            {"message": "Not found"}, status_code=404
        )

        with pytest.raises(ResourceNotFoundError):
            client.get_mve_collection("NONEXISTENT")


class TestGetMveCollections:
    """Tests for listing MVE collections."""

    def test_get_mve_collections(self, client, mock_response):
        """Test listing collections."""
        client._session.request.return_value = mock_response({
            "multivariate_contracts": [
                {"collection_ticker": "COL-1", "title": "Combo A"},
                {"collection_ticker": "COL-2", "title": "Combo B"},
            ],
            "cursor": "",
        })

        cols = client.get_mve_collections()

        assert len(cols) == 2
        assert all(isinstance(c, MveCollection) for c in cols)
        assert cols[0].collection_ticker == "COL-1"
        assert cols[1].title == "Combo B"

    def test_get_mve_collections_with_filters(self, client, mock_response):
        """Test listing collections with filters."""
        client._session.request.return_value = mock_response({
            "multivariate_contracts": [],
            "cursor": "",
        })

        client.get_mve_collections(
            status="open",
            series_ticker="KXPRES",
            limit=50,
        )

        call_url = client._session.request.call_args.args[1]
        assert "status=open" in call_url
        assert "series_ticker=KXPRES" in call_url
        assert "limit=50" in call_url

    def test_get_mve_collections_pagination(self, client, mock_response):
        """Test collection pagination with fetch_all."""
        client._session.request.side_effect = [
            mock_response({
                "multivariate_contracts": [{"collection_ticker": "COL-1"}],
                "cursor": "page2",
            }),
            mock_response({
                "multivariate_contracts": [{"collection_ticker": "COL-2"}],
                "cursor": "",
            }),
        ]

        cols = client.get_mve_collections(fetch_all=True)

        assert len(cols) == 2
        assert client._session.request.call_count == 2


class TestGetMultivariateEvents:
    """Tests for fetching multivariate events."""

    def test_get_multivariate_events(self, client, mock_response):
        """Test fetching MVE events."""
        client._session.request.return_value = mock_response({
            "events": [
                {"event_ticker": "MVE-E1", "series_ticker": "S1", "mutually_exclusive": True},
                {"event_ticker": "MVE-E2", "series_ticker": "S1"},
            ],
            "cursor": "",
        })

        events = client.get_multivariate_events()

        assert len(events) == 2
        assert all(isinstance(e, Event) for e in events)
        assert events[0].event_ticker == "MVE-E1"
        assert events[0].mutually_exclusive is True

    def test_get_multivariate_events_by_collection(self, client, mock_response):
        """Test filtering MVE events by collection ticker."""
        client._session.request.return_value = mock_response({
            "events": [
                {"event_ticker": "MVE-E1", "series_ticker": "S1"},
            ],
            "cursor": "",
        })

        client.get_multivariate_events(collection_ticker="COL-1")

        call_url = client._session.request.call_args.args[1]
        assert "collection_ticker=COL-1" in call_url

    def test_get_multivariate_events_by_series(self, client, mock_response):
        """Test filtering MVE events by series ticker."""
        client._session.request.return_value = mock_response({
            "events": [],
            "cursor": "",
        })

        client.get_multivariate_events(series_ticker="KXPRES")

        call_url = client._session.request.call_args.args[1]
        assert "series_ticker=KXPRES" in call_url

    def test_get_multivariate_events_with_nested_markets(self, client, mock_response):
        """Test requesting nested markets in MVE events."""
        client._session.request.return_value = mock_response({
            "events": [],
            "cursor": "",
        })

        client.get_multivariate_events(with_nested_markets=True)

        call_url = client._session.request.call_args.args[1]
        assert "with_nested_markets=true" in call_url

    def test_get_multivariate_events_pagination(self, client, mock_response):
        """Test MVE events pagination with fetch_all."""
        client._session.request.side_effect = [
            mock_response({
                "events": [{"event_ticker": "E1", "series_ticker": "S"}],
                "cursor": "next",
            }),
            mock_response({
                "events": [{"event_ticker": "E2", "series_ticker": "S"}],
                "cursor": "",
            }),
        ]

        events = client.get_multivariate_events(fetch_all=True)

        assert len(events) == 2
        assert client._session.request.call_count == 2


# --- MveCollection domain methods ---

class TestMveCollectionCreateMarket:
    """Tests for MveCollection.create_market()."""

    def test_create_market(self, client, mock_response):
        """Test creating a combo market in a collection."""
        client._session.request.side_effect = [
            # First call: get collection
            mock_response({
                "multivariate_contract": {
                    "collection_ticker": "COL-1",
                    "title": "Test Collection",
                    "associated_events": [
                        {"ticker": "EVT-A"},
                        {"ticker": "EVT-B"},
                    ],
                }
            }),
            # Second call: create market
            mock_response({
                "market": {
                    "ticker": "KXMVE-COL1-ABC",
                    "event_ticker": "KXMVE-EVT",
                    "status": "open",
                    "mve_collection_ticker": "COL-1",
                    "mve_selected_legs": [
                        {"event_ticker": "EVT-A", "market_ticker": "MKT-A", "side": "yes"},
                        {"event_ticker": "EVT-B", "market_ticker": "MKT-B", "side": "no"},
                    ],
                }
            }),
        ]

        col = client.get_mve_collection("COL-1")
        market = col.create_market([
            {"market_ticker": "MKT-A", "event_ticker": "EVT-A", "side": "yes"},
            {"market_ticker": "MKT-B", "event_ticker": "EVT-B", "side": "no"},
        ])

        assert isinstance(market, Market)
        assert market.ticker == "KXMVE-COL1-ABC"
        assert market.mve_collection_ticker == "COL-1"
        assert len(market.mve_selected_legs) == 2

        # Verify the POST was sent to the right endpoint
        post_url = client._session.request.call_args_list[1].args[1]
        assert "/multivariate_event_collections/COL-1" in post_url


class TestMveCollectionLookupTicker:
    """Tests for MveCollection.lookup_ticker()."""

    def test_lookup_ticker(self, client, mock_response):
        """Test looking up a combo ticker."""
        client._session.request.side_effect = [
            mock_response({
                "multivariate_contract": {"collection_ticker": "COL-1", "title": "Test"}
            }),
            mock_response({
                "market_ticker": "KXMVE-COL1-XYZ",
                "event_ticker": "KXMVE-EVT-XYZ",
            }),
        ]

        col = client.get_mve_collection("COL-1")
        result = col.lookup_ticker([
            {"market_ticker": "MKT-A", "event_ticker": "EVT-A", "side": "yes"},
        ])

        assert result["market_ticker"] == "KXMVE-COL1-XYZ"

    def test_lookup_ticker_not_found(self, client, mock_response):
        """Test looking up an uncreated combo returns 404."""
        client._session.request.side_effect = [
            mock_response({
                "multivariate_contract": {"collection_ticker": "COL-1", "title": "Test"}
            }),
            mock_response({"message": "Not found"}, status_code=404),
        ]

        col = client.get_mve_collection("COL-1")

        with pytest.raises(ResourceNotFoundError):
            col.lookup_ticker([
                {"market_ticker": "MKT-X", "event_ticker": "EVT-X", "side": "yes"},
            ])


class TestMveCollectionGetEvents:
    """Tests for MveCollection.get_events()."""

    def test_get_events(self, client, mock_response):
        """Test getting events for a collection delegates to get_multivariate_events."""
        client._session.request.side_effect = [
            mock_response({
                "multivariate_contract": {"collection_ticker": "COL-1", "title": "Test"}
            }),
            mock_response({
                "events": [
                    {"event_ticker": "MVE-E1", "series_ticker": "S1"},
                ],
                "cursor": "",
            }),
        ]

        col = client.get_mve_collection("COL-1")
        events = col.get_events()

        assert len(events) == 1
        assert events[0].event_ticker == "MVE-E1"

        # Verify collection_ticker filter was passed
        call_url = client._session.request.call_args.args[1]
        assert "collection_ticker=COL-1" in call_url


class TestMveCollectionObject:
    """Tests for MveCollection object methods."""

    def test_repr(self, client, mock_response):
        """Test MveCollection repr."""
        client._session.request.return_value = mock_response({
            "multivariate_contract": {
                "collection_ticker": "COL-1",
                "title": "Presidential Combo",
                "associated_events": [{"ticker": "E1"}, {"ticker": "E2"}],
            }
        })

        col = client.get_mve_collection("COL-1")
        r = repr(col)

        assert "COL-1" in r
        assert "Presidential Combo" in r
        assert "2 events" in r

    def test_equality(self, client, mock_response):
        """Test MveCollection equality is based on collection_ticker."""
        client._session.request.side_effect = [
            mock_response({"multivariate_contract": {"collection_ticker": "COL-1"}}),
            mock_response({"multivariate_contract": {"collection_ticker": "COL-1"}}),
            mock_response({"multivariate_contract": {"collection_ticker": "COL-2"}}),
        ]

        c1 = client.get_mve_collection("COL-1")
        c2 = client.get_mve_collection("COL-1")
        c3 = client.get_mve_collection("COL-2")

        assert c1 == c2
        assert c1 != c3
        assert hash(c1) == hash(c2)

    def test_attribute_delegation(self, client, mock_response):
        """Test MveCollection delegates unknown attributes to data."""
        client._session.request.return_value = mock_response({
            "multivariate_contract": {
                "collection_ticker": "COL-1",
                "description": "A combo collection",
                "is_ordered": True,
                "functional_description": "Product of legs",
            }
        })

        col = client.get_mve_collection("COL-1")

        assert col.description == "A combo collection"
        assert col.is_ordered is True
        assert col.functional_description == "Product of legs"


# --- Communications (RFQ / Quotes) ---

class TestCommunicationsCreateRfq:
    """Tests for Communications.create_rfq()."""

    def test_create_rfq(self, client, mock_response):
        """Test creating an RFQ."""
        client._session.request.return_value = mock_response({
            "rfq": {
                "rfq_id": "rfq-001",
                "market_ticker": "KXMVE-COMBO",
                "status": "active",
                "contracts_fp": "10.00",
            }
        })

        rfq = client.communications.create_rfq("KXMVE-COMBO", contracts_fp="10.00")

        assert isinstance(rfq, RfqModel)
        assert rfq.rfq_id == "rfq-001"
        assert rfq.market_ticker == "KXMVE-COMBO"
        assert rfq.contracts_fp == "10.00"

        # Verify POST body
        import json
        call_kwargs = client._session.request.call_args
        body = json.loads(call_kwargs.kwargs.get("content", call_kwargs[1].get("content", "")))
        assert body["market_ticker"] == "KXMVE-COMBO"
        assert body["contracts_fp"] == "10.00"

    def test_create_rfq_with_target_cost(self, client, mock_response):
        """Test creating an RFQ with target cost in dollars."""
        client._session.request.return_value = mock_response({
            "rfq": {
                "rfq_id": "rfq-002",
                "market_ticker": "KXMVE-COMBO",
                "status": "active",
                "target_cost_dollars": "25.00",
            }
        })

        rfq = client.communications.create_rfq(
            "KXMVE-COMBO", target_cost_dollars="25.00",
        )

        assert rfq.target_cost_dollars == "25.00"

    def test_create_rfq_with_rest_remainder(self, client, mock_response):
        """Test creating an RFQ with rest_remainder flag."""
        client._session.request.return_value = mock_response({
            "rfq": {
                "rfq_id": "rfq-003",
                "market_ticker": "KXMVE-COMBO",
                "status": "active",
                "rest_remainder": True,
            }
        })

        rfq = client.communications.create_rfq(
            "KXMVE-COMBO", contracts_fp="5.00", rest_remainder=True,
        )

        assert rfq.rest_remainder is True


class TestCommunicationsGetRfqs:
    """Tests for Communications.get_rfqs()."""

    def test_get_rfqs(self, client, mock_response):
        """Test listing RFQs."""
        client._session.request.return_value = mock_response({
            "rfqs": [
                {"rfq_id": "rfq-001", "market_ticker": "KXMVE-A", "status": "active"},
                {"rfq_id": "rfq-002", "market_ticker": "KXMVE-B", "status": "expired"},
            ],
            "cursor": "",
        })

        rfqs = client.communications.get_rfqs()

        assert len(rfqs) == 2
        assert all(isinstance(r, RfqModel) for r in rfqs)
        assert rfqs[0].rfq_id == "rfq-001"
        assert rfqs[1].status == "expired"

    def test_get_rfqs_default_query(self, client, mock_response):
        """With no filters, only the (spec-default) limit is sent."""
        client._session.request.return_value = mock_response({
            "rfqs": [],
            "cursor": "",
        })

        client.communications.get_rfqs()

        assert _query_dict(client) == {"limit": "100"}

    def test_get_rfqs_with_filters(self, client, mock_response):
        """All documented filters are sent, exactly as named in the spec."""
        client._session.request.return_value = mock_response({
            "rfqs": [],
            "cursor": "",
        })

        client.communications.get_rfqs(
            market_ticker="kxmve-combo",
            event_ticker="kxmve-evt",
            status="open",
            user_filter="self",
            subaccount=3,
            limit=50,
            cursor="cur-1",
        )

        assert _query_dict(client) == {
            "market_ticker": "KXMVE-COMBO",
            "event_ticker": "KXMVE-EVT",
            "status": "open",
            "user_filter": "self",
            "subaccount": "3",
            "limit": "50",
            "cursor": "cur-1",
        }

    def test_get_rfqs_creator_user_id_deprecated(self, client, mock_response):
        """creator_user_id still works but raises a DeprecationWarning."""
        client._session.request.return_value = mock_response({
            "rfqs": [],
            "cursor": "",
        })

        with pytest.warns(DeprecationWarning, match="user_filter"):
            client.communications.get_rfqs(creator_user_id="user-1")

        assert _query_dict(client) == {"creator_user_id": "user-1", "limit": "100"}

    def test_get_rfqs_rejects_mve_collection_ticker(self, client, mock_response):
        """The undocumented mve_collection_ticker filter is rejected, not sent."""
        with pytest.raises(TypeError, match="mve_collection_ticker"):
            client.communications.get_rfqs(mve_collection_ticker="COL-1")

        client._session.request.assert_not_called()

    def test_get_rfqs_extra_params_passthrough(self, client, mock_response):
        """Unknown kwargs pass through as query params (forward compatibility)."""
        client._session.request.return_value = mock_response({
            "rfqs": [],
            "cursor": "",
        })

        client.communications.get_rfqs(future_param="x")

        assert _query_dict(client) == {"future_param": "x", "limit": "100"}

    def test_get_rfqs_pagination(self, client, mock_response):
        """Test RFQ pagination with fetch_all."""
        client._session.request.side_effect = [
            mock_response({
                "rfqs": [{"rfq_id": "rfq-001"}],
                "cursor": "next",
            }),
            mock_response({
                "rfqs": [{"rfq_id": "rfq-002"}],
                "cursor": "",
            }),
        ]

        rfqs = client.communications.get_rfqs(fetch_all=True)

        assert len(rfqs) == 2
        assert client._session.request.call_count == 2


class TestCommunicationsGetRfq:
    """Tests for Communications.get_rfq()."""

    def test_get_rfq(self, client, mock_response):
        """Test fetching a single RFQ."""
        client._session.request.return_value = mock_response({
            "rfq": {
                "rfq_id": "rfq-001",
                "market_ticker": "KXMVE-COMBO",
                "status": "active",
                "contracts_fp": "10.00",
                "mve_collection_ticker": "COL-1",
                "mve_selected_legs": [
                    {"event_ticker": "E1", "market_ticker": "M1", "side": "yes"},
                ],
            }
        })

        rfq = client.communications.get_rfq("rfq-001")

        assert isinstance(rfq, RfqModel)
        assert rfq.rfq_id == "rfq-001"
        assert rfq.contracts_fp == "10.00"
        assert rfq.mve_selected_legs is not None
        assert len(rfq.mve_selected_legs) == 1

    def test_get_rfq_not_found(self, client, mock_response):
        """Test fetching non-existent RFQ raises error."""
        client._session.request.return_value = mock_response(
            {"message": "Not found"}, status_code=404
        )

        with pytest.raises(ResourceNotFoundError):
            client.communications.get_rfq("nonexistent")


class TestCommunicationsCreateQuote:
    """Tests for Communications.create_quote()."""

    def test_create_quote(self, client, mock_response):
        """Test creating a quote in response to an RFQ."""
        client._session.request.return_value = mock_response({
            "quote": {
                "quote_id": "q-001",
                "rfq_id": "rfq-001",
                "market_ticker": "KXMVE-COMBO",
                "status": "pending",
                "yes_bid_dollars": "0.45",
                "no_bid_dollars": "0.55",
            }
        })

        quote = client.communications.create_quote(
            "rfq-001", yes_bid="0.45", no_bid="0.55",
        )

        assert isinstance(quote, QuoteModel)
        assert quote.quote_id == "q-001"
        assert quote.rfq_id == "rfq-001"
        assert quote.yes_bid_dollars == "0.45"
        assert quote.no_bid_dollars == "0.55"

    def test_create_quote_zero_bid(self, client, mock_response):
        """Test creating a quote with zero bids."""
        client._session.request.return_value = mock_response({
            "quote": {
                "quote_id": "q-002",
                "rfq_id": "rfq-001",
                "yes_bid_dollars": "0.30",
                "no_bid_dollars": "0.00",
            }
        })

        quote = client.communications.create_quote(
            "rfq-001", yes_bid="0.30", no_bid="0.00",
        )

        assert quote.yes_bid_dollars == "0.30"
        assert quote.no_bid_dollars == "0.00"


class TestCommunicationsGetQuotes:
    """Tests for Communications.get_quotes()."""

    def test_get_quotes(self, client, mock_response):
        """Test listing quotes."""
        client._session.request.return_value = mock_response({
            "quotes": [
                {"quote_id": "q-001", "rfq_id": "rfq-001", "status": "pending"},
                {"quote_id": "q-002", "rfq_id": "rfq-001", "status": "accepted"},
            ],
            "cursor": "",
        })

        quotes = client.communications.get_quotes()

        assert len(quotes) == 2
        assert all(isinstance(q, QuoteModel) for q in quotes)

    def test_get_quotes_default_query(self, client, mock_response):
        """With no filters, only the (spec-default) limit is sent."""
        client._session.request.return_value = mock_response({
            "quotes": [],
            "cursor": "",
        })

        client.communications.get_quotes()

        assert _query_dict(client) == {"limit": "500"}

    def test_get_quotes_with_filters(self, client, mock_response):
        """All documented filters are sent, exactly as named in the spec."""
        client._session.request.return_value = mock_response({
            "quotes": [],
            "cursor": "",
        })

        client.communications.get_quotes(
            user_filter="self",
            rfq_user_filter="self",
            rfq_id="rfq-001",
            status="open",
            min_ts=1700000000,
            max_ts=1800000000,
            rfq_creator_subtrader_id="sub-1",
            limit=200,
            cursor="cur-1",
        )

        assert _query_dict(client) == {
            "user_filter": "self",
            "rfq_user_filter": "self",
            "rfq_id": "rfq-001",
            "status": "open",
            "min_ts": "1700000000",
            "max_ts": "1800000000",
            "rfq_creator_subtrader_id": "sub-1",
            "limit": "200",
            "cursor": "cur-1",
        }

    def test_get_quotes_rejects_market_ticker(self, client, mock_response):
        """market_ticker was removed from the API (2026-06-20): loud failure."""
        with pytest.raises(TypeError, match="market_ticker"):
            client.communications.get_quotes(market_ticker="KXMVE-COMBO")

        client._session.request.assert_not_called()

    def test_get_quotes_rejects_event_ticker(self, client, mock_response):
        """event_ticker was likewise removed from the API: loud failure."""
        with pytest.raises(TypeError, match="event_ticker"):
            client.communications.get_quotes(event_ticker="KXMVE-EVT")

        client._session.request.assert_not_called()

    def test_get_quotes_creator_user_id_alias(self, client, mock_response):
        """creator_user_id warns and maps onto quote_creator_user_id."""
        client._session.request.return_value = mock_response({
            "quotes": [],
            "cursor": "",
        })

        with pytest.warns(DeprecationWarning, match="quote_creator_user_id"):
            client.communications.get_quotes(creator_user_id="user-1")

        assert _query_dict(client) == {
            "quote_creator_user_id": "user-1",
            "limit": "500",
        }

    def test_get_quotes_deprecated_id_filters_warn(self, client, mock_response):
        """API-deprecated ID filters still work but raise DeprecationWarning."""
        client._session.request.return_value = mock_response({
            "quotes": [],
            "cursor": "",
        })

        with pytest.warns(DeprecationWarning, match="user_filter"):
            client.communications.get_quotes(quote_creator_user_id="user-1")
        assert _query_dict(client) == {
            "quote_creator_user_id": "user-1",
            "limit": "500",
        }

        with pytest.warns(DeprecationWarning, match="rfq_user_filter"):
            client.communications.get_quotes(rfq_creator_user_id="user-2")
        assert _query_dict(client) == {
            "rfq_creator_user_id": "user-2",
            "limit": "500",
        }

    def test_get_quotes_extra_params_passthrough(self, client, mock_response):
        """Unknown kwargs pass through as query params (forward compatibility)."""
        client._session.request.return_value = mock_response({
            "quotes": [],
            "cursor": "",
        })

        client.communications.get_quotes(future_param="x")

        assert _query_dict(client) == {"future_param": "x", "limit": "500"}


# --- Workflow tests ---

class TestMveWorkflow:
    """End-to-end workflow tests for MVE combo trading."""

    def test_discover_and_create_combo(self, client, mock_response):
        """Test full workflow: discover collection -> create combo market."""
        client._session.request.side_effect = [
            # 1. List collections
            mock_response({
                "multivariate_contracts": [
                    {
                        "collection_ticker": "COL-PRES",
                        "title": "Presidential Combos",
                        "series_ticker": "KXPRES",
                        "associated_events": [
                            {"ticker": "PRES-DEM", "is_yes_only": True},
                            {"ticker": "PRES-REP", "is_yes_only": True},
                        ],
                        "size_min_fp": "2.00",
                        "size_max_fp": "2.00",
                    },
                ],
                "cursor": "",
            }),
            # 2. Create combo market
            mock_response({
                "market": {
                    "ticker": "KXMVE-PRES-COMBO1",
                    "event_ticker": "KXMVE-PRES-EVT",
                    "status": "open",
                    "yes_bid_dollars": "0.30",
                    "yes_ask_dollars": "0.35",
                    "mve_collection_ticker": "COL-PRES",
                    "mve_selected_legs": [
                        {"event_ticker": "PRES-DEM", "market_ticker": "DEM-BIDEN", "side": "yes"},
                        {"event_ticker": "PRES-REP", "market_ticker": "REP-TRUMP", "side": "yes"},
                    ],
                }
            }),
        ]

        # Step 1: Discover collections
        collections = client.get_mve_collections(status="open")
        assert len(collections) == 1
        col = collections[0]
        assert col.collection_ticker == "COL-PRES"

        # Step 2: Create a combo market
        market = col.create_market([
            {"market_ticker": "DEM-BIDEN", "event_ticker": "PRES-DEM", "side": "yes"},
            {"market_ticker": "REP-TRUMP", "event_ticker": "PRES-REP", "side": "yes"},
        ])

        assert market.ticker == "KXMVE-PRES-COMBO1"
        assert market.mve_collection_ticker == "COL-PRES"
        assert len(market.mve_selected_legs) == 2
        assert market.yes_bid_dollars == "0.30"

    def test_rfq_quote_workflow(self, client, mock_response):
        """Test RFQ -> Quote workflow for combo trading."""
        client._session.request.side_effect = [
            # 1. Create RFQ
            mock_response({
                "rfq": {
                    "rfq_id": "rfq-xyz",
                    "market_ticker": "KXMVE-COMBO",
                    "status": "active",
                    "contracts_fp": "5.00",
                }
            }),
            # 2. List RFQs (to see what's out there)
            mock_response({
                "rfqs": [
                    {"rfq_id": "rfq-xyz", "market_ticker": "KXMVE-COMBO", "status": "active", "contracts_fp": "5.00"},
                ],
                "cursor": "",
            }),
            # 3. Create quote in response
            mock_response({
                "quote": {
                    "quote_id": "q-abc",
                    "rfq_id": "rfq-xyz",
                    "market_ticker": "KXMVE-COMBO",
                    "status": "pending",
                    "yes_bid_dollars": "0.40",
                    "no_bid_dollars": "0.60",
                }
            }),
        ]

        # Step 1: Create RFQ
        rfq = client.communications.create_rfq("KXMVE-COMBO", contracts_fp="5.00")
        assert rfq.rfq_id == "rfq-xyz"
        assert rfq.status == "active"

        # Step 2: List active RFQs
        rfqs = client.communications.get_rfqs(status="active")
        assert len(rfqs) == 1

        # Step 3: Respond with a quote
        quote = client.communications.create_quote(
            rfq.rfq_id, yes_bid="0.40", no_bid="0.60",
        )
        assert quote.quote_id == "q-abc"
        assert quote.rfq_id == "rfq-xyz"
        assert quote.yes_bid_dollars == "0.40"


class TestCommunicationsCachedProperty:
    """Test that client.communications is a cached property."""

    def test_same_instance(self, client):
        """Test that accessing communications returns the same instance."""
        comm1 = client.communications
        comm2 = client.communications
        assert comm1 is comm2
        assert isinstance(comm1, Communications)
