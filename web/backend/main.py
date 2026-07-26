import sys
import time
import json
import asyncio
import logging
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Resolve paths relative to this file so the server works from any CWD
_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent.parent
_FRONTEND_DIR = _THIS_DIR.parent / "frontend"

sys.path.insert(0, str(_PROJECT_ROOT))

from pykalshi.client import KalshiClient
from pykalshi.models import (
    MarketModel, OrderbookResponse, BalanceModel, EventModel, PositionModel, SettlementModel,
    SubaccountBalanceModel, SubaccountTransferModel, TradeModel,
)
from pykalshi.enums import MarketStatus, CandlestickPeriod, PositionCountFilter
from pykalshi.exceptions import (
    KalshiAPIError,
    AuthenticationError,
    ResourceNotFoundError,
    RateLimitError,
)
from decimal import Decimal

load_dotenv()

app = FastAPI(title="Kalshi UI Backend")

# Serve React App - static files
app.mount("/components", StaticFiles(directory=str(_FRONTEND_DIR / "components")), name="components")

@app.get("/")
async def read_index():
    return FileResponse(_FRONTEND_DIR / "index.html")

@app.get("/app.jsx")
async def read_app_jsx():
    return FileResponse(_FRONTEND_DIR / "app.jsx")

@app.get("/utils.js")
async def read_utils_js():
    return FileResponse(_FRONTEND_DIR / "utils.js")

# Configure CORS for local React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Exception Handlers ---
# Convert Kalshi API errors to proper HTTP responses with rich context

from fastapi import Request
from fastapi.responses import JSONResponse


@app.exception_handler(KalshiAPIError)
async def pykalshi_error_handler(request: Request, exc: KalshiAPIError):
    """Convert KalshiAPIError to a JSON response with full context."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.message,
            "error_code": exc.error_code,
            "endpoint": exc.endpoint,
            "method": exc.method,
            # Don't expose request_body in production - may contain sensitive data
        },
    )


@app.exception_handler(AuthenticationError)
async def auth_error_handler(request: Request, exc: AuthenticationError):
    """Handle authentication errors."""
    return JSONResponse(
        status_code=401,
        content={
            "error": "Authentication failed. Check your API credentials.",
            "error_code": exc.error_code,
        },
    )


@app.exception_handler(RateLimitError)
async def rate_limit_error_handler(request: Request, exc: RateLimitError):
    """Handle rate limit errors."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded. Please slow down requests.",
            "error_code": "rate_limited",
        },
    )


client: Optional[KalshiClient] = None

@app.on_event("startup")
async def startup_event():
    global client
    try:
        # Initialize client with env vars
        client = KalshiClient()
        print("Successfully authenticated with Kalshi API")
    except Exception as e:
        print(f"Failed to initialize KalshiClient: {e}")
        # Doing this so we can at least return a 500 with a message

def get_client() -> KalshiClient:
    if not client:
        raise HTTPException(status_code=503, detail="Kalshi Client not initialized. Check server logs/credentials.")
    return client

@app.get("/api/balance", response_model=BalanceModel)
def get_balance_short():
    """Get portfolio balance (short URL alias)."""
    return get_client().portfolio.get_balance()


@app.get("/api/exchange/status")
def get_exchange_status():
    """Get exchange operational status and schedule."""
    c = get_client()
    status = c.exchange.get_status()
    schedule = c.exchange.get_schedule()
    return {
        "status": status.model_dump(),
        "schedule": schedule,
    }

@app.get("/api/markets", response_model=List[MarketModel])
def list_markets(limit: int = 100, status: str = "open", ticker: Optional[str] = None):
    c = get_client()

    # Convert string status to Enum
    market_status = None
    if status.lower() != "all":
        try:
            market_status = MarketStatus(status)
        except ValueError:
            valid_statuses = ["all"] + [s.value for s in MarketStatus]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Valid options: {', '.join(valid_statuses)}"
            )

    # 1. Fetch a larger pool to find active markets
    # Many markets have 0 volume, so we need to fetch enough to find the "alive" ones.
    raw_limit = 1000
    markets = c.get_markets(limit=raw_limit, status=market_status)

    market_data = [m.data for m in markets]

    # 2. Filter for Active Markets
    # We only keep volume/OI check to avoid truly dead/empty slots
    from decimal import Decimal
    filtered_markets = []
    for m in market_data:
        # Skip if Volume and OI are both 0/None
        vol = Decimal(m.volume_fp or "0")
        vol24 = Decimal(m.volume_24h_fp or "0")
        oi = Decimal(m.open_interest_fp or "0")
        if not (vol > 0 or vol24 > 0 or oi > 0):
           continue

        filtered_markets.append(m)

    market_data = filtered_markets

    # 3. Sort by Volume (Descending)
    # Prioritize 24h volume for "Hot" markets, then total volume
    market_data.sort(key=lambda m: (Decimal(m.volume_24h_fp or "0"), Decimal(m.volume_fp or "0")), reverse=True)

    # 4. Filter by Ticker if requested
    if ticker:
        ticker_lower = ticker.lower()
        market_data = [m for m in market_data if ticker_lower in m.ticker.lower()]

    return market_data[:limit]

