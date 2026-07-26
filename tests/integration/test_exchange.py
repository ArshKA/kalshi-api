"""Integration tests for Exchange endpoints."""

import pytest


class TestExchangeStatus:
    """Tests for exchange status and schedule."""

    def test_get_status(self, client):
        """Exchange status returns valid response."""
        status = client.exchange.get_status()

        assert hasattr(status, "trading_active")
        assert isinstance(status.trading_active, bool)

    def test_is_trading(self, client):
        """is_trading shortcut works."""
        result = client.exchange.is_trading()
        assert isinstance(result, bool)

    def test_get_schedule(self, client):
        """Exchange schedule returns dict with schedule info."""
        schedule = client.exchange.get_schedule()

        # Schedule is a dict with maintenance_windows and standard_hours
        assert isinstance(schedule, dict)
        assert "maintenance_windows" in schedule or "standard_hours" in schedule

    @pytest.mark.xfail(
        reason="Kalshi removed GET /exchange/announcements; it 404s and is no "
               "longer in the API reference. Whether to drop the method is a "
               "breaking-change decision for the maintainer.",
        strict=False,
    )
    def test_get_announcements(self, client):
        """Exchange announcements returns list."""
        announcements = client.exchange.get_announcements()

        assert isinstance(announcements, list)

    def test_get_user_data_timestamp(self, client):
        """User data timestamp returns integer or None."""
        ts = client.exchange.get_user_data_timestamp()

        # May be None if no data changes, or int timestamp
        assert ts is None or isinstance(ts, int)
