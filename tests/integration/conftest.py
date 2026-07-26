"""Shared fixtures for integration tests.

These tests run against the Kalshi Demo API with real market data
but fake money, making mutations safe to test.

Credentials can be provided in two ways:

1. Demo-specific env vars (recommended):
    KALSHI_DEMO_API_KEY_ID: Demo API key ID
    KALSHI_DEMO_PRIVATE_KEY_PATH: Path to demo private key file

2. Load from .env.demo file:
    Create .env.demo with KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH

Run with: pytest tests/integration/ -v
Skip with: pytest tests/ --ignore=tests/integration/
"""

import os
import pytest
from decimal import Decimal
from pathlib import Path


def _get_demo_credentials():
    """Get demo credentials from environment.

    Checks KALSHI_DEMO_* first, then loads .env.demo if available.
    """
    # First try KALSHI_DEMO_* vars
    key_id = os.getenv("KALSHI_DEMO_API_KEY_ID")
    key_path = os.getenv("KALSHI_DEMO_PRIVATE_KEY_PATH")

    if key_id and key_path:
        return key_id, key_path

    # Try loading .env.demo
    env_demo = Path(__file__).parent.parent.parent / ".env.demo"
    if env_demo.exists():
        with open(env_demo) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    if k == "KALSHI_API_KEY_ID":
                        key_id = v
                    elif k == "KALSHI_PRIVATE_KEY_PATH":
                        # Resolve relative to repo root
                        key_path = str(env_demo.parent / v)

    return key_id, key_path


def _has_demo_credentials():
    """Check if demo credentials are available."""
    key_id, key_path = _get_demo_credentials()
    return key_id and key_path and os.path.exists(key_path)


# Skip all tests in this directory if no demo credentials
pytestmark = pytest.mark.skipif(
    not _has_demo_credentials(),
    reason="Demo credentials not set. Set KALSHI_DEMO_API_KEY_ID/PATH or create .env.demo",
)


@pytest.fixture(scope="session")
def client():
    """Demo client for integration tests.

    Session-scoped to reuse connection across tests.
    Skips entire suite if the Kalshi API is unavailable (503/5xx).
    """
    from pykalshi import KalshiClient

    key_id, key_path = _get_demo_credentials()
    c = KalshiClient(
        api_key_id=key_id,
        private_key_path=key_path,
        demo=True,
    )

    # Health check: skip the whole suite if the API is down
    try:
        c.get_markets(limit=1)
    except Exception as e:
        pytest.skip(f"Kalshi API unavailable, skipping integration tests: {e}")

    yield c
    c.close()


@pytest.fixture
async def async_client():
    """Async demo client for integration tests.

    Function-scoped because httpx.AsyncClient is bound to an event loop.
    """
    from pykalshi import AsyncKalshiClient

    key_id, key_path = _get_demo_credentials()
    async with AsyncKalshiClient(
        api_key_id=key_id,
        private_key_path=key_path,
        demo=True,
    ) as c:
        try:
            await c.get_markets(limit=1)
        except Exception as e:
            pytest.skip(f"Kalshi API unavailable for async client: {e}")
        yield c


@pytest.fixture(scope="session")
def trading_client(client):
    """Client that is only available when the exchange is open for trading.

    Skips tests when the exchange is paused (off-hours, maintenance).
    """
    if not client.exchange.is_trading():
        pytest.skip("Exchange is not trading — skipping order mutation tests")
    return client


@pytest.fixture(scope="session")
def active_market(client):
    """Get an active open market for testing.

    Session-scoped to avoid repeated API calls.
    Prefers markets with higher 24h volume for more reliable tests.
    """
    from pykalshi.enums import MarketStatus

    markets = client.get_markets(limit=50, status=MarketStatus.OPEN)
    if not markets:
        pytest.skip("No open markets available")

    # Prefer markets with volume (more likely to have activity)
    markets_with_volume = [m for m in markets if m.volume_24h_fp]
    if markets_with_volume:
        return max(markets_with_volume, key=lambda m: Decimal(m.volume_24h_fp or "0"))

    # Fall back to any market with bid/ask
    for m in markets:
        if m.yes_bid_dollars or m.yes_ask_dollars:
            return m

    return markets[0]


# --- Demo-exchange flakiness -------------------------------------------------

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Report a 503 from the demo exchange as a skip, not a failure.

    The demo exchange goes unavailable for stretches. When it does, every order
    mutation test fails with `503 service_unavailable`, which buries any real
    regression in noise. The existing `trading_client` fixture only checks
    whether the exchange is trading at setup time; it cannot catch an outage
    that starts mid-run.
    """
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.failed and call.excinfo is not None:
        text = str(call.excinfo.value)
        if "503" in text and "service_unavailable" in text:
            report.outcome = "skipped"
            report.longrepr = f"Demo exchange unavailable (503): {text[:200]}"


# --- Endpoint recording ------------------------------------------------------

@pytest.fixture
def recorded_client(client):
    """A client that records (method, url) for every request it makes.

    Integration tests otherwise assert only on behaviour, so a change to which
    endpoint is called is invisible until the API happens to reject it. That is
    exactly how the v1 order endpoints stayed in place after they were replaced.
    Exposes `client.recorded_calls`.
    """
    calls: list[tuple[str, str]] = []
    original = client._session.request

    def spy(method, url, *args, **kwargs):
        calls.append((method, str(url)))
        return original(method, url, *args, **kwargs)

    client._session.request = spy
    client.recorded_calls = calls
    try:
        yield client
    finally:
        client._session.request = original


def paths_for(client, method: str) -> list[str]:
    """Recorded request paths for a given HTTP method."""
    return [
        url.split("/trade-api/v2", 1)[-1].split("?", 1)[0]
        for m, url in client.recorded_calls
        if m == method
    ]
