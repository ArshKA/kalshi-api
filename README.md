<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/pykalshi_logo_dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="assets/pykalshi_logo_light.svg">
    <img alt="pykalshi logo" src="assets/pykalshi_logo_light.svg" width="70%">
  </picture>
</p>

# PyKalshi

[![PyPI version](https://img.shields.io/pypi/v/pykalshi.svg)](https://pypi.org/project/pykalshi/)
[![Python versions](https://img.shields.io/pypi/pyversions/pykalshi.svg)](https://pypi.org/project/pykalshi/)
[![Tests](https://github.com/ArshKA/pykalshi/actions/workflows/test.yml/badge.svg)](https://github.com/ArshKA/pykalshi/actions/workflows/test.yml)
[![License](https://img.shields.io/pypi/l/pykalshi.svg)](https://github.com/ArshKA/pykalshi/blob/main/LICENSE)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1cD1FJZSeEW2qThzi7IZQKtHxu3z3eWAO)

The Python client for [Kalshi](https://kalshi.com) prediction markets. WebSocket streaming, automatic retries, pandas integration, and clean interfaces for building trading systems.

<p align="center">
  <img src="assets/jupyter_preview.png" alt="Jupyter notebook rich display" width="90%">
</p>

```python
from pykalshi import KalshiClient, Action, Side

client = KalshiClient()

# Place a trade
order = client.portfolio.place_order("KXBTC-25MAR15-B100000", Action.BUY, Side.YES, count_fp="10", yes_price_dollars="0.45")
order.wait_until_terminal()  # Block until filled/canceled
```

## Features

- **WebSocket streaming** - Real-time orderbook, ticker, and trade data with typed messages
- **Automatic retries** - Exponential backoff on rate limits and transient errors
- **Domain objects** - `Market`, `Order`, `Event` with methods like `order.cancel()`, `market.get_orderbook()`
- **pandas integration** - `.to_dataframe()` on any list of results
- **Jupyter support** - Rich HTML display for markets, orders, and positions
- **Local orderbook** - `OrderbookManager` maintains state from WebSocket deltas
- **Type safety** - Pydantic models and typed exceptions throughout

## Installation

```bash
pip install pykalshi

# With pandas support
pip install pykalshi[dataframe]
```

Get your API credentials from [kalshi.com](https://kalshi.com/account/api) and create a `.env` file:

```
KALSHI_API_KEY_ID=your-key-id
KALSHI_PRIVATE_KEY_PATH=/path/to/private-key.key
```

## Quick Start

> **Interactive demo:** [`examples/demo.ipynb`](examples/demo.ipynb) or [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1cD1FJZSeEW2qThzi7IZQKtHxu3z3eWAO)

### Browse Markets

```python
from pykalshi import MarketStatus, CandlestickPeriod

client = KalshiClient()

# Search markets
markets = client.get_markets(status=MarketStatus.OPEN, limit=100)
btc_markets = client.get_markets(series_ticker="KXBTC")

# Get a specific market
market = client.get_market("KXBTC-25MAR15-B100000")
print(f"{market.title}: ${market.yes_bid_dollars} / ${market.yes_ask_dollars}")

# Market data
orderbook = market.get_orderbook()
trades = market.get_trades(limit=50)
candles = market.get_candlesticks(start_ts, end_ts, period=CandlestickPeriod.ONE_HOUR)
```

### Trading

```python
from pykalshi import Action, Side, OrderStatus

# Check balance
balance = client.portfolio.get_balance()
print(f"${balance.balance / 100:.2f} available")

# Place an order
order = client.portfolio.place_order(market, Action.BUY, Side.YES, count_fp="10", yes_price_dollars="0.50")

# Manage orders
order.wait_until_terminal()                    # Block until filled/canceled
order.amend(yes_price_dollars="0.45")          # Amend price
order.decrease(reduce_by_fp="5")               # Shrink the resting size
order.cancel()                                 # Cancel

# Buying NO is the same as selling YES. Orders rest on a single
# YES-denominated book, so a buy of NO at 0.01 reads back as a sell
# of YES at 0.99 -- the same resting order, quoted from the YES side.
order = client.portfolio.place_order(market, Action.BUY, Side.NO, count_fp="10", no_price_dollars="0.01")

# View portfolio
positions = client.portfolio.get_positions()
fills = client.portfolio.get_fills(limit=100)
orders = client.portfolio.get_orders(status=OrderStatus.RESTING)
```

### Real-time Streaming

```python
from pykalshi import Feed, TickerMessage, OrderbookSnapshotMessage

async with Feed(client) as feed:
    await feed.subscribe_ticker("KXBTC-25MAR15-B100000")
    await feed.subscribe_orderbook("KXBTC-25MAR15-B100000")
    await feed.subscribe_trades("KXBTC-25MAR15-B100000")

    async for msg in feed:
        match msg:
            case TickerMessage():
                print(f"Price: ${msg.price_dollars}")
            case OrderbookSnapshotMessage():
                print(f"Book: {len(msg.yes)} yes levels, {len(msg.no)} no levels")
```

### Local Orderbook

```python
from pykalshi import Feed, OrderbookManager

manager = OrderbookManager()

async with Feed(client) as feed:
    await feed.subscribe_orderbook(ticker)

    async for msg in feed:
        manager.apply(msg)
        book = manager.get(ticker)
        best_bid = book["yes_dollars"][0] if book["yes_dollars"] else None
```

### pandas Integration

```python
# Any list result has .to_dataframe()
positions_df = client.portfolio.get_positions().to_dataframe()
markets_df = client.get_markets(limit=500).to_dataframe()
fills_df = client.portfolio.get_fills().to_dataframe()

# Candlesticks and orderbooks too
candles_df = market.get_candlesticks(start, end).to_dataframe()
orderbook_df = market.get_orderbook().to_dataframe()
```

### Error Handling

```python
from pykalshi import InsufficientFundsError, RateLimitError, KalshiAPIError

try:
    order = client.portfolio.place_order(...)
except InsufficientFundsError:
    print("Not enough balance")
except RateLimitError:
    pass  # Client auto-retries with backoff
except KalshiAPIError as e:
    print(f"{e.status_code}: {e.error_code}")
```

## Examples

See the [`examples/`](examples/) directory:

- **[demo.ipynb](examples/demo.ipynb)** - Interactive notebook with rich display examples
- **[basic_usage.py](examples/basic_usage.py)** - Browse markets and check portfolio
- **[place_order.py](examples/place_order.py)** - Place and manage orders
- **[stream_orderbook.py](examples/stream_orderbook.py)** - WebSocket streaming patterns
- **[momentum_bot.py](examples/momentum_bot.py)** - Simple trading bot example

## Web Dashboard

A real-time web dashboard is included for browsing markets, viewing orderbooks, and monitoring your portfolio. It serves as both a development tool and a reference implementation.

```bash
pip install pykalshi[web]
uvicorn web.backend.main:app --reload
```

See [`web/`](web/) for details.

## Why pykalshi?

| | pykalshi | kalshi-python (official) |
|---|:---:|:---:|
| WebSocket streaming | ✓ | — |
| Automatic retry/backoff | ✓ | — |
| Rate limit handling | ✓ | — |
| Domain objects | ✓ | — |
| pandas integration | ✓ | — |
| Jupyter display | ✓ | — |
| Local orderbook | ✓ | — |
| Typed exceptions | ✓ | — |
| Pydantic models | ✓ | — |
| Full API coverage | — | ✓ |

The official SDK is auto-generated from the OpenAPI spec. pykalshi adds the infrastructure needed for production trading: real-time data, error recovery, and ergonomic interfaces.

## Links

- [Kalshi API Reference](https://docs.kalshi.com/api-reference)
- [kalshi-starter-code-python (official examples)](https://github.com/Kalshi/kalshi-starter-code-python)

---

*This is an unofficial library and is not affiliated with Kalshi.*