@app.get("/api/markets/{ticker}", response_model=MarketModel)
def get_market_detail(ticker: str):
    c = get_client()
    try:
        market = c.get_market(ticker)
        return market.data
    except ResourceNotFoundError:
        # If market not found, try looking up as Series or Event ticker
        # This handles cases like ?ticker=KXSB (Series) or ?ticker=KXSB-26 (Event)
        # We "redirect" effectively by returning the first market.
        markets = c.get_markets(series_ticker=ticker)
        if markets:
            return markets[0].data

        markets = c.get_markets(event_ticker=ticker)
        if markets:
            return markets[0].data

        raise  # Re-raise original 404 if no fallback found

@app.get("/api/portfolio/balance")
def get_portfolio_balance():
    """Get portfolio balance (full URL path)."""
    return get_client().portfolio.get_balance().model_dump()


@app.get("/api/portfolio/positions", response_model=List[PositionModel])
def get_portfolio_positions():
    """Get all portfolio positions with non-zero balances."""
    positions = get_client().portfolio.get_positions(count_filter=PositionCountFilter.POSITION, fetch_all=True)
    return [p.model_dump() for p in positions]


@app.get("/api/portfolio/settlements", response_model=List[SettlementModel])
def get_portfolio_settlements(limit: int = 50):
    """Get settlement history for resolved positions."""
    settlements = get_client().portfolio.get_settlements(limit=limit)
    return [s.model_dump() for s in settlements]


@app.get("/api/portfolio/summary")
def get_portfolio_summary():
    """Get portfolio summary: balance and position stats."""
    c = get_client()
    balance = c.portfolio.get_balance()
    positions = c.portfolio.get_positions(count_filter=PositionCountFilter.POSITION, fetch_all=True)

    from decimal import Decimal

    # Calculate total position exposure
    total_exposure = sum(abs(Decimal(p.market_exposure_dollars or "0")) for p in positions)

    # Calculate unrealized P&L by fetching current market prices
    unrealized_pnl = Decimal("0")
    position_market_value = Decimal("0")
    for pos in positions:
        pos_qty = Decimal(pos.position_fp)
        if pos_qty == 0:
            continue
        try:
            market = c.get_market(pos.ticker)
            market_data = market.data

            # Get mid price (or last price as fallback)
            yes_bid = Decimal(market_data.yes_bid_dollars or "0")
            yes_ask = Decimal(market_data.yes_ask_dollars or "0")
            if yes_bid and yes_ask:
                mid_price = (yes_bid + yes_ask) / 2
            else:
                mid_price = Decimal(market_data.last_price_dollars or "0.50")

            # Calculate position value at current price
            if pos_qty > 0:
                # Long YES: value = contracts * yes_price
                current_value = pos_qty * mid_price
            else:
                # Long NO (negative position): value = contracts * (1.00 - yes_price)
                current_value = abs(pos_qty) * (Decimal("1") - mid_price)

            position_market_value += current_value

            # Unrealized = current_value - cost_basis
            # market_exposure_dollars is typically what you paid (cost basis)
            cost_basis = abs(Decimal(pos.market_exposure_dollars or "0"))
            unrealized_pnl += current_value - cost_basis
        except Exception:
            # If we can't fetch market data, skip this position
            pass

    return {
        "balance_dollars": str((Decimal(balance.balance) / 100).quantize(Decimal("0.01"))),
        "portfolio_value_dollars": str((Decimal(balance.portfolio_value) / 100).quantize(Decimal("0.01"))),
        "position_count": len(positions),
        "total_exposure_dollars": str(total_exposure),
        "position_market_value_dollars": str(position_market_value),
        "unrealized_pnl_dollars": str(unrealized_pnl),
    }


