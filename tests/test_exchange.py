"""Tests for Exchange status and schedule."""

import pytest
from unittest.mock import ANY


class TestExchangeStatus:
    """Tests for exchange status retrieval."""

    def test_get_status(self, client, mock_response):
        """Test fetching exchange status."""
        client._session.request.return_value = mock_response({
            "exchange_active": True,
            "trading_active": True,
        })

        status = client.exchange.get_status()

        assert status.exchange_active is True
        assert status.trading_active is True
        client._session.request.assert_called_with(
            "GET",
            "https://demo-api.kalshi.co/trade-api/v2/exchange/status",
            headers=ANY,
            timeout=ANY,
        )

    def test_get_status_inactive(self, client, mock_response):
        """Test exchange status when trading is closed."""
        client._session.request.return_value = mock_response({
            "exchange_active": True,
            "trading_active": False,
        })

        status = client.exchange.get_status()

        assert status.exchange_active is True
        assert status.trading_active is False

    def test_is_trading_shortcut(self, client, mock_response):
        """Test is_trading property shortcut."""
        client._session.request.return_value = mock_response({
            "exchange_active": True,
            "trading_active": True,
        })

        assert client.exchange.is_trading() is True

    def test_is_trading_when_closed(self, client, mock_response):
        """Test is_trading returns False when trading inactive."""
        client._session.request.return_value = mock_response({
            "exchange_active": True,
            "trading_active": False,
        })

        assert client.exchange.is_trading() is False


class TestExchangeSchedule:
    """Tests for exchange schedule retrieval."""

    def test_get_schedule(self, client, mock_response):
        """Test fetching exchange schedule."""
        client._session.request.return_value = mock_response({
            "schedule": {
                "standard_hours": [
                    {"monday": [{"open_time": "00:00", "close_time": "00:00"}]}
                ],
                "maintenance_windows": [],
            }
        })

        schedule = client.exchange.get_schedule()

        assert "standard_hours" in schedule
        assert len(schedule["standard_hours"]) == 1
        client._session.request.assert_called_with(
            "GET",
            "https://demo-api.kalshi.co/trade-api/v2/exchange/schedule",
            headers=ANY,
            timeout=ANY,
        )

    def test_get_schedule_empty(self, client, mock_response):
        """Test empty schedule response."""
        client._session.request.return_value = mock_response({"schedule": {}})

        schedule = client.exchange.get_schedule()

        assert schedule == {}


class TestUserDataTimestamp:
    """Tests for user data timestamp."""

    def test_get_user_data_timestamp(self, client, mock_response):
        """Test fetching user data timestamp."""
        client._session.request.return_value = mock_response({
            "user_data_timestamp": 1704067200000,
        })

        ts = client.exchange.get_user_data_timestamp()

        assert ts == 1704067200000
        client._session.request.assert_called_with(
            "GET",
            "https://demo-api.kalshi.co/trade-api/v2/exchange/user_data_timestamp",
            headers=ANY,
            timeout=ANY,
        )

    def test_get_user_data_timestamp_missing(self, client, mock_response):
        """Test handling missing timestamp field."""
        client._session.request.return_value = mock_response({})

        ts = client.exchange.get_user_data_timestamp()

        assert ts == 0


class TestExchangeCachedProperty:
    """Tests for Exchange cached property on client."""

    def test_exchange_is_cached(self, client):
        """Test that client.exchange returns same instance."""
        exchange1 = client.exchange
        exchange2 = client.exchange
        assert exchange1 is exchange2

    def test_exchange_has_client_reference(self, client):
        """Test that Exchange has reference to client."""
        assert client.exchange._client is client
