# Java test guide

Primary verification now runs through Maven/JUnit.

## Run tests

```bash
mvn test
```

## Coverage areas

- Auth header generation and error mapping
- Markets and portfolio workflows
- Exchange and API key services
- WebSocket feed parsing
- Orderbook state updates
- Token bucket rate limiting
- Async wrapper behavior

## Legacy Python tests

The original Python test suite is still present as migration reference and can be run with:

```bash
uv sync --all-extras
uv run pytest tests/ --ignore=tests/integration -q
```
