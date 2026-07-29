"""Integration tests for multivariate event collections, combo markets, and communications.

These tests run against the Kalshi Demo API with real data.
MVE collections/combos may not always be available on demo,
so tests skip gracefully when there's no data.
"""

from decimal import Decimal

import pytest
from pykalshi import (
    MveCollection, Event, Market,
    MveCollectionModel, MveSelectedLeg, RfqModel, QuoteModel,
)
from pykalshi.exceptions import KalshiAPIError, ResourceNotFoundError


class TestMveCollections:
    """Tests for MVE collection discovery endpoints."""

    def test_get_mve_collections(self, client):
        """List MVE collections returns list of MveCollection objects."""
        collections = client.get_mve_collections(limit=10)

        assert isinstance(collections, list)
        if collections:
            col = collections[0]
            assert isinstance(col, MveCollection)
            assert col.collection_ticker is not None
            assert len(col.collection_ticker) > 0

    def test_get_mve_collections_with_status_filter(self, client):
        """List MVE collections with status filter."""
        collections = client.get_mve_collections(status="open", limit=10)

        assert isinstance(collections, list)
        # All returned should be open (if any exist)

    def test_get_single_mve_collection(self, client):
        """Get a single MVE collection by ticker."""
        collections = client.get_mve_collections(limit=1)
        if not collections:
            pytest.skip("No MVE collections available on demo")

        ticker = collections[0].collection_ticker
        col = client.get_mve_collection(ticker)

        assert isinstance(col, MveCollection)
        assert col.collection_ticker == ticker
        assert col.data is not None

    def test_mve_collection_has_associated_events(self, client):
        """MVE collections should have associated events."""
        collections = client.get_mve_collections(limit=10)
        if not collections:
            pytest.skip("No MVE collections available on demo")

        # Find one with associated events
        for col in collections:
            if col.data.associated_events:
                assert len(col.data.associated_events) > 0
                ae = col.data.associated_events[0]
                assert ae.ticker is not None
                return

        pytest.skip("No MVE collections with associated events found")

    def test_mve_collection_repr(self, client):
        """MveCollection repr is well-formed."""
        collections = client.get_mve_collections(limit=1)
        if not collections:
            pytest.skip("No MVE collections available on demo")

        r = repr(collections[0])
        assert r.startswith("<MveCollection ")
        assert r.endswith(">")
        assert collections[0].collection_ticker in r

    def test_invalid_collection_ticker(self, client):
        """Invalid collection ticker raises error."""
        with pytest.raises(KalshiAPIError):
            client.get_mve_collection("NONEXISTENT-COLLECTION-XYZ-999")


class TestMultivariateEvents:
    """Tests for the /events/multivariate endpoint."""

    def test_get_multivariate_events(self, client):
        """List multivariate events returns Event objects."""
        events = client.get_multivariate_events(limit=10)

        assert isinstance(events, list)
        if events:
            e = events[0]
            assert isinstance(e, Event)
            assert e.event_ticker is not None

    def test_get_multivariate_events_by_collection(self, client):
        """Filter multivariate events by collection ticker."""
        collections = client.get_mve_collections(limit=1)
        if not collections:
            pytest.skip("No MVE collections available on demo")

        events = client.get_multivariate_events(
            collection_ticker=collections[0].collection_ticker, limit=10
        )

        assert isinstance(events, list)
        # Events should all belong to this collection's series
        if events:
            assert isinstance(events[0], Event)

    def test_get_multivariate_events_by_series(self, client):
        """Filter multivariate events by series ticker."""
        collections = client.get_mve_collections(limit=5)
        if not collections:
            pytest.skip("No MVE collections available on demo")

        # Find a collection with a series_ticker
        for col in collections:
            if col.series_ticker:
                events = client.get_multivariate_events(
                    series_ticker=col.series_ticker, limit=5
                )
                assert isinstance(events, list)
                return

        pytest.skip("No MVE collections with series_ticker found")


class TestMveCollectionNavigation:
    """Tests for MveCollection domain methods."""

    def test_collection_get_events(self, client):
        """MveCollection.get_events() delegates to get_multivariate_events."""
        collections = client.get_mve_collections(limit=5)
        if not collections:
            pytest.skip("No MVE collections available on demo")

        for col in collections:
            events = col.get_events()
            assert isinstance(events, list)
            if events:
                assert isinstance(events[0], Event)
                return

        # No events found in any collection, that's ok
        assert True