@app.get("/api/portfolio/history")
def get_portfolio_history(days: int = 30, resolution: Optional[str] = None):
    """Get portfolio realized P&L history for charting.

    Calculates P&L timeline from settlements only (realized P&L).
    Fills don't represent P&L - they're cash exchanges for positions.

    Args:
        days: Number of days of history (default 30).
        resolution: Optional resampling - 'minute', 'hour', or 'day'.
    """
    from datetime import datetime

    c = get_client()
    now = int(time.time())
    min_ts = now - (days * 86400)

    events = []

    # Get settlements - these are the only true realized P&L events
    settlements = c.portfolio.get_settlements(fetch_all=True)
    for settlement in settlements:
        ts = None
        if settlement.settled_time:
            try:
                dt = datetime.fromisoformat(settlement.settled_time.replace('Z', '+00:00'))
                ts = int(dt.timestamp())
            except Exception:
                pass
        if not ts or ts < min_ts:
            continue

        # Settlement P&L = revenue - costs - fees (costs/revenue in cents, fee in dollar string)
        fee_cents = round(float(settlement.fee_cost or 0) * 100)
        delta_cents = settlement.revenue - settlement.yes_total_cost - settlement.no_total_cost - fee_cents
        events.append({'ts': ts, 'delta': str((Decimal(delta_cents) / 100).quantize(Decimal("0.01"))), 'type': 'settlement'})

    if not events:
        return []

    # Sort by timestamp
    events.sort(key=lambda e: e['ts'])

    # Calculate cumulative P&L
    from decimal import Decimal as D
    cumulative = D("0")
    for e in events:
        cumulative += D(e['delta'])
        e['pnl'] = str(cumulative)

    # Resample if requested
    if resolution and len(events) > 1:
        period_seconds = {
            'minute': 60,
            'hour': 3600,
            'day': 86400,
        }.get(resolution, 3600)

        # Create time buckets
        start_ts = (events[0]['ts'] // period_seconds) * period_seconds
        end_ts = now
        resampled = []

        event_idx = 0
        current_pnl = 0

        for bucket_ts in range(start_ts, end_ts + period_seconds, period_seconds):
            # Advance through events up to this bucket
            while event_idx < len(events) and events[event_idx]['ts'] <= bucket_ts:
                current_pnl = events[event_idx]['pnl']
                event_idx += 1
            resampled.append({'ts': bucket_ts, 'pnl': current_pnl, 'type': 'resampled'})

        return resampled

    return [{'ts': e['ts'], 'pnl': e['pnl'], 'type': e['type']} for e in events]


# --- Subaccounts ---

@app.get("/api/portfolio/subaccounts/balances")
def get_subaccount_balances():
    """Get balances for all subaccounts."""
    try:
        balances = get_client().portfolio.get_subaccount_balances()
        return [b.model_dump() for b in balances]
    except ResourceNotFoundError:
        # 404 means subaccounts not enabled or none exist
        return []


@app.get("/api/portfolio/subaccounts/transfers")
def get_subaccount_transfers(limit: int = 50):
    """Get transfer history between subaccounts."""
    try:
        transfers = get_client().portfolio.get_subaccount_transfers(limit=limit)
        return [t.model_dump() for t in transfers]
    except ResourceNotFoundError:
        # 404 means subaccounts not enabled or none exist
        return []


@app.post("/api/portfolio/subaccounts")
def create_subaccount():
    """Create a new subaccount."""
    return get_client().portfolio.create_subaccount().model_dump()


@app.post("/api/portfolio/subaccounts/transfer")
def transfer_between_subaccounts(from_subaccount: int, to_subaccount: int, amount_cents: int):
    """Transfer funds between subaccounts (amounts in cents)."""
    transfer_id = get_client().portfolio.transfer_between_subaccounts(
        from_subaccount, to_subaccount, amount_cents
    )
    return {"client_transfer_id": transfer_id}

@app.get("/api/markets/{ticker}/orderbook", response_model=OrderbookResponse)
def get_market_orderbook(ticker: str):
    c = get_client()
    # Try to resolve the ticker in case it's a series/event ticker
    real_ticker = ticker
    try:
        c.get_market(ticker)
    except ResourceNotFoundError:
        # Try to resolve to a real market ticker
        markets = c.get_markets(series_ticker=ticker)
        if not markets:
            markets = c.get_markets(event_ticker=ticker)
        if markets:
            real_ticker = markets[0].ticker

    market = c.get_market(real_ticker)
    return market.get_orderbook()

@app.get("/api/series", response_model=List[str])
def list_series():
    """Returns a list of unique series tickers found from active/recent events."""
    c = get_client()
    events = c.get_events(limit=100, status=MarketStatus.OPEN)
    return sorted(list(set(e.series_ticker for e in events if e.series_ticker)))

@app.get("/api/series/{series_ticker}/events", response_model=List[EventModel])
def list_series_events(series_ticker: str):
    events = get_client().get_events(series_ticker=series_ticker, limit=100)
    return [e.data for e in events]

@app.get("/api/events/{event_ticker}/markets", response_model=List[MarketModel])
def list_event_markets(event_ticker: str):
    markets = get_client().get_markets(event_ticker=event_ticker)
    return [m.data for m in markets]

@app.get("/api/markets/{ticker}/candlesticks")
def get_market_history(ticker: str, period: str = "hour", limit: int = 168):
    c = get_client()
    market = c.get_market(ticker)

    # Determine time range (default to 1 week for hourly)
    end_ts = int(time.time())
    start_ts = end_ts - (limit * 3600)

    # Map string period to Enum
    period_enum = CandlestickPeriod.ONE_HOUR
    if period == "day":
        period_enum = CandlestickPeriod.ONE_DAY
        start_ts = end_ts - (limit * 86400)
    elif period == "minute":
        period_enum = CandlestickPeriod.ONE_MINUTE
        start_ts = end_ts - (limit * 60)

    history = market.get_candlesticks(start_ts, end_ts, period_enum)

    # Flatten for frontend: [{ts, price}, ...]
    data = []
    for candle in history.candlesticks:
        price = None
        if candle.price:
            price = candle.price.mean_dollars if candle.price.mean_dollars is not None else candle.price.close_dollars
        if price is not None:
            data.append({
                "ts": candle.end_period_ts,
                "price": price,
                "yes_ask_dollars": candle.yes_ask.close_dollars if candle.yes_ask else None,
                "yes_bid_dollars": candle.yes_bid.close_dollars if candle.yes_bid else None,
                "volume_fp": candle.volume_fp,
            })

    return data


@app.get("/api/markets/{ticker}/trades", response_model=List[TradeModel])
def get_market_trades(ticker: str, limit: int = 20):
    """Get recent public trades for a market."""
    trades = get_client().get_trades(ticker=ticker, limit=limit)
    return [t.model_dump() for t in trades]


# --- WebSocket Streaming Endpoint ---

# WebSocket URLs (must match feed.py)
WS_PROD_URL = "wss://external-api-ws.kalshi.com/trade-api/ws/v2"
WS_DEMO_URL = "wss://external-api-ws.demo.kalshi.co/trade-api/ws/v2"
WS_SIGN_PATH = "/trade-api/ws/v2"


def get_ws_auth_headers() -> dict:
    """Generate auth headers for Kalshi WebSocket connection."""
    c = get_client()
    timestamp, signature = c._sign_request("GET", WS_SIGN_PATH)
    return {
        "KALSHI-ACCESS-KEY": c.api_key_id,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
    }


def get_ws_url() -> str:
    """Get the appropriate WebSocket URL based on client config."""
    c = get_client()
    return WS_DEMO_URL if "demo" in c.api_base else WS_PROD_URL


@app.websocket("/ws/market/{ticker}")
async def market_websocket(websocket: WebSocket, ticker: str):
    """
    WebSocket proxy for real-time market data.

    Connects to Kalshi's WebSocket API and forwards orderbook_delta and ticker
    messages for the specified market. The frontend maintains orderbook state
    by applying deltas to the initial snapshot.

    Message types forwarded:
    - orderbook_snapshot: Initial full orderbook state
    - orderbook_delta: Incremental orderbook updates
    - ticker: Price/volume/OI updates
    """
    await websocket.accept()

    try:
        import websockets
    except ImportError:
        await websocket.send_json({"error": "websockets library not installed"})
        await websocket.close()
        return

    kalshi_ws = None
    try:
        # Connect to Kalshi WebSocket
        headers = get_ws_auth_headers()
        ws_url = get_ws_url()

        logger.info(f"Connecting to Kalshi WS for {ticker}")

        async with websockets.connect(
            ws_url,
            additional_headers=headers,
            ping_interval=20,
            ping_timeout=10,
        ) as kalshi_ws:
            # Subscribe to orderbook, ticker, and trade channels
            subscribe_msg = {
                "id": 1,
                "cmd": "subscribe",
                "params": {
                    "channels": ["orderbook_delta", "ticker", "trade"],
                    "market_ticker": ticker
                }
            }
            await kalshi_ws.send(json.dumps(subscribe_msg))
            logger.info(f"Subscribed to {ticker}")

            # Forward messages from Kalshi to browser
            async for message in kalshi_ws:
                try:
                    data = json.loads(message)
                    msg_type = data.get("type")

                    # Only forward relevant message types
                    if msg_type in ("orderbook_snapshot", "orderbook_delta", "ticker", "trade", "subscribed", "error"):
                        await websocket.send_text(message)
                except json.JSONDecodeError:
                    pass
                except WebSocketDisconnect:
                    logger.info(f"Browser disconnected while forwarding for {ticker}")
                    break

    except WebSocketDisconnect:
        logger.info(f"Browser disconnected from {ticker}")
    except Exception as e:
        logger.error(f"WebSocket error for {ticker}: {e}")
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass  # Browser may already be disconnected
    finally:
        # Ensure browser websocket is closed
        logger.info(f"Closing WebSocket for {ticker}")
        try:
            await websocket.close()
        except Exception:
            pass  # Already closed
