"""Tests for API key management and account limits."""

import pytest
import json
from unittest.mock import ANY


class TestAPIKeysList:
    """Tests for listing API keys."""

    def test_list_api_keys(self, client, mock_response):
        """Test listing all API keys."""
        client._session.request.return_value = mock_response({
            "api_keys": [
                {
                    "id": "key-001",
                    "name": "Trading Bot",
                    "created_time": "2024-01-01T00:00:00Z",
                    "last_used": "2024-01-15T12:00:00Z",
                    "scopes": ["read", "trade"],
                },
                {
                    "id": "key-002",
                    "name": "Data Reader",
                    "created_time": "2024-01-10T00:00:00Z",
                    "last_used": None,
                    "scopes": ["read"],
                },
            ]
        })

        keys = client.api_keys.list()

        assert len(keys) == 2
        assert keys[0].id == "key-001"
        assert keys[0].name == "Trading Bot"
        assert keys[0].scopes == ["read", "trade"]
        assert keys[1].id == "key-002"
        client._session.request.assert_called_with(
            "GET",
            "https://external-api.demo.kalshi.co/trade-api/v2/api_keys",
            headers=ANY,
            timeout=ANY,
        )

    def test_list_api_keys_empty(self, client, mock_response):
        """Test empty API keys list."""
        client._session.request.return_value = mock_response({"api_keys": []})

        keys = client.api_keys.list()

        assert keys == []


class TestAPIKeyCreate:
    """Tests for creating API keys."""

    def test_create_api_key(self, client, mock_response):
        """Test creating API key with public key."""
        client._session.request.return_value = mock_response({
            "api_key_id": "new-key-001",
        })

        key_id = client.api_keys.create(
            public_key="-----BEGIN PUBLIC KEY-----\nMIIB...\n-----END PUBLIC KEY-----",
            name="My New Key",
        )

        assert key_id == "new-key-001"

        # Verify POST body
        call_args = client._session.request.call_args
        assert call_args.args[0] == "POST"
        body = json.loads(call_args.kwargs["content"])
        assert "public_key" in body
        assert body["name"] == "My New Key"

    def test_create_api_key_no_name(self, client, mock_response):
        """Test creating API key without name."""
        client._session.request.return_value = mock_response({
            "api_key_id": "new-key-002"
        })

        key_id = client.api_keys.create(public_key="-----BEGIN PUBLIC KEY-----\n...")

        assert key_id == "new-key-002"
        call_args = client._session.request.call_args
        body = json.loads(call_args.kwargs["content"])
        assert "name" not in body


class TestAPIKeyGenerate:
    """Tests for generating API key pairs."""

    def test_generate_api_key(self, client, mock_response):
        """Test generating a new API key pair."""
        client._session.request.return_value = mock_response({
            "id": "gen-key-001",
            "private_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----",
            "name": "Generated Key",
        })

        key = client.api_keys.generate(name="Generated Key")

        assert key.id == "gen-key-001"
        assert "PRIVATE KEY" in key.private_key
        assert key.name == "Generated Key"

        call_args = client._session.request.call_args
        assert call_args.args[0] == "POST"
        assert "/api_keys/generate" in call_args.args[1]

    def test_generate_api_key_no_name(self, client, mock_response):
        """Test generating API key without name."""
        client._session.request.return_value = mock_response({
            "id": "gen-key-002",
            "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...",
        })

        key = client.api_keys.generate()

        assert key.id == "gen-key-002"
        call_args = client._session.request.call_args
        body = json.loads(call_args.kwargs["content"])
        assert body == {}


class TestAPIKeyDelete:
    """Tests for deleting API keys."""

    def test_delete_api_key(self, client, mock_response):
        """Test deleting an API key."""
        client._session.request.return_value = mock_response({}, status_code=204)

        client.api_keys.delete("key-to-delete")

        client._session.request.assert_called_with(
            "DELETE",
            "https://external-api.demo.kalshi.co/trade-api/v2/api_keys/key-to-delete",
            headers=ANY,
            timeout=ANY,
        )

    def test_delete_nonexistent_key(self, client, mock_response):
        """Test deleting a non-existent key raises error."""
        from pykalshi.exceptions import ResourceNotFoundError

        client._session.request.return_value = mock_response(
            {"message": "Key not found"}, status_code=404
        )

        with pytest.raises(ResourceNotFoundError):
            client.api_keys.delete("nonexistent-key")


class TestAPILimits:
    """Tests for API rate limits."""

    def test_get_limits(self, client, mock_response):
        """Test fetching API rate limits."""
        client._session.request.return_value = mock_response({
            "usage_tier": "standard",
            "read_limit": 20,
            "write_limit": 10,
        })

        limits = client.api_keys.get_limits()

        assert limits.usage_tier == "standard"
        assert limits.read_limit == 20
        assert limits.write_limit == 10
        client._session.request.assert_called_with(
            "GET",
            "https://external-api.demo.kalshi.co/trade-api/v2/account/limits",
            headers=ANY,
            timeout=ANY,
        )

    def test_get_limits_minimal(self, client, mock_response):
        """Test limits with minimal response."""
        client._session.request.return_value = mock_response({
            "usage_tier": "basic",
        })

        limits = client.api_keys.get_limits()

        assert limits.usage_tier == "basic"
        assert limits.read_limit is None
        assert limits.write_limit is None


class TestAPIKeysCachedProperty:
    """Tests for APIKeys cached property on client."""

    def test_api_keys_is_cached(self, client):
        """Test that client.api_keys returns same instance."""
        api_keys1 = client.api_keys
        api_keys2 = client.api_keys
        assert api_keys1 is api_keys2

    def test_api_keys_has_client_reference(self, client):
        """Test that APIKeys has reference to client."""
        assert client.api_keys._client is client