class TestMveMarketFields:
    """Tests that MVE fields are properly captured on Market objects."""

    def test_mve_filter_exclude(self, client):
        """mve_filter='exclude' removes combo markets."""
        markets = client.get_markets(limit=10, mve_filter="exclude")

        assert isinstance(markets, list)
        for m in markets:
            # Excluded markets should not have KXMVE prefix
            assert not m.ticker.startswith("KXMVE")

    def test_mve_filter_only(self, client):
        """mve_filter='only' returns only combo markets."""
        markets = client.get_markets(limit=10, mve_filter="only")

        assert isinstance(markets, list)
        if markets:
            # All should be MVE combo markets
            for m in markets:
                assert m.ticker.startswith("KXMVE")
                # Should have MVE fields populated
                assert m.mve_collection_ticker is not None

    def test_mve_market_has_selected_legs(self, client):
        """MVE combo markets should have mve_selected_legs populated."""
        markets = client.get_markets(limit=10, mve_filter="only")
        if not markets:
            pytest.skip("No MVE combo markets available on demo")

        for m in markets:
            if m.mve_selected_legs:
                assert len(m.mve_selected_legs) > 0
                leg = m.mve_selected_legs[0]
                assert isinstance(leg, MveSelectedLeg)
                assert leg.event_ticker is not None
                assert leg.market_ticker is not None
                assert leg.side in ("yes", "no")
                return

        pytest.skip("No MVE markets with selected legs found")


class TestCommunications:
    """Tests for RFQ/quote communications endpoints."""

    def test_get_rfqs(self, client):
        """List RFQs returns list of RfqModel objects."""
        rfqs = client.communications.get_rfqs(limit=10)

        assert isinstance(rfqs, list)
        if rfqs:
            rfq = rfqs[0]
            assert isinstance(rfq, RfqModel)
            assert rfq.rfq_id is not None

    def test_get_quotes(self, client):
        """List quotes returns list of QuoteModel objects.

        Scopes results with rfq_user_filter="self" — the documented
        replacement for the API-deprecated creator-ID filters.
        """
        quotes = client.communications.get_quotes(rfq_user_filter="self", limit=10)

        assert isinstance(quotes, list)
        if quotes:
            q = quotes[0]
            assert isinstance(q, QuoteModel)
            assert q.quote_id is not None

    def test_get_rfqs_with_filter(self, client):
        """List RFQs with status filter."""
        rfqs = client.communications.get_rfqs(status="open", limit=10)

        assert isinstance(rfqs, list)

    def test_communications_cached_property(self, client):
        """client.communications returns same instance."""
        comm1 = client.communications
        comm2 = client.communications
        assert comm1 is comm2


class TestMveCreateMarket:
    """Tests for creating combo markets in collections.

    These are more involved - they actually create markets on the exchange.
    Only run if there are open collections with associated events.
    """

    def test_create_and_lookup_combo_market(self, client):
        """Create a combo market and look it up."""
        collections = client.get_mve_collections(status="open", limit=10)
        if not collections:
            pytest.skip("No open MVE collections available on demo")

        # Find a collection with associated events that have markets
        for col in collections:
            if not col.data.associated_events or len(col.data.associated_events) < 2:
                continue

            # Try to get markets for the associated events
            legs = []
            for ae in col.data.associated_events[:int(Decimal(col.data.size_max_fp)) if col.data.size_max_fp else 2]:
                try:
                    event_markets = client.get_markets(
                        event_ticker=ae.ticker, limit=1
                    )
                    if event_markets:
                        legs.append({
                            "market_ticker": event_markets[0].ticker,
                            "event_ticker": ae.ticker,
                            "side": "yes",
                        })
                except Exception:
                    continue

            min_legs = int(Decimal(col.data.size_min_fp)) if col.data.size_min_fp else 2
            if len(legs) < min_legs:
                continue

            legs = legs[:int(Decimal(col.data.size_max_fp)) if col.data.size_max_fp else len(legs)]

            # Try to create the combo market
            try:
                market = col.create_market(legs)

                assert isinstance(market, Market)
                assert market.ticker is not None
                assert market.ticker.startswith("KXMVE")

                # Now look it up
                result = col.lookup_ticker(legs)
                assert "market_ticker" in result or "event_ticker" in result
                return
            except KalshiAPIError:
                # Some combos may be rejected - try next collection
                continue

        pytest.skip("No suitable MVE collections found for combo creation")


class TestMveDataFrameList:
    """Test DataFrameList works with MVE types."""

    def test_collections_to_dataframe(self, client):
        """MveCollection DataFrameList converts to DataFrame."""
        collections = client.get_mve_collections(limit=5)
        if not collections:
            pytest.skip("No MVE collections available")

        df = collections.to_dataframe()

        import pandas as pd
        assert isinstance(df, pd.DataFrame)
        assert len(df) == len(collections)
        assert "collection_ticker" in df.columns

    def test_multivariate_events_to_dataframe(self, client):
        """Multivariate events DataFrameList converts to DataFrame."""
        events = client.get_multivariate_events(limit=5)
        if not events:
            pytest.skip("No multivariate events available")

        df = events.to_dataframe()

        import pandas as pd
        assert isinstance(df, pd.DataFrame)
        assert len(df) == len(events)
