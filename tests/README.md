# Kalshi API Tests

Unit and integration tests for the Kalshi API client library.

## Running Tests

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/test_exchange.py

# Run specific test class
pytest tests/test_exchange.py::TestExchangeStatus

# Run with coverage
pytest tests/ --cov=pykalshi
```

## Test Structure

### `conftest.py` - Shared Fixtures

- **`mock_response`**: Factory for creating mock HTTP responses with JSON data and status codes
- **`client`**: Pre-configured `KalshiClient` with mocked auth and HTTP session (no real API calls)

### Test Files

| File | Description |
|------|-------------|
| `test_client.py` | Core HTTP client: auth headers, error handling, retries |
| `test_models.py` | Pydantic model validation for all data types |
| `test_portfolio.py` | Portfolio operations: positions, fills, orders |
| `test_workflow.py` | End-to-end workflows: balance, order placement, orderbook |
| `test_feed.py` | WebSocket feed: subscriptions, handlers, message dispatch |
| `test_exchange.py` | Exchange status, schedule |
| `test_api_keys.py` | API key management: list, create, generate, delete, rate limits |
| `test_series.py` | Series, public trades, batch candlesticks |
| `test_markets.py` | Markets and events: fetch, list, candlesticks, filters |
| `test_integration.py` | Live API tests (skipped without credentials) |

## Test Coverage by Feature

### Client (`test_client.py`)
- Auth header generation with RSA-PSS signatures
- HTTP response handling (success, errors)
- Custom exceptions: `AuthenticationError`, `ResourceNotFoundError`, `InsufficientFundsError`
- Error message and code extraction

### Models (`test_models.py`)
- All Pydantic models validate correctly
- Enum parsing (Action, Side, OrderStatus, MarketStatus)
- Optional fields handled
- Extra fields ignored (forward compatibility)
- Type coercion and validation errors

### Portfolio (`test_portfolio.py`)
- `get_positions()` with filters (ticker, event_ticker, count_filter)
- `get_fills()` with filters (ticker, order_id, min_ts, max_ts)
- `get_order()` by ID
- 404 handling for missing orders

### Workflows (`test_workflow.py`)
- `portfolio.get_balance()` method
- `portfolio.place_order()` with Market objects
- `market.get_orderbook()` returns typed response

### WebSocket Feed (`test_feed.py`)
- URL selection (demo vs production)
- Handler registration (direct and decorator)
- Subscription management
- Message dispatch and parsing for all channel types:
  - `ticker`, `trade`, `fill`
  - `orderbook_snapshot`, `orderbook_delta`
- Error handling (malformed JSON, handler exceptions)
- Auth header generation

### Exchange (`test_exchange.py`)
- `client.exchange.get_status()` - operational status
- `client.exchange.is_trading()` - quick boolean check
- `client.exchange.get_schedule()` - trading hours
- `client.exchange.get_user_data_timestamp()` - data validation timestamp
- Cached property behavior

### API Keys (`test_api_keys.py`)
- `client.api_keys.list()` - list all keys
- `client.api_keys.create()` - create with public key
- `client.api_keys.generate()` - generate key pair
- `client.api_keys.delete()` - delete key
- `client.api_keys.get_limits()` - rate limit info
- 404 handling for non-existent keys

### Series & Trades (`test_series.py`)
- `client.get_series()` - fetch single series
- `client.get_all_series()` - list with category filter
- `series.get_markets()` - markets in a series
- `client.get_trades()` - public trade history with filters
- `client.get_candlesticks_batch()` - batch candlestick retrieval
- Pagination with `fetch_all=True`

### Markets & Events (`test_markets.py`)
- `client.get_market()` - fetch single market
- `client.get_markets()` - list with filters (series, event, status)
- `market.get_candlesticks()` - historical OHLC data
- Series ticker resolution from event
- `client.get_event()` - fetch single event
- `client.get_events()` - list with filters
- Market equality and hashing
- Attribute delegation to underlying model

## Test Patterns

### Mocking HTTP Responses

```python
def test_example(client, mock_response):
    client._session.request.return_value = mock_response({
        "data": {"key": "value"}
    })

    result = client.get("/endpoint")

    assert result["data"]["key"] == "value"
```

### Testing Error Cases

```python
def test_not_found(client, mock_response):
    client._session.request.return_value = mock_response(
        {"message": "Not found"}, status_code=404
    )

    with pytest.raises(ResourceNotFoundError):
        client.get("/missing")
```

### Testing Pagination

```python
def test_pagination(client, mock_response):
    client._session.request.side_effect = [
        mock_response({"items": [1], "cursor": "page2"}),
        mock_response({"items": [2], "cursor": ""}),
    ]

    result = client.get_items(fetch_all=True)

    assert len(result) == 2
    assert client._session.request.call_count == 2
```

### Verifying Request Parameters

```python
def test_filters(client, mock_response):
    client._session.request.return_value = mock_response({"items": []})

    client.get_items(status="active", limit=50)

    call_url = client._session.request.call_args.args[1]
    assert "status=active" in call_url
    assert "limit=50" in call_url
```

## Integration Tests

`test_integration.py` contains tests that hit the real Kalshi API. These are **skipped by default** unless valid credentials are configured:

```bash
# Set environment variables
export KALSHI_API_KEY_ID="your_key"
export KALSHI_PRIVATE_KEY_PATH="/path/to/key.pem"

# Run integration tests
pytest tests/test_integration.py -v
```

Integration tests verify:
- Balance retrieval
- Market listing and fetching
- Orderbook data
- Position queries
- Fill history
- Order queries
