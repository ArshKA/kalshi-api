"""Integration tests for API Keys endpoints.

These tests create and delete API keys. They clean up after themselves
but should only be run against the demo environment.
"""

import pytest


class TestAPIKeysReadOnly:
    """Read-only API key tests."""

    def test_list_api_keys(self, client):
        """List API keys returns list."""
        keys = client.api_keys.list()

        assert isinstance(keys, list)
        # Should have at least the key we're using
        assert len(keys) >= 1

        # Verify structure
        key = keys[0]
        assert hasattr(key, "id")
        assert hasattr(key, "name")

    def test_get_limits(self, client):
        """Get API limits (nested token-bucket shape)."""
        limits = client.api_keys.get_limits()

        assert isinstance(limits.usage_tier, str) and limits.usage_tier
        assert limits.read.refill_rate > 0
        assert limits.read.bucket_capacity > 0
        assert limits.write.refill_rate > 0
        assert limits.write.bucket_capacity > 0
        assert isinstance(limits.grants, list)

        # Deprecated flat aliases still resolve (with a warning).
        with pytest.warns(DeprecationWarning):
            assert limits.read_limit == limits.read.refill_rate
        with pytest.warns(DeprecationWarning):
            assert limits.write_limit == limits.write.refill_rate


class TestAPIKeysMutation:
    """Mutation tests for API keys.

    These tests create and delete keys. They include cleanup
    to avoid leaving orphaned keys.
    """

    def test_generate_and_delete_api_key(self, client):
        """Generate an API key and then delete it."""
        # Generate (creates both public/private key pair)
        generated = client.api_keys.generate(name="integration-test-key")

        assert generated.id is not None
        assert isinstance(generated.id, str)
        assert hasattr(generated, "private_key")

        key_id = generated.id

        # Verify it appears in list
        keys = client.api_keys.list()
        key_ids = [k.id for k in keys]
        assert key_id in key_ids

        # Delete (cleanup)
        client.api_keys.delete(key_id)

        # Verify it's gone
        keys = client.api_keys.list()
        key_ids = [k.id for k in keys]
        assert key_id not in key_ids

    def test_generate_api_key_has_private_key(self, client):
        """Generate API key returns private key (only shown once)."""
        generated = client.api_keys.generate(name="integration-test-generated")

        assert hasattr(generated, "id")
        assert hasattr(generated, "private_key")
        assert "PRIVATE KEY" in generated.private_key

        # Cleanup
        client.api_keys.delete(generated.id)

    def test_generate_requires_name(self, client):
        """Generate API key requires a name (API constraint)."""
        import pytest
        from pykalshi.exceptions import KalshiAPIError

        # API requires name parameter - returns 400
        with pytest.raises(KalshiAPIError) as exc_info:
            client.api_keys.generate()

        assert exc_info.value.status_code == 400

    def test_create_with_public_key(self, client):
        """Create API key with user-provided RSA public key."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        # Generate a new RSA keypair
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
        )
        public_key = private_key.public_key()

        # Export public key in PEM format
        public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        # Create API key with our public key (returns just the key ID string)
        key_id = client.api_keys.create(
            public_key=public_key_pem,
            name="integration-test-create-key",
        )

        assert key_id is not None
        assert isinstance(key_id, str)

        # Verify it appears in list
        keys = client.api_keys.list()
        key_ids = [k.id for k in keys]
        assert key_id in key_ids

        # Cleanup
        client.api_keys.delete(key_id)

        # Verify it's gone
        keys = client.api_keys.list()
        key_ids = [k.id for k in keys]
        assert key_id not in key_ids
