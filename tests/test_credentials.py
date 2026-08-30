import os
import pytest
from unittest import mock
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from pykalshi._base import _BaseKalshiClient


@pytest.fixture
def mock_load_private_key():
    with mock.patch("pykalshi._base._BaseKalshiClient._load_private_key") as m:
        yield m


@pytest.fixture
def mock_load_private_key_string():
    with mock.patch("pykalshi._base._BaseKalshiClient._load_private_key_string") as m:
        yield m


@mock.patch.dict(os.environ, {"KALSHI_API_KEY_ID": "env_api_key"})
def test_credential_precedence_private_key(mock_load_private_key, mock_load_private_key_string):
    """Test that private_key arg takes precedence over env vars and private_key_path."""
    mock_load_private_key_string.return_value = mock.Mock(spec=RSAPrivateKey)
    
    with mock.patch.dict(os.environ, {"KALSHI_PRIVATE_KEY": "env_private_key_str", "KALSHI_PRIVATE_KEY_PATH": "env_path"}):
        client = _BaseKalshiClient(
            private_key="arg_private_key_str",
            private_key_path="arg_path"
        )
        
        # Should use the argument string, not the env var or path
        mock_load_private_key_string.assert_called_once_with("arg_private_key_str")
        mock_load_private_key.assert_not_called()
        assert isinstance(client.private_key, RSAPrivateKey)


@mock.patch.dict(os.environ, {"KALSHI_API_KEY_ID": "env_api_key"})
def test_credential_precedence_private_key_path(mock_load_private_key, mock_load_private_key_string):
    """Test that private_key_path arg takes precedence over env vars if private_key is omitted."""
    mock_load_private_key.return_value = mock.Mock(spec=RSAPrivateKey)
    
    with mock.patch.dict(os.environ, {"KALSHI_PRIVATE_KEY": "env_private_key_str", "KALSHI_PRIVATE_KEY_PATH": "env_path"}):
        client = _BaseKalshiClient(
            private_key_path="arg_path"
        )
        
        # Should use the argument path, not the env var
        mock_load_private_key.assert_called_once_with("arg_path")
        mock_load_private_key_string.assert_not_called()


@mock.patch.dict(os.environ, {"KALSHI_API_KEY_ID": "env_api_key"})
def test_credential_precedence_env_vars(mock_load_private_key, mock_load_private_key_string):
    """Test that KALSHI_PRIVATE_KEY takes precedence over KALSHI_PRIVATE_KEY_PATH when both are set."""
    mock_load_private_key_string.return_value = mock.Mock(spec=RSAPrivateKey)
    
    with mock.patch.dict(os.environ, {"KALSHI_PRIVATE_KEY": "env_private_key_str", "KALSHI_PRIVATE_KEY_PATH": "env_path"}):
        client = _BaseKalshiClient()
        
        # Should use the env var string
        mock_load_private_key_string.assert_called_once_with("env_private_key_str")
        mock_load_private_key.assert_not_called()


@mock.patch.dict(os.environ, {"KALSHI_API_KEY_ID": "env_api_key"})
def test_invalid_private_key_type():
    """Test that passing an invalid type to private_key raises TypeError."""
    with pytest.raises(TypeError, match="Expected private_key to be str or RSAPrivateKey, got int"):
        _BaseKalshiClient(private_key=12345)
